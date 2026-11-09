"""Storage for "how did you like it?" prompts sent after a title is played.

A prompt row is both the claim ("this title was asked once") and the key a chat button
refers to. States: ``pending`` (claimed, message possibly sent), ``sent`` (the chat
service accepted it), ``answered``. Open prompts (``pending``/``sent``) can be answered;
a rating is only ever written by :meth:`answer_rating_prompt_row`.

Delivery identity: the place a prompt is delivered to (Telegram bot + chat, or Discord
application + user) is fingerprinted by ``auth_users.rating_prompt_generation``, a counter
that only ever grows and is bumped in the same statement that changes the identity. A
prompt remembers the generation it was claimed under and can only be answered while that
is still current, so an old button can never come back to life after the destination
changed and was changed back.
"""
import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from api_service.exceptions.database_exceptions import RatingPromptConfigError
from api_service.services.notification_formats import telegram_bot_base, telegram_chat_id

DEFAULT_DELAY_HOURS = 12
MAX_DELAY_HOURS = 48
CHANNELS = ('telegram', 'discord')
_KEEP = object()  # "leave this column alone" in an identity-change writer
_HEX64 = re.compile(r'[0-9a-fA-F]{64}')
_SNOWFLAKE = re.compile(r'\d{17,20}')
_TOKEN = re.compile(r'\S{20,120}')
TELEGRAM_DESTINATION_HINT = ('Rating prompts need a Telegram destination: a sendMessage URL with your own numeric '
                             'chat_id (talk to the bot in a private chat).')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _loads(raw) -> dict:
    try:
        value = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def normalize_rating_prompt_config(raw: dict, generation: int = 0) -> Dict[str, Any]:
    """Turn the stored JSON into ``{enabled, delay_hours, enabled_at, channel, discord, generation}``.

    ``enabled_at`` is naive UTC or None. Without a start date nothing qualifies, so a damaged
    row can never flood the user. ``discord`` holds ``bot_token``, ``public_key`` and ``user_id``
    strings (possibly empty).
    """
    try:
        enabled_at = datetime.fromisoformat(raw['enabled_at']) if raw.get('enabled_at') else None
    except (TypeError, ValueError):
        enabled_at = None
    delay = raw.get('delay_hours')
    if not isinstance(delay, int) or isinstance(delay, bool) or not 0 <= delay <= MAX_DELAY_HOURS:
        delay = DEFAULT_DELAY_HOURS
    discord = raw.get('discord') if isinstance(raw.get('discord'), dict) else {}
    return {
        'enabled': bool(raw.get('enabled')) and enabled_at is not None,
        'delay_hours': delay, 'enabled_at': enabled_at,
        'channel': raw.get('channel') if raw.get('channel') in CHANNELS else 'telegram',
        'discord': {key: str(discord.get(key) or '') for key in ('bot_token', 'public_key', 'user_id')},
        'generation': int(generation or 0),
    }


def discord_credentials_complete(discord: dict) -> bool:
    """Whether a Discord bot token, application public key and user id are all present and well formed."""
    return bool(_TOKEN.fullmatch(discord.get('bot_token', '')) and _HEX64.fullmatch(discord.get('public_key', ''))
                and _SNOWFLAKE.fullmatch(discord.get('user_id', '')))


def delivery_identity(notify: dict, config: dict) -> tuple:
    """What a prompt is delivered to: changes here must invalidate outstanding buttons."""
    if config['channel'] == 'discord':
        return 'discord', config['discord']['public_key'].lower(), config['discord']['user_id']
    url = notify.get('url') if notify.get('format') == 'telegram' else None
    return 'telegram', telegram_bot_base(url), telegram_chat_id(url)


class RatingPromptMixin:
    """Per-user prompt settings plus the ``rating_prompts`` table."""

    # ── identity-changing writers (one connection, one UPDATE) ─────────────

    def _change_delivery_identity(self, user_id: int, change: Callable) -> Optional[tuple]:
        """Read the owner's notification + prompt config under a row lock and write the result in ONE statement.

        ``change(notify, raw_config, generation)`` returns ``(new_notify, new_raw_config, bump)`` where either
        value may be ``_KEEP``. The generation counter is incremented in that same UPDATE when ``bump`` is true,
        so a destination can never change without it. SQLite serialises writers with ``BEGIN IMMEDIATE``;
        MySQL/PostgreSQL lock the row with ``FOR UPDATE``.

        :return: ``(notify, raw_config)`` as stored afterwards, or None when the account does not exist.
        """
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if self.db_type == 'sqlite':
                    cursor.execute('BEGIN IMMEDIATE')
                lock = '' if self.db_type == 'sqlite' else ' FOR UPDATE'
                cursor.execute(f"SELECT notify_config, rating_prompt_config, rating_prompt_generation "
                               f"FROM auth_users WHERE id={ph}{lock}", (user_id,))
                row = cursor.fetchone()
                if not row:
                    conn.rollback()
                    return None
                notify, config = _loads(row[0]), _loads(row[1])
                new_notify, new_config, bump = change(notify, config, int(row[2] or 0))
                sets, params = [], []
                if new_notify is not _KEEP:
                    sets.append(f'notify_config={ph}')
                    params.append(json.dumps(new_notify) if new_notify else None)
                if new_config is not _KEEP:
                    sets.append(f'rating_prompt_config={ph}')
                    params.append(json.dumps(new_config) if new_config else None)
                if bump:
                    sets.append('rating_prompt_generation=rating_prompt_generation+1')
                if sets:
                    cursor.execute(f"UPDATE auth_users SET {', '.join(sets)} WHERE id={ph}", (*params, user_id))
                conn.commit()
                return (notify if new_notify is _KEEP else (new_notify or {}),
                        config if new_config is _KEEP else (new_config or {}))
            except Exception:
                conn.rollback()
                raise

    def set_personal_notification(self, user_id, config):
        """Save (or with None, remove) a user's own notification destination.

        Under the same lock and in the same UPDATE: while the rating-prompt channel is Telegram, a changed
        bot/chat (or removal) bumps the generation, and removal also switches those prompts off (the rest of
        the saved settings, including Discord credentials, is kept).
        """
        def change(notify, raw_config, _generation):
            if not raw_config:
                return config, _KEEP, False
            current = normalize_rating_prompt_config(raw_config)
            bump = delivery_identity(notify, current) != delivery_identity(config or {}, current)
            disable = config is None and current['channel'] == 'telegram' and raw_config.get('enabled')
            return config, ({**raw_config, 'enabled': False} if disable else _KEEP), bump
        self._change_delivery_identity(user_id, change)

    # ── settings (auth_users.rating_prompt_config, JSON) ───────────────────

    def get_rating_prompt_config(self, user_id: int) -> Dict[str, Any]:
        """Normalised settings plus the current ``generation`` (see :func:`normalize_rating_prompt_config`)."""
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT rating_prompt_config, rating_prompt_generation FROM auth_users WHERE id={ph}",
                           (user_id,))
            row = cursor.fetchone()
        return normalize_rating_prompt_config(_loads(row[0]) if row else {}, row[1] if row else 0)

    @staticmethod
    def public_rating_prompt_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """The settings as shown to their owner: the bot token is never included."""
        discord = config['discord']
        return {'enabled': config['enabled'], 'delay_hours': config['delay_hours'], 'channel': config['channel'],
                'discord': {'public_key': discord['public_key'], 'user_id': discord['user_id'],
                            'has_token': bool(discord['bot_token'])}}

    def set_rating_prompt_config(self, user_id: int, enabled: bool, delay_hours: int,
                                 channel: str = 'telegram', discord: Optional[dict] = None) -> Dict[str, Any]:
        """Save the settings. ``enabled_at`` is reset on every off -> on change, never otherwise.

        Discord fields are validated and stored on every call that supplies them (so credentials can be saved
        with prompts still off); an omitted ``bot_token`` keeps the stored one. Changing the channel or the
        Discord key / user id bumps the delivery generation in the same statement.

        :raises ValueError: for an invalid delay, channel, or Discord field, or when enabling Discord without
            complete credentials.
        """
        if isinstance(delay_hours, bool) or not isinstance(delay_hours, int) or not 0 <= delay_hours <= MAX_DELAY_HOURS:
            raise RatingPromptConfigError(f'delay_hours must be a whole number from 0 to {MAX_DELAY_HOURS}')
        if channel not in CHANNELS:
            raise RatingPromptConfigError('channel must be telegram or discord')
        if discord is not None and not isinstance(discord, dict):
            raise RatingPromptConfigError('discord must be an object')

        def change(notify, raw_config, _generation):
            current = normalize_rating_prompt_config(raw_config)
            stored = current['discord']
            merged = dict(stored)
            for key in ('bot_token', 'public_key', 'user_id'):
                value = (discord or {}).get(key)
                if value is not None and (key != 'bot_token' or value != ''):
                    merged[key] = str(value).strip()
            if merged['public_key'] and not _HEX64.fullmatch(merged['public_key']):
                raise RatingPromptConfigError('The application public key must be 64 hexadecimal characters')
            merged['public_key'] = merged['public_key'].lower()
            if merged['user_id'] and not _SNOWFLAKE.fullmatch(merged['user_id']):
                raise RatingPromptConfigError('The Discord user id must be 17 to 20 digits')
            if merged['bot_token'] and not _TOKEN.fullmatch(merged['bot_token']):
                raise RatingPromptConfigError('The bot token looks invalid')
            if channel == 'discord' and not discord_credentials_complete(merged):
                raise RatingPromptConfigError('Discord needs the bot token, the application public key and your user id')
            # Checked here, under the owner-row lock: a destination removed after the route's own check
            # (which only gives the friendly message first) must not end up with prompts switched on.
            if enabled and channel == 'telegram':
                _, base, chat_id = delivery_identity(notify, {'channel': 'telegram', 'discord': merged})
                if not base or not chat_id:
                    raise RatingPromptConfigError(TELEGRAM_DESTINATION_HINT)
            enabled_at = current['enabled_at'] if current['enabled'] else _utcnow()
            updated = {'enabled': bool(enabled), 'delay_hours': delay_hours, 'enabled_at': enabled_at.isoformat(),
                       'channel': channel, 'discord': merged}
            bump = bool(raw_config) and (delivery_identity(notify, current)
                                         != delivery_identity(notify, normalize_rating_prompt_config(updated)))
            return _KEEP, updated, bump

        if self._change_delivery_identity(user_id, change) is None:
            raise RatingPromptConfigError('Unknown account')
        return self.get_rating_prompt_config(user_id)

    def active_rating_prompt_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        """The settings when the account is active and has prompts switched on right now, else None."""
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT is_active FROM auth_users WHERE id={ph}", (user_id,))
            row = cursor.fetchone()
        if not (row and row[0]):
            return None
        config = self.get_rating_prompt_config(user_id)
        return config if config['enabled'] else None

    def list_users_with_rating_prompts(self) -> List[int]:
        """Ids of active accounts whose settings are switched on."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, is_active FROM auth_users WHERE rating_prompt_config IS NOT NULL")
            ids = [row[0] for row in cursor.fetchall() if row[1]]
        return [user_id for user_id in ids if self.get_rating_prompt_config(user_id)['enabled']]

    def discord_public_keys(self) -> List[str]:
        """Application public keys (lower-case hex) of active accounts that saved complete Discord credentials.

        Prompts need not be switched on: Discord's signed PING at URL-save time must already verify.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_active, rating_prompt_config FROM auth_users WHERE rating_prompt_config IS NOT NULL")
            rows = cursor.fetchall()
        keys = set()
        for is_active, raw in rows:
            config = normalize_rating_prompt_config(_loads(raw))
            if is_active and config['channel'] == 'discord' and discord_credentials_complete(config['discord']):
                keys.add(config['discord']['public_key'].lower())
        return sorted(keys)

    # ── candidates and prompt rows ─────────────────────────────────────────

    def eligible_rating_prompt_titles(self, user_id: int, identity_id: int, enabled_at: datetime,
                                      cutoff: datetime, limit: int,
                                      only: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Played, unrated, not-excluded titles last played in ``[enabled_at, cutoff]`` and never asked about.

        :param cutoff: Naive UTC; latest play time that already counts as "long enough ago".
        :param only: ``(tmdb_id, media_type)`` to check just that title right before sending.
        :return: Oldest play first, at most ``limit`` of ``{tmdb_id, media_type, title, year}``.
        """
        ph = self._ph()
        extra, extra_params = '', ()
        if only:
            extra, extra_params = f' AND w.tmdb_id={ph} AND w.media_type={ph}', (str(only[0]), only[1])
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT w.tmdb_id, w.media_type, w.title, w.year FROM watched_media w "
                f"WHERE w.media_user_identity_id={ph} AND w.rating IS NULL AND w.excluded=0 "
                f"AND w.watched_at IS NOT NULL AND w.watched_at>={ph} AND w.watched_at<={ph} "
                f"AND NOT EXISTS (SELECT 1 FROM rating_prompts p WHERE p.user_id={ph} "
                f"AND p.media_user_identity_id=w.media_user_identity_id AND p.tmdb_id=w.tmdb_id "
                f"AND p.media_type=w.media_type){extra} ORDER BY w.watched_at ASC LIMIT {ph}",
                (identity_id, enabled_at, cutoff, user_id, *extra_params, limit),
            )
            return [{'tmdb_id': str(row[0]), 'media_type': row[1], 'title': row[2], 'year': row[3]}
                    for row in cursor.fetchall()]

    def claim_rating_prompt(self, user_id: int, identity_id: int, title: Dict[str, Any],
                            generation: Optional[int] = None):
        """Insert a ``pending`` prompt in one statement.

        :param generation: The delivery generation the caller read; the row is inserted only while it is still
            current (``None`` skips the check and uses whatever is current).
        :return: ``{id, nonce}`` when claimed, ``None`` when this title was already claimed for the user, ``False``
            when the delivery destination changed since ``generation`` was read.
        """
        ph = self._ph()
        nonce = secrets.token_hex(8)
        key = (user_id, identity_id, str(title['tmdb_id']), title['media_type'])
        where = f"user_id={ph} AND media_user_identity_id={ph} AND tmdb_id={ph} AND media_type={ph}"
        guard, guard_params = (f" AND rating_prompt_generation={ph}", (generation,)) if generation is not None else ('', ())
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"INSERT INTO rating_prompts (user_id, media_user_identity_id, tmdb_id, media_type, title, nonce, "
                    f"generation) SELECT {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, rating_prompt_generation "
                    f"FROM auth_users WHERE id={ph}{guard}",
                    (*key, str(title['title'])[:500], nonce, user_id, *guard_params))
                inserted = cursor.rowcount
                conn.commit()
            if not inserted:
                return False
        except Exception:
            # The UNIQUE constraint is the claim: a row already there means someone else got it first.
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT 1 FROM rating_prompts WHERE {where}", key)
                if cursor.fetchone():
                    return None
            raise
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id FROM rating_prompts WHERE {where}", key)
            return {'id': cursor.fetchone()[0], 'nonce': nonce}

    def mark_rating_prompt_sent(self, prompt_id: int) -> None:
        """``pending`` -> ``sent``; a prompt already answered while the send was in flight stays answered."""
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE rating_prompts SET status='sent' WHERE id={ph} AND status='pending'", (prompt_id,))
            conn.commit()

    def drop_rating_prompt(self, prompt_id: int) -> None:
        """Delete a prompt whose message definitely was not sent, so the next run retries it."""
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM rating_prompts WHERE id={ph} AND status='pending'", (prompt_id,))
            conn.commit()

    def get_rating_prompt(self, prompt_id: int) -> Optional[Dict[str, Any]]:
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT id, user_id, media_user_identity_id, tmdb_id, media_type, title, nonce, status, generation "
                f"FROM rating_prompts WHERE id={ph}", (prompt_id,))
            row = cursor.fetchone()
        if not row:
            return None
        return {'id': row[0], 'user_id': row[1], 'identity_id': row[2], 'tmdb_id': str(row[3]),
                'media_type': row[4], 'title': row[5], 'nonce': row[6], 'status': row[7], 'generation': row[8]}

    def users_with_open_prompts(self) -> List[int]:
        """Ids of accounts that have at least one unanswered prompt."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM rating_prompts WHERE status IN ('pending','sent')")
            return [row[0] for row in cursor.fetchall()]

    def answer_rating_prompt_row(self, prompt_id: int, nonce: str, value: int, identity_id: int) -> str:
        """Claim a prompt and store its rating in one transaction.

        The owner's state is re-read on the same connection, so a deactivated account, a switched-off
        setting, a changed delivery destination (generation) or an unlinked/replaced media profile cannot
        rate through an old button. A title that was rated in the meantime keeps its rating.

        The owner row is locked (``FOR UPDATE`` on MySQL/PostgreSQL; on SQLite the claim UPDATE already holds
        the write lock) so a concurrent destination change either commits first, which refuses this tap, or
        waits until this rating is committed.

        :param identity_id: The owner's *current* verified media identity; must equal the prompt's.
        :return: ``'saved'``, ``'already_rated'`` or ``'unavailable'``.
        """
        ph = self._ph()
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10:
            return 'unavailable'
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE rating_prompts SET status='answered', answered_at={ph} "
                    f"WHERE id={ph} AND nonce={ph} AND status IN ('pending','sent') AND media_user_identity_id={ph}",
                    (_utcnow(), prompt_id, nonce, identity_id))
                if cursor.rowcount != 1:
                    conn.rollback()
                    return 'unavailable'
                cursor.execute(
                    f"SELECT p.tmdb_id, p.media_type, u.is_active, u.rating_prompt_config, p.user_id, "
                    f"p.generation, u.rating_prompt_generation "
                    f"FROM rating_prompts p JOIN auth_users u ON u.id=p.user_id WHERE p.id={ph}"
                    f"{'' if self.db_type == 'sqlite' else ' FOR UPDATE'}", (prompt_id,))
                tmdb_id, media_type, is_active, raw, user_id, generation, current_generation = cursor.fetchone()
                enabled = normalize_rating_prompt_config(_loads(raw))['enabled']
                # The owner must still hold a verified link to this very identity.
                cursor.execute(
                    f"SELECT p.verified FROM user_media_profiles p JOIN media_user_identities i "
                    f"ON i.provider=p.provider AND i.external_user_id=p.external_user_id "
                    f"WHERE p.user_id={ph} AND i.id={ph}", (user_id, identity_id))
                linked = any(bool(row[0]) for row in cursor.fetchall())
                if not is_active or not enabled or not linked or int(generation or 0) != int(current_generation or 0):
                    conn.rollback()
                    return 'unavailable'
                cursor.execute(
                    f"SELECT rating FROM watched_media WHERE media_user_identity_id={ph} AND tmdb_id={ph} AND media_type={ph}",
                    (identity_id, tmdb_id, media_type))
                row = cursor.fetchone()
                if row is None:
                    conn.rollback()
                    return 'unavailable'
                if row[0] is not None:
                    conn.commit()  # asked once, answered elsewhere: keep the claim, keep their rating
                    return 'already_rated'
                cursor.execute(
                    f"UPDATE watched_media SET rating={ph}, updated_at=CURRENT_TIMESTAMP WHERE media_user_identity_id={ph} "
                    f"AND tmdb_id={ph} AND media_type={ph} AND rating IS NULL",
                    (float(value), identity_id, tmdb_id, media_type))
                if cursor.rowcount != 1:
                    conn.rollback()
                    return 'unavailable'
                conn.commit()
                return 'saved'
            except Exception:
                conn.rollback()
                raise
