"""Storage for "how did you like it?" prompts sent after a title is played.

A prompt row is both the claim ("this title was asked once") and the key a Telegram
button refers to. States: ``pending`` (claimed, message possibly sent), ``sent``
(Telegram accepted it), ``answered``. Open prompts (``pending``/``sent``) can be
answered; a rating is only ever written by :meth:`answer_rating_prompt_row`.
"""
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DEFAULT_DELAY_HOURS = 12
MAX_DELAY_HOURS = 48
OPEN_STATES = ('pending', 'sent')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RatingPromptMixin:
    """Per-user prompt settings plus the ``rating_prompts`` table."""

    # ── settings (auth_users.rating_prompt_config, JSON) ───────────────────

    def get_rating_prompt_config(self, user_id: int) -> Dict[str, Any]:
        """Return ``{enabled, delay_hours, enabled_at}``; ``enabled_at`` is naive UTC or None."""
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT rating_prompt_config FROM auth_users WHERE id={ph}", (user_id,))
            row = cursor.fetchone()
        try:
            raw = json.loads(row[0]) if row and row[0] else {}
        except (TypeError, ValueError):
            raw = {}
        try:
            enabled_at = datetime.fromisoformat(raw['enabled_at']) if raw.get('enabled_at') else None
        except (TypeError, ValueError):
            enabled_at = None
        delay = raw.get('delay_hours')
        if not isinstance(delay, int) or isinstance(delay, bool) or not 0 <= delay <= MAX_DELAY_HOURS:
            delay = DEFAULT_DELAY_HOURS
        # Without a start date nothing qualifies, so a damaged row can never flood the user.
        return {'enabled': bool(raw.get('enabled')) and enabled_at is not None,
                'delay_hours': delay, 'enabled_at': enabled_at}

    def set_rating_prompt_config(self, user_id: int, enabled: bool, delay_hours: int) -> Dict[str, Any]:
        """Save the settings. ``enabled_at`` is reset on every off -> on change, never otherwise.

        :raises ValueError: when ``delay_hours`` is not an integer from 0 to 48.
        """
        if isinstance(delay_hours, bool) or not isinstance(delay_hours, int) or not 0 <= delay_hours <= MAX_DELAY_HOURS:
            raise ValueError(f'delay_hours must be a whole number from 0 to {MAX_DELAY_HOURS}')
        current = self.get_rating_prompt_config(user_id)
        enabled_at = current['enabled_at'] if current['enabled'] else _utcnow()
        payload = {'enabled': bool(enabled), 'delay_hours': delay_hours, 'enabled_at': enabled_at.isoformat()}
        self._write_rating_prompt_config(user_id, payload)
        return {'enabled': bool(enabled), 'delay_hours': delay_hours, 'enabled_at': enabled_at}

    def clear_rating_prompt_config(self, user_id: int) -> None:
        """Remove the settings (used when the notification destination is removed)."""
        self._write_rating_prompt_config(user_id, None)

    def _write_rating_prompt_config(self, user_id: int, payload: Optional[dict]) -> None:
        ph = self._ph()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE auth_users SET rating_prompt_config={ph} WHERE id={ph}",
                           (json.dumps(payload) if payload else None, user_id))
            conn.commit()

    def list_users_with_rating_prompts(self) -> List[int]:
        """Ids of active accounts whose settings are switched on."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, is_active FROM auth_users WHERE rating_prompt_config IS NOT NULL")
            ids = [row[0] for row in cursor.fetchall() if row[1]]
        return [user_id for user_id in ids if self.get_rating_prompt_config(user_id)['enabled']]

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

    def claim_rating_prompt(self, user_id: int, identity_id: int, title: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insert a ``pending`` prompt; ``None`` when this title was already claimed for the user."""
        ph = self._ph()
        nonce = secrets.token_hex(8)
        key = (user_id, identity_id, str(title['tmdb_id']), title['media_type'])
        where = f"user_id={ph} AND media_user_identity_id={ph} AND tmdb_id={ph} AND media_type={ph}"
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"INSERT INTO rating_prompts (user_id, media_user_identity_id, tmdb_id, media_type, title, nonce) "
                    f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})", (*key, str(title['title'])[:500], nonce))
                conn.commit()
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
                f"SELECT id, user_id, media_user_identity_id, tmdb_id, media_type, title, nonce, status "
                f"FROM rating_prompts WHERE id={ph}", (prompt_id,))
            row = cursor.fetchone()
        if not row:
            return None
        return {'id': row[0], 'user_id': row[1], 'identity_id': row[2], 'tmdb_id': str(row[3]),
                'media_type': row[4], 'title': row[5], 'nonce': row[6], 'status': row[7]}

    def users_with_open_prompts(self) -> List[int]:
        """Ids of accounts that have at least one unanswered prompt."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM rating_prompts WHERE status IN ('pending','sent')")
            return [row[0] for row in cursor.fetchall()]

    def answer_rating_prompt_row(self, prompt_id: int, nonce: str, value: int, identity_id: int) -> str:
        """Claim a prompt and store its rating in one transaction.

        The owner's state is re-read on the same connection, so a deactivated account,
        a switched-off setting or an unlinked/replaced media profile cannot rate through an old button.
        A title that was rated in the meantime keeps its rating.

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
                    f"SELECT p.tmdb_id, p.media_type, u.is_active, u.rating_prompt_config, p.user_id "
                    f"FROM rating_prompts p JOIN auth_users u ON u.id=p.user_id WHERE p.id={ph}", (prompt_id,))
                tmdb_id, media_type, is_active, raw, user_id = cursor.fetchone()
                try:
                    enabled = bool(json.loads(raw).get('enabled')) if raw else False
                except (TypeError, ValueError, AttributeError):
                    enabled = False
                # The owner must still hold a verified link to this very identity.
                cursor.execute(
                    f"SELECT p.verified FROM user_media_profiles p JOIN media_user_identities i "
                    f"ON i.provider=p.provider AND i.external_user_id=p.external_user_id "
                    f"WHERE p.user_id={ph} AND i.id={ph}", (user_id, identity_id))
                linked = any(bool(row[0]) for row in cursor.fetchall())
                if not is_active or not enabled or not linked:
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
