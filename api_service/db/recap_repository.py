"""Durable recap progress and per-administrator reminder preferences.

The ledger deliberately has no foreign keys to disposable request history or media
users. Only successful, canonical SuggestArr requests can seed it.
"""
from datetime import datetime, timedelta, timezone

from api_service.services.recap_badges import LedgerTitle, build_badges


SUPPORT_MILESTONES = (100, 500, 1000, 5000, 10000)
WATCH_PROVIDERS = ('plex', 'jellyfin')


def watch_provider(env):
    """Return the media server able to report watched titles, or ``None`` when unconfigured."""
    provider = (env.get('SELECTED_SERVICE') or '').lower()
    prefix = provider.upper()
    if provider in WATCH_PROVIDERS and env.get(f'{prefix}_API_URL') and env.get(f'{prefix}_TOKEN'):
        return provider
    return None


def utc_datetime(value):
    if value is None:
        return None
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def insert_ignore(db_type, table, columns, select_or_values):
    """Compose SQL from internal constants only; values remain parameterized."""
    prefix = 'INSERT OR IGNORE' if db_type == 'sqlite' else 'INSERT IGNORE' if db_type in ('mysql', 'mariadb') else 'INSERT'
    query = f'{prefix} INTO {table} ({columns}) {select_or_values}'
    return query + (' ON CONFLICT DO NOTHING' if db_type == 'postgres' else '')


def record_requested_title(cursor, db_type, media_type=None, media_id=None):
    """Backfill all history, or record one canonical title in the caller's transaction."""
    ph = '?' if db_type == 'sqlite' else '%s'
    query = ("SELECT media_type, tmdb_request_id, user_id, COALESCE(requested_at,CURRENT_TIMESTAMP) FROM requests "
             "WHERE requested_by='SuggestArr' AND media_type IN ('movie','tv')")
    params = ()
    if media_type is not None:
        query += f' AND media_type={ph} AND tmdb_request_id={ph}'
        params = (media_type, str(media_id))
    query += ' ORDER BY requested_at ASC'
    # WHERE also disambiguates SQLite's INSERT ... SELECT ... ON CONFLICT grammar.
    cursor.execute(insert_ignore(db_type, 'recap_titles',
                                 'media_type, tmdb_id, user_id, requested_at', query), params)


def _columns(cursor, db_type, table):
    """Existing column names of an internal table, for additive migrations."""
    if db_type == 'sqlite':
        cursor.execute(f'PRAGMA table_info({table})')
        return {row[1] for row in cursor.fetchall()}
    if db_type == 'postgres':
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'")
    else:
        cursor.execute(f'SHOW COLUMNS FROM {table}')
    return {row[0] for row in cursor.fetchall()}


def initialize_recap_schema(db):
    """Additive and repeatable on SQLite, PostgreSQL and MySQL/MariaDB."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS recap_titles (
            media_type VARCHAR(16) NOT NULL, tmdb_id VARCHAR(64) NOT NULL,
            user_id VARCHAR(191), requested_at TIMESTAMP NOT NULL, watched_at TIMESTAMP NULL,
            PRIMARY KEY (media_type, tmdb_id))''')
        if 'watched_at' not in _columns(cursor, db.db_type, 'recap_titles'):
            # First observed play of a requested title by its recipient, at or after the request.
            cursor.execute('ALTER TABLE recap_titles ADD COLUMN watched_at TIMESTAMP NULL')
        if db.db_type in ('mysql', 'mariadb'):
            cursor.execute("SHOW INDEX FROM recap_titles WHERE Key_name='idx_recap_titles_user'")
            if not cursor.fetchall():
                cursor.execute('CREATE INDEX idx_recap_titles_user ON recap_titles (user_id)')
        else:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_recap_titles_user ON recap_titles (user_id)')
        cursor.execute('''CREATE TABLE IF NOT EXISTS recap_preferences (
            user_id INTEGER PRIMARY KEY, reminder_mode VARCHAR(16) NOT NULL DEFAULT 'enabled')''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS recap_prompts (
            user_id INTEGER NOT NULL, scope VARCHAR(16) NOT NULL,
            highest_milestone INTEGER NOT NULL DEFAULT 0,
            last_shown_at TIMESTAMP NULL, snoozed_until TIMESTAMP NULL,
            snoozed_milestone INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, scope))''')
        record_requested_title(cursor, db.db_type)
        conn.commit()


class RecapRepository:
    def __init__(self, db):
        self.db = db
        self.ph = '?' if db.db_type == 'sqlite' else '%s'

    def _scope(self, user, env):
        installation = user.get('role') == 'admin' and env.get('REQUEST_VISIBILITY') != 'own_all'
        ids = None if installation else sorted(set(
            str(profile['external_user_id']) for profile in self.db.get_user_media_profiles(int(user['id']))
            if profile.get('provider') in ('plex', 'jellyfin', 'emby')))
        return ('installation' if installation else 'personal'), ids

    def _restriction(self, ids):
        if ids is None:
            return '', ()
        if not ids:
            return ' WHERE 1=0', ()
        return f" WHERE r.user_id IN ({','.join([self.ph] * len(ids))})", tuple(ids)

    def ledger(self, ids):
        """All ledger titles in a scope, joined with any cached metadata.

        :param ids: Recipient profile IDs, or ``None`` for the whole installation.
        :return: List of ``LedgerTitle`` with timezone-aware dates.
        """
        restriction, params = self._restriction(ids)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT r.tmdb_id, r.media_type, r.user_id, r.requested_at, r.watched_at, m.title,
                m.poster_path, m.release_date, m.genre_ids, m.rating, m.origin_country FROM recap_titles r
                LEFT JOIN metadata m ON m.media_id=r.tmdb_id AND m.media_type=r.media_type''' + restriction, params)
            rows = cursor.fetchall()
        return [LedgerTitle(str(row[0]), row[1], row[2], utc_datetime(row[3]), utc_datetime(row[4]), *row[5:9],
                            float(row[9]) if row[9] is not None else None, row[10]) for row in rows]

    def summary(self, user, env, include_posters=False, now=None):
        now = now or datetime.now(timezone.utc)
        scope, ids = self._scope(user, env)
        rows = self.ledger(ids)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT reminder_mode FROM recap_preferences WHERE user_id={self.ph}', (int(user['id']),))
            row = cursor.fetchone()
            mode = row[0] if row else 'enabled'
        posters = []
        if include_posters:
            ranked = sorted((row for row in rows if row.poster_path),
                            key=lambda row: (row.rating or 0, row.requested_at, row.tmdb_id), reverse=True)
            posters = [{'tmdb_id': row.tmdb_id, 'media_type': row.media_type, 'poster_path': row.poster_path,
                        'title': row.title, 'rating': row.rating} for row in ranked[:4]]
        tracking = watch_provider(env) is not None
        badges, next_badge, streak = build_badges(rows, scope, now, tracking)
        total = len(rows)
        watched = sum(row.watched_at is not None for row in rows)
        first = min((row.requested_at for row in rows), default=None)
        return {'scope': scope, 'has_linked_profiles': ids is None or bool(ids),
                'total': total, 'movies': sum(row.media_type == 'movie' for row in rows),
                'tv': sum(row.media_type == 'tv' for row in rows),
                'first_requested_at': first.isoformat() if first else None,
                'watch_tracking': tracking, 'watched': watched if tracking else None,
                'hit_rate': round(watched * 100 / total) if tracking and total else None, 'streak': streak,
                'badges': badges, 'next_badge': next_badge, 'posters': posters,
                'preferences': {'reminder_mode': mode}, 'can_support': user.get('role') == 'admin'}

    def pending_watch(self, ids):
        """Ledger titles in a scope not yet seen as watched, as ``(media_type, tmdb_id, user_id, requested_at)``."""
        restriction, params = self._restriction(ids)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT r.media_type, r.tmdb_id, r.user_id, r.requested_at FROM recap_titles r' + restriction +
                           (' AND ' if restriction else ' WHERE ') + 'r.watched_at IS NULL', params)
            return [(row[0], str(row[1]), row[2], utc_datetime(row[3])) for row in cursor.fetchall()]

    def mark_watched(self, matches):
        """Record first observed plays; an existing ``watched_at`` is never overwritten.

        :param matches: Iterable of ``(watched_at, media_type, tmdb_id)``.
        :return: Number of titles newly marked as watched.
        """
        values = [(date.astimezone(timezone.utc).replace(tzinfo=None), media_type, str(tmdb_id))
                  for date, media_type, tmdb_id in matches]
        if not values:
            return 0
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            updated = 0
            for value in values:
                cursor.execute(f'''UPDATE recap_titles SET watched_at={self.ph}
                    WHERE media_type={self.ph} AND tmdb_id={self.ph} AND watched_at IS NULL''', value)
                updated += max(cursor.rowcount, 0)
            conn.commit()
        return updated

    def _ensure_state(self, cursor, user_id, scope):
        if self.db.db_type in ('mysql', 'mariadb'):
            # A duplicate INSERT IGNORE takes a shared InnoDB lock. Two tabs
            # upgrading it to an UPDATE can deadlock; this no-op upsert takes
            # an exclusive lock on the preference row before reading state.
            cursor.execute('''INSERT INTO recap_preferences (user_id) VALUES (%s)
                ON DUPLICATE KEY UPDATE user_id=VALUES(user_id)''', (user_id,))
        else:
            cursor.execute(insert_ignore(self.db.db_type, 'recap_preferences', 'user_id', f'VALUES ({self.ph})'), (user_id,))
        cursor.execute(insert_ignore(self.db.db_type, 'recap_prompts', 'user_id, scope', f'VALUES ({self.ph},{self.ph})'), (user_id, scope))

    def claim_prompt(self, user, env, now=None):
        """A conditional version update grants each presentation to one caller only."""
        now = now or datetime.now(timezone.utc)
        summary = self.summary(user, env, now=now)
        first = utc_datetime(summary['first_requested_at'])
        milestone = max((n for n in SUPPORT_MILESTONES if n <= summary['total']), default=0)
        if user.get('role') != 'admin' or not milestone or not first or now < first + timedelta(days=14):
            return None
        user_id, scope = int(user['id']), summary['scope']
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            self._ensure_state(cursor, user_id, scope)
            cursor.execute(f'''SELECT highest_milestone,last_shown_at,snoozed_until,snoozed_milestone,version
                FROM recap_prompts WHERE user_id={self.ph} AND scope={self.ph}''', (user_id, scope))
            highest, last, snooze, snoozed_milestone, version = cursor.fetchone()
            last, snooze = utc_datetime(last), utc_datetime(snooze)
            due = (now >= snooze if snooze else
                   last is None or (milestone > highest and now >= last + timedelta(days=90))
                   or now >= last + timedelta(days=180))
            if not due:
                conn.commit()
                return None
            # Linked profiles may have changed while a personal prompt was snoozed.
            shown_milestone = min(snoozed_milestone, milestone) if snooze else milestone
            cursor.execute(f'''UPDATE recap_prompts SET highest_milestone={self.ph}, last_shown_at={self.ph},
                snoozed_until=NULL,snoozed_milestone=0,version=version+1
                WHERE user_id={self.ph} AND scope={self.ph} AND version={self.ph}
                AND EXISTS (SELECT 1 FROM recap_preferences WHERE user_id={self.ph} AND reminder_mode='enabled')''',
                (max(highest, shown_milestone), now.replace(tzinfo=None), user_id, scope, version, user_id))
            claimed = cursor.rowcount == 1
            conn.commit()
        return {'milestone': shown_milestone, 'scope': scope, 'version': version + 1} if claimed else None

    def update_preferences(self, user, env, action, now=None):
        now = now or datetime.now(timezone.utc)
        user_id = int(user['id'])
        scope, _ids = self._scope(user, env)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            self._ensure_state(cursor, user_id, scope)
            if action in ('enable', 'disable', 'supported'):
                mode = {'enable': 'enabled', 'disable': 'disabled', 'supported': 'supported'}[action]
                cursor.execute(f'UPDATE recap_preferences SET reminder_mode={self.ph} WHERE user_id={self.ph}', (mode, user_id))
            elif action == 'remind_later':
                cursor.execute(f'''UPDATE recap_prompts SET snoozed_until={self.ph},
                    snoozed_milestone=highest_milestone,version=version+1
                    WHERE user_id={self.ph} AND scope={self.ph} AND last_shown_at IS NOT NULL''',
                    ((now + timedelta(days=30)).replace(tzinfo=None), user_id, scope))
            elif action == 'dismiss':
                cursor.execute(f'''UPDATE recap_prompts SET snoozed_until=NULL,snoozed_milestone=0,version=version+1
                    WHERE user_id={self.ph} AND scope={self.ph}''', (user_id, scope))
            conn.commit()
        return self.summary(user, env, now=now)['preferences']
