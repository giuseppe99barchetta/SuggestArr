"""Pure badge, streak and unlock-date rules over recap ledger rows. No I/O.

Every unlock date is derived from the durable ledger itself, so badges keep the
date they were earned without a separate achievements table.
"""
import json
from collections import namedtuple
from datetime import timedelta

from api_service.services.filter_normalization import TMDB_GENRE_MAP

GENRES = {value: key for key, value in TMDB_GENRE_MAP.items()}
GENRES.update({10759: 'Action & Adventure', 10762: 'Kids', 10765: 'Sci-Fi & Fantasy',
               10766: 'Soap', 10767: 'Talk', 10768: 'War & Politics', 10764: 'Reality'})

TITLE_LABELS = {10: 'First discoveries', 25: 'Curious mind', 50: 'Half-century', 100: 'Century club',
                250: 'Film buff', 500: 'Discovery enthusiast', 1000: 'A thousand discoveries',
                2500: 'Marathon curator', 5000: 'Cinema explorer', 10000: 'Discovery legend'}
# A single profile rarely reaches the installation-wide tiers, so it gets a denser ladder.
TITLE_THRESHOLDS = {'personal': (10, 25, 50, 100, 250, 500, 1000),
                    'installation': (10, 50, 100, 250, 500, 1000, 2500, 5000, 10000)}
WATCH_BADGES = ((1, 'First pick watched'), (10, 'Ten picks enjoyed'), (50, 'Trusted taste'), (250, 'Perfect match'))
STREAK_BADGES = ((3, 'Steady viewer'), (6, 'Half-year habit'), (12, 'Year-round viewer'))
YEAR_BADGES = ((1, 'one_year', 'One year of discoveries'), (2, 'years_2', 'Two years of discoveries'),
               (3, 'years_3', 'Three years of discoveries'), (5, 'years_5', 'Five years of discoveries'))
VARIETY_BADGES = (('genres_5', 'Genre hopper', 5, 'genres', 'Request titles from 5 genres'),
                  ('genres_10', 'Eclectic taste', 10, 'genres', 'Request titles from 10 genres'),
                  ('decades_5', 'Time traveller', 5, 'decades', 'Request titles from 5 release decades'),
                  ('countries_5', 'World tour', 5, 'countries', 'Request titles from 5 countries'),
                  ('balanced', 'Best of both worlds', 10, 'balanced', 'Request 10 movies and 10 TV series'))

LedgerTitle = namedtuple('LedgerTitle', 'tmdb_id media_type user_id requested_at watched_at title poster_path '
                                        'release_date genre_ids rating origin_country')


def genre_labels(raw):
    """Return the set of known genre labels from a stored TMDb ``genre_ids`` value.

    :param raw: JSON string or list of TMDb genre IDs, possibly malformed or empty.
    :return: Set of genre labels; unknown IDs and malformed values are ignored.
    """
    try:
        ids = json.loads(raw) if isinstance(raw, str) else raw
        return {GENRES[int(value)] for value in ids or [] if str(value).isdigit() and int(value) in GENRES}
    except (TypeError, ValueError):
        return set()


def _decades(row):
    year = str(row.release_date or '')[:4]
    return {int(year) // 10} if len(year) == 4 and year.isdigit() else set()


def _countries(row):
    raw = row.origin_country or ''
    try:
        values = json.loads(raw) if raw.startswith('[') else raw.split(',')
    except (AttributeError, ValueError):
        values = []
    return {str(value).strip().upper() for value in values if str(value).strip()}


VARIETY_KEYS = {'genres': lambda row: genre_labels(row.genre_ids), 'decades': _decades, 'countries': _countries}


def month_key(date):
    """Return a sortable month index so consecutive months differ by exactly one."""
    return date.year * 12 + date.month - 1


def month_streaks(dates, now):
    """Measure consecutive calendar months containing at least one date.

    :param dates: Timezone-aware datetimes in any order.
    :param now: Reference instant; a streak is still current if its last month is this or the previous one.
    :return: Tuple ``(current, longest, reached)`` where ``reached`` maps a run length to the first
        date of the month that completed it for the first time.
    """
    firsts = {}
    for date in sorted(dates):
        firsts.setdefault(month_key(date), date)
    current = longest = run = 0
    previous = None
    reached = {}
    for key in sorted(firsts):
        run = run + 1 if previous is not None and key == previous + 1 else 1
        previous = key
        longest = max(longest, run)
        reached.setdefault(run, firsts[key])
    if previous is not None and month_key(now) - previous <= 1:
        current = run
    return current, longest, reached


def _iso(date):
    return date.isoformat() if date else None


def _badge(badge_id, kind, label, threshold, progress, unlocked_at, description, **extra):
    return {'id': badge_id, 'kind': kind, 'label': label, 'threshold': threshold,
            'progress': min(progress, threshold), 'unlocked': unlocked_at is not None,
            'unlocked_at': _iso(unlocked_at), 'description': description, **extra}


def _nth(dates, n):
    return dates[n - 1] if len(dates) >= n else None


def _first_reaching(rows, keys, n):
    """Date of the request that brought the distinct ``keys`` count to ``n``, plus the final count."""
    seen = set()
    reached = None
    for row in rows:
        seen |= keys(row)
        if reached is None and len(seen) >= n:
            reached = row.requested_at
    return reached, len(seen)


def _balanced(rows, n):
    counts = {'movie': 0, 'tv': 0}
    reached = None
    for row in rows:
        counts[row.media_type] = counts.get(row.media_type, 0) + 1
        if reached is None and counts['movie'] >= n and counts['tv'] >= n:
            reached = row.requested_at
    return reached, min(counts['movie'], counts['tv'])


def build_badges(rows, scope, now, watch_tracking):
    """Evaluate every badge for one recap scope.

    :param rows: ``LedgerTitle`` rows with timezone-aware ``requested_at``/``watched_at``.
    :param scope: ``'personal'`` or ``'installation'``; selects the title ladder.
    :param now: Reference instant for anniversaries and streaks.
    :param watch_tracking: Whether a media server can report watched suggestions. Watch-based
        badges are omitted otherwise, rather than shown as permanently locked.
    :return: Tuple ``(badges, next_badge, streak)``; ``streak`` is ``None`` without watch tracking.
    """
    rows = sorted(rows, key=lambda row: row.requested_at)
    requested = [row.requested_at for row in rows]
    watched = sorted(row.watched_at for row in rows if row.watched_at)
    badges = [_badge(f'titles_{n}', 'titles', TITLE_LABELS[n], n, len(rows), _nth(requested, n),
                     f'Request {n:,} titles') for n in TITLE_THRESHOLDS[scope]]
    streak = None
    if watch_tracking:
        badges += [_badge(f'watched_{n}', 'watched', label, n, len(watched), _nth(watched, n),
                          'Watch a title SuggestArr requested' if n == 1 else f'Watch {n} titles SuggestArr requested')
                   for n, label in WATCH_BADGES]
    for badge_id, label, n, key, description in VARIETY_BADGES:
        reached, progress = _balanced(rows, n) if key == 'balanced' else _first_reaching(rows, VARIETY_KEYS[key], n)
        badges.append(_badge(badge_id, 'variety', label, n, progress, reached, description))
    if watch_tracking:
        current, longest, reached = month_streaks(watched, now)
        streak = {'current': current, 'longest': longest}
        badges += [_badge(f'streak_{n}', 'streak', label, n, longest, reached.get(n),
                          f'Watch a suggested title in {n} consecutive months') for n, label in STREAK_BADGES]
    first = requested[0] if requested else None
    for years, badge_id, label in YEAR_BADGES:
        due = first + timedelta(days=365 * years) if first else None
        elapsed = (now - first).days if first else 0
        badges.append(_badge(badge_id, 'days', label, 365 * years, max(0, elapsed), due if due and now >= due else None,
                             'One year since your first recorded request' if years == 1
                             else f'{years} years since your first recorded request', unlocks_at=_iso(due)))
    next_badge = next((badge for badge in badges if badge['kind'] == 'titles' and not badge['unlocked']), None)
    return badges, next_badge, streak
