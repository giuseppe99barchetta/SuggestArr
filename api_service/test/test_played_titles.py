"""PlayedTitles turns raw media-server plays into one row per title for the Ratings page."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from api_service.services.year_recap import PlayedTitles

ENV = {'JELLYFIN_API_URL': 'http://jf.local:8096', 'JELLYFIN_TOKEN': 'secret'}


def _entry(kind, tmdb, title, day, year=None):
    return {'account': 'u1', 'kind': kind, 'id': f'{kind}{day}', 'series_id': 's1', 'tmdb': tmdb,
            'title': title, 'year': year, 'date': datetime(2026, 1, day, tzinfo=timezone.utc)}


def test_episodes_collapse_to_their_show_and_keep_the_latest_play():
    entries = [
        _entry('episode', '10', 'Bluey', 3),
        _entry('movie', '20', 'Arrival', 2, 2016),
        _entry('episode', '10', 'Bluey', 5),
        _entry('movie', None, 'Unmatched', 4),
    ]
    with patch.object(PlayedTitles, '_scan', AsyncMock(return_value=(entries, True))), \
         patch.object(PlayedTitles, '_resolve', AsyncMock()):
        titles, truncated = asyncio.run(PlayedTitles().titles('jellyfin', 'u1', ENV))
    assert truncated is True
    assert [(t['media_type'], t['tmdb_id'], t['title'], t['year']) for t in titles] == [
        ('tv', '10', 'Bluey', None), ('movie', '20', 'Arrival', 2016),
    ]
    assert titles[0]['watched_at'] == datetime(2026, 1, 5)


def test_unconfigured_server_returns_none():
    assert asyncio.run(PlayedTitles().titles('jellyfin', 'u1', {})) is None


def test_emby_reads_the_jellyfin_configuration():
    with patch.object(PlayedTitles, '_scan', AsyncMock(return_value=([_entry('movie', '20', 'Arrival', 2)], False))), \
         patch.object(PlayedTitles, '_resolve', AsyncMock()):
        titles, _ = asyncio.run(PlayedTitles().titles('emby', 'u1', ENV))
    assert [t['tmdb_id'] for t in titles] == ['20']


def test_transient_resolve_failure_keeps_later_plays_for_the_next_sync():
    entries = [
        _entry('movie', '20', 'Arrival', 2),
        _entry('movie', None, 'Dune', 4),
        _entry('movie', '30', 'Heat', 6),
    ]
    failure = AsyncMock(side_effect=TimeoutError())
    with patch.object(PlayedTitles, '_scan', AsyncMock(return_value=(entries, False))), \
         patch.object(PlayedTitles, '_json', failure):
        titles, truncated = asyncio.run(PlayedTitles().titles('jellyfin', 'u1', ENV))
    assert truncated is True
    assert [t['tmdb_id'] for t in titles] == ['20']
