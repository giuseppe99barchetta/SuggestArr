"""Ask users how they liked what they watched, with one Telegram tap per rating.

``run_rating_prompts`` (scheduled) syncs each opted-in user's play history and sends
a prompt for titles played long enough ago. ``run_rating_answers`` (scheduled) polls
each bot with open prompts for button taps and stores the rating. Messages go out
directly rather than through the webhook queue, so a stale queued prompt can never
be sent. Delivery is at-most-once: an ambiguous send is never repeated.
"""
import hmac
import json
import re
import threading
from datetime import datetime, timedelta, timezone

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
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
_CALLBACK = re.compile(r'rp:(\d{1,12}):([0-9a-f]{16}):(\d{1,2})')
_prompt_lock = threading.Lock()
_answer_lock = threading.Lock()
_offsets = {}  # bot base -> next getUpdates offset; lost on restart, replays are harmless
_warned = set()


class NotSent(Exception):
    """The message was definitely not created (rejected before sending, or by Telegram itself)."""


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


def _post(db, url, payload, allow_private):
    """POST JSON to a Bot API URL under the webhook worker's outbound rules; returns ``(status, json_or_None)``."""
    try:
        validate_url(url, allow_private=allow_private)
        if not db.is_webhook_destination_allowed(url):
            raise ValueError('Destination is not in the allowlist')
    except ValueError as exc:
        raise NotSent(str(exc)) from None
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')
    status, raw = run_coroutine_sync(send_bytes(
        'POST', url, data=data, allow_private=allow_private,
        headers={'Content-Type': 'application/json', 'User-Agent': 'SuggestArr-Webhook/1'}), logger)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = None
    return status, parsed if isinstance(parsed, dict) else None


def _send_prompt(db, dest, body):
    """Send one prompt. Returns on success, raises NotSent on a definite rejection, anything else is ambiguous."""
    status, data = _post(db, dest['url'], body.encode('utf-8'), dest['allow_private'])
    if 200 <= status < 300 and data and data.get('ok') is True:
        return
    code = data.get('error_code') if data else None
    if data and data.get('ok') is False and isinstance(code, int) and 400 <= code < 500:
        raise NotSent(f'Telegram error {code}')
    raise RuntimeError(f'Unconfirmed send (HTTP {status})')


def _cutoff(config):
    """Latest play time (naive UTC) that already counts as long enough ago."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=config['delay_hours'])


def _prompt_user(db, user_id, provider):
    config = db.get_rating_prompt_config(user_id)
    identity = identity_for_user(db, user_id, provider, verified_only=True)
    if not config['enabled'] or not identity or not telegram_destination(db, user_id):
        return
    result = sync_identity_history(db, provider, identity, logger)
    if result is None or result[1]:
        return  # server not configured or history only partly read: a recent replay could be hidden
    candidates = db.eligible_rating_prompt_titles(
        user_id, identity['id'], config['enabled_at'], _cutoff(config), MAX_PROMPTS_PER_RUN)
    for title in candidates:
        # Everything is re-read per title: sending can take seconds, and the person may have
        # rated or excluded it, changed the delay, switched off, or moved their account meanwhile.
        config = db.active_rating_prompt_config(user_id)
        dest = telegram_destination(db, user_id)
        current = identity_for_user(db, user_id, provider, verified_only=True)
        if not config or not dest or not current or current['id'] != identity['id']:
            return
        if not db.eligible_rating_prompt_titles(user_id, identity['id'], config['enabled_at'], _cutoff(config),
                                                1, only=(title['tmdb_id'], title['media_type'])):
            continue
        prompt = db.claim_rating_prompt(user_id, identity['id'], title)
        if not prompt:
            continue
        _, body = render_rating_prompt(dest['url'], title['title'], title['year'], prompt['id'], prompt['nonce'])
        try:
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


def answer_rating_prompt(db, bot_base, callback):
    """Apply one button tap if every ownership check passes.

    Args:
        db: DatabaseManager.
        bot_base: Bot API base URL the tap arrived through.
        callback: Telegram ``callback_query`` object.

    Returns:
        The short text to show the person who tapped.
    """
    refused = 'Not available'
    match = _CALLBACK.fullmatch(callback.get('data') or '')
    if not match:
        return refused
    prompt = db.get_rating_prompt(int(match.group(1)))
    if not prompt or not hmac.compare_digest(prompt['nonce'], match.group(2)):
        return refused
    dest = telegram_destination(db, prompt['user_id'])
    sender = (callback.get('from') or {}).get('id')
    chat = ((callback.get('message') or {}).get('chat') or {}).get('id')
    # Only the private chat the owner configured may answer: no group members, no other bot.
    if not dest or dest['base'] != bot_base or str(sender) != dest['chat_id'] or str(chat) != dest['chat_id']:
        return refused
    identity = identity_for_user(db, prompt['user_id'], selected_provider(), verified_only=True)
    if not identity or identity['id'] != prompt['identity_id']:
        return refused
    value = int(match.group(3))
    outcome = db.answer_rating_prompt_row(prompt['id'], match.group(2), value, identity['id'])
    if outcome == 'saved':
        return f'Saved: {value}/10 for {prompt["title"]}'[:200]
    return 'Already rated' if outcome == 'already_rated' else refused


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
    """Scheduled entry point: read button taps for every bot that has open prompts."""
    if not _answer_lock.acquire(blocking=False):
        return
    try:
        db = DatabaseManager()
        bots = {}
        for user_id in db.users_with_open_prompts():
            dest = telegram_destination(db, user_id)
            if dest:
                # One stream per bot; the strictest outbound policy among its users applies.
                bots[dest['base']] = bots.get(dest['base'], True) and dest['allow_private']
        for base, allow_private in bots.items():
            try:
                _poll(db, base, allow_private)
            except Exception as exc:
                logger.warning('Telegram polling skipped: %s', type(exc).__name__)
    finally:
        _answer_lock.release()
