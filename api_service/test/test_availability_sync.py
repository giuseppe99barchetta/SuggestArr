"""Tests for following requested titles through Seer (requested -> processing -> available)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.db import database_manager as dm_mod
from api_service.db.database_manager import DatabaseManager
from api_service.jobs import availability_sync
from api_service.jobs.availability_sync import external_media_url, plan_availability_changes
from api_service.services.request_sources import DISCOVER_SOURCE
from api_service.services.seer.seer_client import SeerClient, media_play_url

MOVIE, SHOW, OLD = ('movie', '1'), ('tv', '2'), ('movie', '3')


def st(status, url=None):
    return {'status': status, 'url': url}


def _page(results, total=None):
    return {'pageInfo': {'results': total if total is not None else len(results)}, 'results': results}


def _seer(pages):
    client = SeerClient('http://seer.test', 'key')
    client._fetch_available_media_page = AsyncMock(side_effect=pages)
    return client


def test_statuses_take_the_further_of_regular_and_4k_and_skip_unknown():
    client = _seer([_page([
        {'mediaType': 'movie', 'tmdbId': 1, 'status': 3, 'status4k': 5},
        {'mediaType': 'tv', 'tmdbId': 2, 'status': 4, 'status4k': 1},
        {'mediaType': 'tv', 'tmdbId': 4, 'status': 2},
        {'mediaType': 'movie', 'tmdbId': 5, 'status': 1},
        {'mediaType': 'person', 'tmdbId': 6, 'status': 5},
    ])])
    assert asyncio.run(client.get_media_statuses()) == {
        ('movie', '1'): st('available'), ('tv', '2'): st('partial'), ('tv', '4'): st('pending'),
    }


def test_play_links_move_to_the_external_media_server_address():
    lan = 'http://jellyfin:8096/web/index.html#!/details?id=abc'
    assert external_media_url(lan, 'https://media.example.com/') == 'https://media.example.com/web/index.html#!/details?id=abc'
    assert external_media_url('http://jf/jellyfin/web/#!/x', 'https://m.example') == 'https://m.example/web/#!/x'
    assert external_media_url('https://app.plex.tv/desktop#!/x', 'https://m.example') == 'https://app.plex.tv/desktop#!/x'
    assert external_media_url(lan, '') == lan
    assert external_media_url(None, 'https://m.example') is None


def test_play_links_come_from_the_available_copy_and_only_web_links_pass():
    lan = 'http://192.168.1.20:8096/web/index.html#!/details?id=abc'
    assert media_play_url({'status': 5, 'mediaUrl': lan}) == lan
    assert media_play_url({'status': 5, 'plexUrl': 'https://app.plex.tv/desktop#!/x'}) == 'https://app.plex.tv/desktop#!/x'
    assert media_play_url({'status': 3, 'mediaUrl': lan, 'status4k': 5, 'mediaUrl4k': 'http://jf.local/4k'}) == 'http://jf.local/4k'
    assert media_play_url({'status': 3, 'mediaUrl': lan}) is None
    assert media_play_url({'status': 5, 'mediaUrl': 'javascript:alert(1)'}) is None
    assert media_play_url({'status': 5, 'mediaUrl': 'http://x/' + 'a' * 600}) is None


def test_a_partial_read_reports_nothing_rather_than_titles_leaving_seer():
    pages = [_page([{'mediaType': 'movie', 'tmdbId': 1, 'status': 5}], total=150), None]
    assert asyncio.run(_seer(pages).get_media_statuses()) is None
    assert asyncio.run(_seer([None]).get_media_statuses()) is None


def test_available_ids_still_read_every_page():
    pages = [_page([{'mediaType': 'movie', 'tmdbId': 1, 'status': 5}], total=150),
             _page([{'mediaType': 'tv', 'tmdbId': 2, 'status4k': 4}])]
    assert asyncio.run(_seer(pages).get_available_tmdb_ids()) == {'movie': {'1'}, 'tv': {'2'}}


def test_first_sync_only_records_the_current_state():
    changes, available = plan_availability_changes({MOVIE, SHOW}, {}, {MOVIE: st('available', 'http://jf/1')})
    assert changes == {MOVIE: st('available', 'http://jf/1'), SHOW: st('requested')}
    assert available == []


def test_later_syncs_store_changes_and_announce_titles_that_became_available():
    known = {MOVIE: st('processing'), SHOW: st('requested'), OLD: st('available', 'http://jf/3')}
    statuses = {MOVIE: st('available'), SHOW: st('available'), OLD: st('available', 'http://jf/3')}
    changes, available = plan_availability_changes({MOVIE, SHOW, OLD}, known, statuses)
    assert changes == {MOVIE: st('available'), SHOW: st('available')}
    assert sorted(available) == sorted([MOVIE, SHOW])


def test_titles_no_longer_requested_are_forgotten_and_partial_is_not_announced():
    changes, available = plan_availability_changes({MOVIE}, {MOVIE: st('processing'), OLD: st('available')}, {MOVIE: st('partial')})
    assert changes == {MOVIE: st('partial'), OLD: None}
    assert available == []


def test_a_new_play_link_is_stored_without_announcing_again():
    changes, available = plan_availability_changes({MOVIE}, {MOVIE: st('available')}, {MOVIE: st('available', 'http://jf/1')})
    assert changes == {MOVIE: st('available', 'http://jf/1')}
    assert available == []


def test_sync_stores_statuses_shows_them_on_requests_and_fires_the_webhook(tmp_path):
    with (
        patch.object(dm_mod, "DB_PATH", str(tmp_path / "availability.db")),
        patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}),
    ):
        DatabaseManager._instance = None
        db = DatabaseManager()
        db.save_metadata({"id": "1", "title": "Dune"}, "movie")
        db.save_request("movie", "1", DISCOVER_SOURCE)
        db.enqueue_webhook_event = MagicMock()
        seer = MagicMock(get_media_statuses=AsyncMock(side_effect=[{}, {MOVIE: st('available', 'http://jf.local/1')}]))
        seer.__aenter__ = AsyncMock(return_value=seer)
        seer.__aexit__ = AsyncMock(return_value=False)
        env = {'SEER_API_URL': 'http://seer.test', 'SEER_TOKEN': 'key'}
        with patch.object(availability_sync.ConfigService, 'get_runtime_config', return_value=env), \
                patch.object(availability_sync, 'SeerClient', return_value=seer), \
                patch.object(availability_sync, 'DatabaseManager', return_value=db):
            first = asyncio.run(availability_sync.sync_availability())
            second = asyncio.run(availability_sync.sync_availability())

        request = db.get_all_requests_grouped_by_source()["data"][0]["requests"][0]

    DatabaseManager._instance = None
    assert first == {'status': 'ok', 'changed': 1, 'available': 0}
    assert second == {'status': 'ok', 'changed': 1, 'available': 1}
    assert request["availability"] == 'available'
    assert request["media_url"] == 'http://jf.local/1'
    db.enqueue_webhook_event.assert_called_once_with('request.available', {'tmdb_id': '1', 'media_type': 'movie'})


def test_sync_without_seer_settings_does_nothing():
    with patch.object(availability_sync.ConfigService, 'get_runtime_config', return_value={}):
        assert asyncio.run(availability_sync.sync_availability())['status'] == 'not_configured'


def test_progress_filter_matches_the_badge_precedence(tmp_path):
    from datetime import datetime, timezone
    from api_service.db.recap_repository import RecapRepository
    with (
        patch.object(dm_mod, "DB_PATH", str(tmp_path / "progress.db")),
        patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}),
    ):
        DatabaseManager._instance = None
        db = DatabaseManager()
        for tmdb_id in ("1", "2", "3", "4", "5"):
            db.save_metadata({"id": tmdb_id, "title": f"T{tmdb_id}"}, "movie")
            db.save_request("movie", tmdb_id, DISCOVER_SOURCE)
        db.save_media_availability({('movie', '2'): st('processing'), ('movie', '3'): st('available'),
                                    ('movie', '4'): st('available'), ('movie', '5'): st('pending')})
        RecapRepository(db).mark_watched([(datetime(2030, 1, 2, tzinfo=timezone.utc), "movie", "4")])

        def ids(progress):
            result = db.get_all_requests_grouped_by_source(per_page=50, progress=progress)
            found = sorted(r["request_id"] for source in result["data"] for r in source["requests"])
            assert result["total_requests"] == len(found)
            return found

        picked = {progress: ids(progress) for progress in ('requested', 'processing', 'available', 'watched', None)}
    DatabaseManager._instance = None
    assert picked == {
        'requested': ['1', '5'], 'processing': ['2'], 'available': ['3'], 'watched': ['4'],
        None: ['1', '2', '3', '4', '5'],
    }


def test_tables_created_before_play_links_gain_the_column(tmp_path):
    import sqlite3
    db_file = str(tmp_path / "old.db")
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE media_availability (media_type VARCHAR(16) NOT NULL, tmdb_id VARCHAR(64) NOT NULL, "
                     "status VARCHAR(16) NOT NULL, updated_at TIMESTAMP, PRIMARY KEY (media_type, tmdb_id))")
    with (
        patch.object(dm_mod, "DB_PATH", db_file),
        patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}),
    ):
        DatabaseManager._instance = None
        db = DatabaseManager()
        db.save_media_availability({MOVIE: st('available', 'http://jf/1')})
        stored = db.get_media_availability()
    DatabaseManager._instance = None
    assert stored == {MOVIE: st('available', 'http://jf/1')}
