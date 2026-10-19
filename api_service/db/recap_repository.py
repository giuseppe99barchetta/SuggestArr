"""Durable recap progress and per-administrator reminder preferences.

The ledger deliberately has no foreign keys to disposable request history or media
users. Only successful, canonical SuggestArr requests can seed it.
"""
from datetime import datetime, timedelta, timezone


TITLE_BADGES = ((10, 'First discoveries'), (100, 'Century club'),
                (500, 'Discovery enthusiast'), (1000, 'A thousand discoveries'),
                (5000, 'Cinema explorer'), (10000, 'Discovery legend'))
SUPPORT_MILESTONES = (100, 500, 1000, 5000, 10000)


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


def initialize_recap_schema(db):
    """Additive and repeatable on SQLite, PostgreSQL and MySQL/MariaDB."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS recap_titles (
            media_type VARCHAR(16) NOT NULL, tmdb_id VARCHAR(64) NOT NULL,
            user_id VARCHAR(191), requested_at TIMESTAMP NOT NULL,
            PRIMARY KEY (media_type, tmdb_id))''')
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


def badge_progress(total, first_requested_at, now):
    badges = [{'id': f'titles_{threshold}', 'label': label, 'threshold': threshold,
               'unlocked': total >= threshold, 'kind': 'titles'}
              for threshold, label in TITLE_BADGES]
    first = utc_datetime(first_requested_at)
    badges.append({'id': 'one_year', 'label': 'One year of discoveries', 'threshold': 365,
                   'unlocked': bool(first and now >= first + timedelta(days=365)), 'kind': 'days'})
    next_badge = next((badge for badge in badges if badge['kind'] == 'titles' and not badge['unlocked']), None)
    return badges, next_badge


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

    def summary(self, user, env, include_posters=False, now=None):
        now = now or datetime.now(timezone.utc)
        scope, ids = self._scope(user, env)
        restriction, params = self._restriction(ids)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT COUNT(*), COALESCE(SUM(CASE WHEN r.media_type='movie' THEN 1 ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN r.media_type='tv' THEN 1 ELSE 0 END),0), MIN(r.requested_at)
                FROM recap_titles r''' + restriction, params)
            total, movies, tv, first = cursor.fetchone()
            # MySQL returns SUM(integer-expression) as Decimal; keep the API numeric.
            total, movies, tv = int(total), int(movies), int(tv)
            cursor.execute(f'SELECT reminder_mode FROM recap_preferences WHERE user_id={self.ph}', (int(user['id']),))
            row = cursor.fetchone()
            mode = row[0] if row else 'enabled'
            posters = []
            if include_posters:
                where = restriction + (' AND ' if restriction else ' WHERE ')
                cursor.execute('''SELECT r.tmdb_id, r.media_type, m.poster_path, m.title, m.rating FROM recap_titles r
                    JOIN metadata m ON m.media_id=r.tmdb_id AND m.media_type=r.media_type''' + where +
                    "m.poster_path IS NOT NULL AND m.poster_path<>'' "
                    "ORDER BY COALESCE(m.rating,0) DESC, r.requested_at DESC, r.tmdb_id DESC LIMIT 4", params)
                posters = [{'tmdb_id': row[0], 'media_type': row[1], 'poster_path': row[2],
                            'title': row[3], 'rating': float(row[4]) if row[4] is not None else None}
                           for row in cursor.fetchall()]
        badges, next_badge = badge_progress(total, first, now)
        return {'scope': scope, 'has_linked_profiles': ids is None or bool(ids),
                'total': total, 'movies': movies, 'tv': tv,
                'first_requested_at': utc_datetime(first).isoformat() if first else None,
                'badges': badges, 'next_badge': next_badge, 'posters': posters,
                'preferences': {'reminder_mode': mode}, 'can_support': user.get('role') == 'admin'}

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
