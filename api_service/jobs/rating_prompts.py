"""Ask users how they liked what they watched, with one chat tap per rating.

``run_rating_prompts`` (scheduled) syncs each opted-in user's play history and sends a
prompt for titles played long enough ago, to Telegram or to a Discord DM. Telegram taps are
read by ``run_rating_answers`` (scheduled ``getUpdates`` polling); Discord taps arrive at the
signed ``/api/discord/interactions`` route, which calls :func:`answer_discord_interaction`.
Messages go out directly rather than through the webhook queue, so a stale queued prompt can
never be sent. Delivery is at-most-once: an ambiguous send is never repeated.
"""
import hmac
import json
import re
import threading
from datetime import datetime, timedelta, timezone

from api_service.config.logger_manager import LoggerManager
from api_service.db.components.rating_prompt_mixin import discord_credentials_complete
from api_service.db.database_manager import DatabaseManager
from api_service.services import discord_interactions as discord
from api_service.services.http.guarded_session import send_bytes
from api_service.services.notification_formats import (
    render_rating_prompt, telegram_bot_base, telegram_chat_id,
)
from api_service.services.watch_history_sync import (
    SUPPORTED_PROVIDERS, identity_for_user, selected_provider, sync_identity_history,
)
from api_service.utils.asyncio_loop import run_coroutine_sync
from api_service.utils.ssrf_guard import validate_url

logger = LoggerManager.get_logger('RatingPrompts')
MAX_PROMPTS_PER_RUN = 5
DISCORD_API = 'https://discord.com/api/v10'
DISCORD_ALLOW_PRIVATE = False  # only tests point DISCORD_API at a local fake
_DISCORD_AGENT = 'DiscordBot (https://github.com/giuseppe99barchetta/SuggestArr, 1)'
_CALLBACK = re.compile(r'rp:(\d{1,12}):([0-9a-f]{16}):(\d{1,2})')
_prompt_lock = threading.Lock()
_answer_lock = threading.Lock()
_offsets = {}  # Telegram bot base -> next getUpdates offset; lost on restart, replays are harmless
_warned = set()


class NotSent(Exception):
    """The message was definitely not created (rejected before sending, or by the chat service itself)."""

    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status, self.code = status, code


def telegram_destination(db, user_id):
    """The user's personal Telegram destination, if it can carry rating prompts.

    Returns:
        ``{url, chat_id, base, allow_private}`` or None (not Telegram, no private numeric
        chat id, or a URL that does not end in ``/sendMessage``).
    """
    config = db.get_personal_notification(user_id)
    if not config or config.get('format') != 'telegram':
        return None
    url = config.get('url')
    chat_id, base = telegram_chat_id(url), telegram_bot_base(url)
    if not chat_id or not base:
        return None
    return {'url': url, 'chat_id': chat_id, 'base': base, 'allow_private': bool(config.get('allow_private'))}


def prompt_destination(db, user_id, config):
    """Where this user's prompts go, from their rating-prompt settings, or None when not deliverable.

    Every destination carries ``channel``, ``bot_key`` (which bot/application the tap must arrive through) and
    ``sender_id`` (the one account allowed to tap).
    """
    if config['channel'] == 'discord':
        creds = config['discord']
        if not discord_credentials_complete(creds):
            return None
        key = creds['public_key'].lower()
        return {'channel': 'discord', 'token': creds['bot_token'], 'public_key': key,
                'user_id': creds['user_id'], 'bot_key': key, 'sender_id': creds['user_id']}
    telegram = telegram_destination(db, user_id)
    if not telegram:
        return None
    return {**telegram, 'channel': 'telegram', 'bot_key': telegram['base'], 'sender_id': telegram['chat_id']}


def _post(db, url, payload, allow_private, headers=None):
    """POST JSON under the webhook worker's outbound rules; returns ``(status, json_object_or_None)``."""
    try:
        validate_url(url, allow_private=allow_private)
        if not db.is_webhook_destination_allowed(url):
            raise ValueError('Destination is not in the allowlist')
    except ValueError as exc:
        raise NotSent(str(exc)) from None
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')
    status, raw = run_coroutine_sync(send_bytes(
        'POST', url, data=data, allow_private=allow_private,
        headers={'Content-Type': 'application/json', 'User-Agent': 'SuggestArr-Webhook/1', **(headers or {})}), logger)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = None
    return status, parsed if isinstance(parsed, dict) else None


def _send_prompt(db, dest, body):
    """Send one Telegram prompt. Returns on success, raises NotSent on a definite rejection, anything else is ambiguous."""
    status, data = _post(db, dest['url'], body.encode('utf-8'), dest['allow_private'])
    if 200 <= status < 300 and data and data.get('ok') is True:
        return
    code = data.get('error_code') if data else None
    if data and data.get('ok') is False and isinstance(code, int) and 400 <= code < 500:
        raise NotSent(f'Telegram error {code}', status, code)
    raise RuntimeError(f'Unconfirmed send (HTTP {status})')


def _discord_call(db, dest, path, payload):
    return _post(db, f'{DISCORD_API}{path}', payload, DISCORD_ALLOW_PRIVATE,
                 headers={'Authorization': f"Bot {dest['token']}", 'User-Agent': _DISCORD_AGENT})


def _discord_rejection(status, data):
    """``(code, True)`` when Discord itself rejected the request (a JSON error body with a 4xx status)."""
    code = data.get('code') if data else None
    return code, bool(data and isinstance(code, int) and 'message' in data and 400 <= status <= 429)


def _discord_dm_channel(db, dest):
    """The id of the DM with the user. Any failure is safe to retry: no message exists yet."""
    try:
        status, data = _discord_call(db, dest, '/users/@me/channels', {'recipient_id': dest['user_id']})
    except NotSent:
        raise
    except Exception as exc:
        raise NotSent(f'Could not open the DM ({type(exc).__name__})') from None
    if 200 <= status < 300 and data and data.get('id'):
        return str(data['id'])
    code, _ = _discord_rejection(status, data)
    raise NotSent(f'Could not open the DM (HTTP {status}, code {code})', status, code)


def _send_discord_message(db, dest, channel_id, payload):
    """Post a message into the DM. Success returns; a Discord-originated rejection raises NotSent; anything else is ambiguous."""
    status, data = _discord_call(db, dest, f'/channels/{channel_id}/messages', payload)
    if 200 <= status < 300 and data and data.get('id'):
        return
    code, rejected = _discord_rejection(status, data)
    if rejected:
        raise NotSent(f'Discord error {code}', status, code)
    raise RuntimeError(f'Unconfirmed send (HTTP {status})')


def describe_discord_failure(exc):
    """A plain sentence for the person setting Discord up, from a NotSent error."""
    if exc.code == 50007:
        return ('Discord does not let this bot message you: share a server with the bot (or install it to your '
                'account) and allow direct messages from server members.')
    if exc.status == 401:
        return 'Discord rejected the bot token.'
    if exc.code is not None:
        return f'Discord refused the message (code {exc.code}).'
    return 'Discord refused the message.'


def send_test_message(db, config):
    """Send a plain test DM through the user's Discord bot.

    Returns:
        ``(True, None)`` or ``(False, reason)``.
    """
    dest = prompt_destination(db, 0, config)
    if not dest or dest['channel'] != 'discord':
        return False, 'Discord needs the bot token, the application public key and your user id.'
    try:
        channel_id = _discord_dm_channel(db, dest)
        _send_discord_message(db, dest, channel_id, {
            'content': 'SuggestArr: rating prompts are connected.', 'allowed_mentions': {'parse': []}})
    except NotSent as exc:
        return False, describe_discord_failure(exc)
    except Exception as exc:
        logger.warning('Discord test message unconfirmed: %s', type(exc).__name__)
        return False, 'Could not tell whether Discord delivered the message. Try again.'
    return True, None


def _cutoff(config):
    """Latest play time (naive UTC) that already counts as long enough ago."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=config['delay_hours'])


def _prompt_label(title):
    return f"{title['title']} ({title['year']})" if title.get('year') else title['title']


def _fresh_state(db, user_id, provider, identity, title):
    """Re-read what a prompt depends on, right before it is claimed.

    Returns:
        ``(config, destination)`` when the title may still be asked about, ``False`` when only this title no
        longer qualifies (rated, excluded, played again, delay changed), ``None`` when the user's whole run
        should stop (switched off, deactivated, destination or media link changed).
    """
    config = db.active_rating_prompt_config(user_id)
    dest = prompt_destination(db, user_id, config) if config else None
    current = identity_for_user(db, user_id, provider, verified_only=True)
    if not dest or not current or current['id'] != identity['id']:
        return None
    if not db.eligible_rating_prompt_titles(user_id, identity['id'], config['enabled_at'], _cutoff(config),
                                            1, only=(title['tmdb_id'], title['media_type'])):
        return False
    return config, dest


def _prompt_user(db, user_id, provider):
    config = db.get_rating_prompt_config(user_id)
    identity = identity_for_user(db, user_id, provider, verified_only=True)
    if not config['enabled'] or not identity or not prompt_destination(db, user_id, config):
        return
    result = sync_identity_history(db, provider, identity, logger)
    if result is None or result[1]:
        return  # server not configured or history only partly read: a recent replay could be hidden
    candidates = db.eligible_rating_prompt_titles(
        user_id, identity['id'], config['enabled_at'], _cutoff(config), MAX_PROMPTS_PER_RUN)
    dm_channels = {}
    for title in candidates:
        # Everything is re-read per title: sending can take seconds, and the person may have
        # rated or excluded it, changed the delay, switched off, or moved their account meanwhile.
        state = _fresh_state(db, user_id, provider, identity, title)
        if state is None:
            return
        if state is False:
            continue
        config, dest = state
        if dest['channel'] == 'discord' and (dest['token'], dest['user_id']) not in dm_channels:
            # The one slow network step before the claim; the state is re-read right after it.
            try:
                dm_channels[(dest['token'], dest['user_id'])] = _discord_dm_channel(db, dest)
            except NotSent as exc:
                logger.warning('Rating prompts for user %s not sent: %s', user_id, exc)
                return  # nothing is claimed yet, the next run retries
            state = _fresh_state(db, user_id, provider, identity, title)
            if state is None:
                return
            if state is False:
                continue
            config, dest = state
            if dest['channel'] != 'discord' or (dest['token'], dest['user_id']) not in dm_channels:
                return  # the destination changed while the DM was being opened
        prompt = db.claim_rating_prompt(user_id, identity['id'], title, config['generation'])
        if prompt is False:
            return  # the delivery destination changed since it was read
        if not prompt:
            continue
        try:
            if dest['channel'] == 'discord':
                _send_discord_message(db, dest, dm_channels[(dest['token'], dest['user_id'])], {
                    'content': f'What did you think of {_prompt_label(title)}?',
                    'allowed_mentions': {'parse': []},
                    'components': discord.prompt_components(prompt['id'], prompt['nonce'])})
            else:
                _, body = render_rating_prompt(dest['url'], title['title'], title['year'], prompt['id'], prompt['nonce'])
                _send_prompt(db, dest, body)
            db.mark_rating_prompt_sent(prompt['id'])
        except NotSent as exc:
            db.drop_rating_prompt(prompt['id'])
            logger.warning('Rating prompt for user %s not sent: %s', user_id, exc)
        except Exception as exc:
            # Ambiguous: the message may have arrived, so the claim stays and nothing is resent.
            logger.warning('Rating prompt for user %s has an unconfirmed send: %s', user_id, type(exc).__name__)


def run_rating_prompts():
    """Scheduled entry point: send due prompts for every opted-in user."""
    if not _prompt_lock.acquire(blocking=False):
        return
    try:
        provider = selected_provider()
        if provider not in SUPPORTED_PROVIDERS:
            return
        db = DatabaseManager()
        for user_id in db.list_users_with_rating_prompts():
            try:
                _prompt_user(db, user_id, provider)
            except Exception as exc:
                logger.warning('Rating prompts skipped for user %s: %s', user_id, type(exc).__name__)
    finally:
        _prompt_lock.release()


def _apply_tap(db, custom_id, channel, bot_key, sender, private):
    """Apply one button tap if every ownership check passes.

    Args:
        db: DatabaseManager.
        custom_id: The button's ``rp:<prompt>:<nonce>:<n>`` payload.
        channel: ``telegram`` or ``discord``.
        bot_key: The bot (Telegram bot base) or application (Discord public key) the tap arrived through.
        sender: The account that tapped.
        private: Whether the tap came from a private one-to-one chat.

    Returns:
        ``(outcome, prompt, value)`` with outcome ``saved``, ``already_rated`` or ``unavailable``.
    """
    match = _CALLBACK.fullmatch(custom_id or '')
    if not match:
        return 'unavailable', None, 0
    prompt = db.get_rating_prompt(int(match.group(1)))
    if not prompt or not hmac.compare_digest(prompt['nonce'], match.group(2)):
        return 'unavailable', None, 0
    dest = prompt_destination(db, prompt['user_id'], db.get_rating_prompt_config(prompt['user_id']))
    # Only the owner's own account, in a private chat, through the owner's own bot/application.
    if (not dest or not private or dest['channel'] != channel or dest['bot_key'] != bot_key
            or dest['sender_id'] != str(sender)):
        return 'unavailable', None, 0
    identity = identity_for_user(db, prompt['user_id'], selected_provider(), verified_only=True)
    if not identity or identity['id'] != prompt['identity_id']:
        return 'unavailable', None, 0
    value = int(match.group(3))
    return db.answer_rating_prompt_row(prompt['id'], match.group(2), value, identity['id']), prompt, value


def _saved_text(prompt, value):
    return f'Saved: {value}/10 for {prompt["title"]}'[:200]


def answer_rating_prompt(db, bot_base, callback):
    """Apply a Telegram ``callback_query``; returns the short text to show the person who tapped."""
    sender = (callback.get('from') or {}).get('id')
    chat = ((callback.get('message') or {}).get('chat') or {}).get('id')
    outcome, prompt, value = _apply_tap(db, callback.get('data'), 'telegram', bot_base, sender,
                                        chat is not None and str(chat) == str(sender))
    if outcome == 'saved':
        return _saved_text(prompt, value)
    return 'Already rated' if outcome == 'already_rated' else 'Not available'


def answer_discord_interaction(db, public_key, interaction):
    """Apply a Discord button interaction already verified against ``public_key``; returns the reply body."""
    user = interaction.get('user')
    # In a DM Discord sends ``user``; in a server it sends ``member`` instead.
    private = isinstance(user, dict) and not interaction.get('member')
    outcome, prompt, value = _apply_tap(db, (interaction.get('data') or {}).get('custom_id'), 'discord',
                                        public_key.lower(), (user or {}).get('id'), private)
    if outcome == 'saved':
        return discord.updated(_saved_text(prompt, value))
    if outcome == 'already_rated':
        return discord.updated('Already rated')
    return discord.refused()


def _poll(db, base, allow_private):
    payload = {'timeout': 0, 'limit': 100, 'allowed_updates': ['callback_query']}
    if base in _offsets:
        payload['offset'] = _offsets[base]
    status, data = _post(db, f'{base}/getUpdates', payload, allow_private)
    if not data or data.get('ok') is not True:
        if base not in _warned:
            _warned.add(base)
            logger.warning('Telegram polling failed (HTTP %s); a bot with a webhook set, or read by another '
                           'program, cannot be polled', status)
        return
    _warned.discard(base)
    for update in data.get('result') or []:
        callback = update.get('callback_query')
        if isinstance(callback, dict) and callback.get('id'):
            try:
                text = answer_rating_prompt(db, base, callback)
            except Exception as exc:
                # Transient failure (e.g. database): leave this update unconfirmed so Telegram serves it again.
                logger.warning('Could not handle a rating tap, will retry: %s', type(exc).__name__)
                return
            try:
                _post(db, f'{base}/answerCallbackQuery', {'callback_query_id': callback['id'], 'text': text},
                      allow_private)
            except Exception as exc:
                logger.warning('Could not confirm a rating tap to Telegram: %s', type(exc).__name__)
        # Handled (or deliberately ignored): only now is the update confirmed by the next offset.
        _offsets[base] = max(_offsets.get(base, 0), int(update.get('update_id', -1)) + 1)


def run_rating_answers():
    """Scheduled entry point: read button taps for every Telegram bot that has open prompts."""
    if not _answer_lock.acquire(blocking=False):
        return
    try:
        db = DatabaseManager()
        bots = {}
        for user_id in db.users_with_open_prompts():
            dest = prompt_destination(db, user_id, db.get_rating_prompt_config(user_id))
            if dest and dest['channel'] == 'telegram':
                # One stream per bot; the strictest outbound policy among its users applies.
                bots[dest['base']] = bots.get(dest['base'], True) and dest['allow_private']
        for base, allow_private in bots.items():
            try:
                _poll(db, base, allow_private)
            except Exception as exc:
                logger.warning('Telegram polling skipped: %s', type(exc).__name__)
    finally:
        _answer_lock.release()
