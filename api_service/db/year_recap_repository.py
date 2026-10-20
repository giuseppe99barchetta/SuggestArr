"""Annual aggregates of recorded discoveries; never reconstruct deleted history."""
from collections import Counter
from datetime import datetime, timezone

from api_service.db.recap_repository import RecapRepository, watch_provider
from api_service.services.recap_badges import build_badges, genre_labels, month_key, month_streaks

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def genre_distribution(genre_values):
    """Share of genre tags among requested titles, rounded to exactly 100%.

    :param genre_values: Stored ``genre_ids`` values, one per requested title.
    :return: Tuple ``(genres, covered)``: up to four ``{label, percent}`` entries (the fourth may be
        ``Other``) and the number of titles that had genre metadata.
    """
    counts = Counter()
    covered = 0
    for raw in genre_values:
        labels = genre_labels(raw)
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


def longest_run_in_year(dates, year):
    """Longest run of consecutive months within ``year`` containing at least one date."""
    in_year = [date for date in dates if date.year == year]
    return month_streaks(in_year, datetime(year, 12, 31, tzinfo=timezone.utc))[1]


class YearRecapRepository(RecapRepository):
    def summary(self, user, env, year, scope='personal', now=None):
        now = now or datetime.now(timezone.utc)
        can_server = user.get('role') == 'admin' and env.get('REQUEST_VISIBILITY') != 'own_all'
        if scope == 'server' and not can_server:
            raise PermissionError('Server recap is unavailable for this account')
        profiles = self.db.get_user_media_profiles(int(user['id'])) if scope == 'personal' else []
        ids = None if scope == 'server' else sorted({str(p['external_user_id']) for p in profiles
                                                   if p.get('provider') in ('plex', 'jellyfin', 'emby')})
        ledger = self.ledger(ids)
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = min(datetime(year + 1, 1, 1, tzinfo=timezone.utc), now)
        rows = sorted((row for row in ledger if start <= row.requested_at < end),
                      key=lambda row: (row.requested_at, row.tmdb_id), reverse=True)
        monthly = [{'month': month, 'label': datetime(year, i + 1, 1).strftime('%B'), 'requests': 0, 'minutes': None}
                   for i, month in enumerate(MONTHS)]
        for row in rows:
            monthly[row.requested_at.month - 1]['requests'] += 1
        genres, covered = genre_distribution(row.genre_ids for row in rows)
        # Standout titles: best rated first, so January recaps are not just the last few requests.
        ranked = sorted((row for row in rows if row.title), key=lambda row: row.rating or 0, reverse=True)
        titles = [{'title': row.title, 'poster_path': row.poster_path,
                   'detail': ('Movie' if row.media_type == 'movie' else 'TV series') +
                   (f' · {str(row.release_date)[:4]}' if row.release_date else '') +
                   (' · Watched' if row.watched_at else '')}
                  for row in ranked][:4]
        tracking = watch_provider(env) is not None
        watched_rows = [row for row in rows if row.watched_at]
        hit_rate = ({'watched': len(watched_rows), 'total': len(rows),
                     'percent': round(len(watched_rows) * 100 / len(rows)),
                     'movies': sum(row.media_type == 'movie' for row in watched_rows),
                     'series': sum(row.media_type == 'tv' for row in watched_rows)}
                    if tracking and rows else None)
        watch_dates = [row.watched_at for row in ledger if row.watched_at and row.watched_at < end]
        badges, _next, _streak = build_badges(ledger, 'installation' if scope == 'server' else 'personal', now, tracking)
        unlocked = sorted((badge for badge in badges if badge['unlocked_at']
                           and start <= datetime.fromisoformat(badge['unlocked_at']) < end),
                          key=lambda badge: badge['unlocked_at'])
        provider = (env.get('SELECTED_SERVICE') or '').lower()
        recorded = [row.requested_at for row in ledger if row.requested_at <= now]
        return {'year': year, 'isDemo': False, 'scope': scope, 'allowedScopes': ['personal', 'server'] if can_server else ['personal'],
                'availableYears': sorted({now.year} | {date.year for date in recorded}, reverse=True),
                'hasLinkedProfiles': ids is None or bool(ids), 'isYearToDate': year == now.year,
                'generatedAt': now.isoformat(), 'firstRecordedAt': min(recorded).isoformat() if recorded else None,
                'provider': provider if provider in ('plex', 'jellyfin') else None,
                'providerLabel': {'plex': 'Plex', 'jellyfin': 'Jellyfin'}.get(provider, 'SuggestArr'),
                'activeUsers': None, 'requested': {'total': len(rows), 'movies': sum(row.media_type == 'movie' for row in rows),
                                                  'series': sum(row.media_type == 'tv' for row in rows)},
                'watched': None, 'watchMinutes': None, 'watchStatus': 'not_loaded',
                'watchNote': 'Watch activity has not been loaded. Watch time requires a full playback-session history.',
                'monthly': monthly, 'peakMonth': max(monthly, key=lambda month: month['requests']),
                'genres': genres, 'genreSource': 'requested', 'genreCoverage': covered, 'titles': titles,
                'hitRate': hit_rate,
                'streak': {'longest': longest_run_in_year(watch_dates, year),
                           'months': len({month_key(date) for date in watch_dates if date.year == year})} if tracking else None,
                'badgesUnlocked': [{'id': badge['id'], 'kind': badge['kind'], 'label': badge['label'],
                                    'unlockedAt': badge['unlocked_at']} for badge in unlocked]}
