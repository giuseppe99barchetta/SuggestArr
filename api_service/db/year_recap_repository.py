"""Annual aggregates of recorded discoveries; never reconstruct deleted history."""
import json
from collections import Counter
from datetime import datetime, timezone

from api_service.db.recap_repository import RecapRepository, utc_datetime
from api_service.services.filter_normalization import TMDB_GENRE_MAP

GENRES = {value: key for key, value in TMDB_GENRE_MAP.items()}
GENRES.update({10759: 'Action & Adventure', 10762: 'Kids', 10765: 'Sci-Fi & Fantasy',
               10766: 'Soap', 10767: 'Talk', 10768: 'War & Politics', 10764: 'Reality'})
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def genre_distribution(rows):
    counts = Counter()
    covered = 0
    for row in rows:
        try:
            ids = json.loads(row[7]) if isinstance(row[7], str) else row[7]
            labels = {GENRES[int(value)] for value in ids or [] if str(value).isdigit() and int(value) in GENRES}
        except (TypeError, ValueError):
            labels = set()
        if labels:
            covered += 1
            counts.update(labels)
    ranked = counts.most_common()
    if len(ranked) > 4:
        ranked = ranked[:3] + [('Other', sum(count for _, count in ranked[3:]))]
    total = sum(count for _, count in ranked)
    # Largest remainder rounding keeps the displayed breakdown at exactly 100%.
    shares = [count * 100 / total for _, count in ranked] if total else []
    rounded = [int(value) for value in shares]
    for index in sorted(range(len(shares)), key=lambda i: (shares[i] - rounded[i], -i), reverse=True)[:100 - sum(rounded)]:
        rounded[index] += 1
    return [{'label': label, 'percent': rounded[i]} for i, (label, _) in enumerate(ranked)], covered


class YearRecapRepository(RecapRepository):
    def summary(self, user, env, year, scope='personal', now=None):
        now = now or datetime.now(timezone.utc)
        can_server = user.get('role') == 'admin' and env.get('REQUEST_VISIBILITY') != 'own_all'
        if scope == 'server' and not can_server:
            raise PermissionError('Server recap is unavailable for this account')
        profiles = self.db.get_user_media_profiles(int(user['id'])) if scope == 'personal' else []
        ids = None if scope == 'server' else sorted({str(p['external_user_id']) for p in profiles
                                                   if p.get('provider') in ('plex', 'jellyfin', 'emby')})
        restriction, params = self._restriction(ids)
        start = datetime(year, 1, 1)
        end = min(datetime(year + 1, 1, 1, tzinfo=timezone.utc), now).replace(tzinfo=None)
        # Legacy SQLite timestamps contain both spaces and ISO T separators.
        date_expr = 'julianday(r.requested_at)' if self.db.db_type == 'sqlite' else 'r.requested_at'
        date_param = 'julianday(?)' if self.db.db_type == 'sqlite' else self.ph
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT r.requested_at FROM recap_titles r' + restriction, params)
            recorded_dates = [utc_datetime(row[0]) for row in cursor.fetchall()]
            cursor.execute('''SELECT r.tmdb_id,r.media_type,r.user_id,r.requested_at,
                m.title,m.poster_path,m.release_date,m.genre_ids FROM recap_titles r
                LEFT JOIN metadata m ON m.media_id=r.tmdb_id AND m.media_type=r.media_type''' +
                restriction + (' AND ' if restriction else ' WHERE ') +
                f'{date_expr}>={date_param} AND {date_expr}<{date_param} ORDER BY {date_expr} DESC,r.tmdb_id DESC',
                params + (start, end))
            rows = cursor.fetchall()
        monthly = [{'month': month, 'label': datetime(year, i + 1, 1).strftime('%B'), 'requests': 0, 'minutes': None}
                   for i, month in enumerate(MONTHS)]
        for row in rows:
            monthly[utc_datetime(row[3]).month - 1]['requests'] += 1
        genres, covered = genre_distribution(rows)
        titles = [{'title': row[4], 'poster_path': row[5],
                   'detail': ('Movie' if row[1] == 'movie' else 'TV series') +
                   (f' · {str(row[6])[:4]}' if row[6] else '')}
                  for row in rows if row[4]][:4]
        provider = (env.get('SELECTED_SERVICE') or '').lower()
        return {'year': year, 'isDemo': False, 'scope': scope, 'allowedScopes': ['personal', 'server'] if can_server else ['personal'],
                'availableYears': sorted({now.year} | {date.year for date in recorded_dates if date <= now}, reverse=True),
                'hasLinkedProfiles': ids is None or bool(ids), 'isYearToDate': year == now.year,
                'generatedAt': now.isoformat(), 'firstRecordedAt': min(recorded_dates).isoformat() if recorded_dates else None,
                'provider': provider if provider in ('plex', 'jellyfin') else None,
                'providerLabel': {'plex': 'Plex', 'jellyfin': 'Jellyfin'}.get(provider, 'SuggestArr'),
                'activeUsers': None, 'requested': {'total': len(rows), 'movies': sum(row[1] == 'movie' for row in rows),
                                                  'series': sum(row[1] == 'tv' for row in rows)},
                'watched': None, 'watchMinutes': None, 'watchStatus': 'not_loaded',
                'watchNote': 'Watch activity has not been loaded. Watch time requires a full playback-session history.',
                'monthly': monthly, 'peakMonth': max(monthly, key=lambda month: month['requests']),
                'genres': genres, 'genreSource': 'requested', 'genreCoverage': covered, 'titles': titles}
