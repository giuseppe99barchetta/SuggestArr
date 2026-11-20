"""Tests for Trakt recommendations job automation."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.jobs.trakt_recommendations_automation import TraktRecommendationsAutomation


def _trakt_automation(media_type, max_results, lists):
    automation = TraktRecommendationsAutomation()
    automation.job_data = {
        "media_type": media_type,
        "max_results": max_results,
        "filters": {"ignore_collected": True, "ignore_watched": True},
    }
    automation.trakt_client = AsyncMock()
    automation.trakt_client.get_recommendations.side_effect = lambda item_type, **_: lists[item_type]
    return automation


def _passes(item):
    return {"id": int(item["tmdb_id"]), "title": item["tmdb_id"], "media_type": item["media_type"]}


@pytest.mark.asyncio
async def test_fetch_keeps_scanning_past_max_results():
    """The cap is applied when requesting, so the fetch returns every quality-passing candidate."""
    lists = {"movie": [{"tmdb_id": str(i)} for i in range(1, 4)]}
    automation = _trakt_automation("movie", 2, lists)
    automation._enrich_and_filter_item = AsyncMock(side_effect=_passes)

    results = await automation.fetch_trakt_recommendations()

    assert [r["id"] for r in results] == [1, 2, 3]
    automation.trakt_client.get_recommendations.assert_awaited_once_with(
        "movie", limit=100, ignore_collected=True, ignore_watched=True,
    )


@pytest.mark.asyncio
async def test_both_types_share_one_inspection_budget():
    lists = {"movie": [{"tmdb_id": str(i)} for i in range(100)],
             "tv": [{"tmdb_id": str(1000 + i)} for i in range(100)]}
    automation = _trakt_automation("both", 100, lists)
    automation._enrich_and_filter_item = AsyncMock(side_effect=_passes)

    await automation.fetch_trakt_recommendations()

    inspected = [call.args[0]["media_type"] for call in automation._enrich_and_filter_item.await_args_list]
    assert len(inspected) == 100 and inspected.count("movie") == inspected.count("tv") == 50


@pytest.mark.asyncio
async def test_unused_budget_of_one_type_goes_to_the_other():
    lists = {"movie": [{"tmdb_id": str(i)} for i in range(80)], "tv": []}
    automation = _trakt_automation("both", 100, lists)
    automation._enrich_and_filter_item = AsyncMock(side_effect=_passes)

    results = await automation.fetch_trakt_recommendations()

    assert len(results) == 80


@pytest.mark.asyncio
async def test_filter_and_request_stops_at_max_results_after_skipping_requested():
    automation = _trakt_automation("movie", 2, {})
    automation.db_manager = MagicMock()
    automation.db_manager.check_request_exists.side_effect = lambda media_type, tmdb_id: tmdb_id in {"1", "2"}
    automation.seer_discovered_ids = set()
    automation.local_content = {}
    automation.seer_client = MagicMock()
    automation.seer_client.check_already_downloaded = AsyncMock(return_value=False)
    automation.seer_client.check_already_requested = AsyncMock(return_value=False)
    automation.seer_client.request_media = AsyncMock(return_value=True)
    automation.job_data["user_ids"] = ["u1"]
    results = [{"id": i, "title": str(i), "media_type": "movie"} for i in range(1, 7)]

    requested, _ = await automation.filter_and_request(results)

    assert requested == 2
    assert [c.args[1]["id"] for c in automation.seer_client.request_media.await_args_list] == [3, 4]


@pytest.mark.asyncio
async def test_create_rejects_non_trakt_job():
    with patch("api_service.jobs.trakt_recommendations_automation.JobRepository") as repo_cls:
        repo = repo_cls.return_value
        repo.get_job.return_value = {"id": 1, "job_type": "discover", "name": "Wrong"}

        with pytest.raises(ValueError, match="not a trakt_recommendations job"):
            await TraktRecommendationsAutomation.create(1)


@pytest.mark.asyncio
async def test_build_trakt_client_requires_single_linked_user():
    automation = TraktRecommendationsAutomation()
    automation.job_data = {"user_ids": []}
    automation.env_vars = {"SELECTED_SERVICE": "jellyfin"}
    automation.db_manager = MagicMock()

    with pytest.raises(ValueError, match="exactly one linked media user"):
        automation._build_trakt_client()


def test_build_trakt_client_accepts_client_id_without_secret():
    automation = TraktRecommendationsAutomation()
    automation.job_data = {"user_ids": ["jf-1"]}
    automation.env_vars = {
        "SELECTED_SERVICE": "jellyfin",
        "TRAKT_CLIENT_ID": "cid",
        "TRAKT_CLIENT_SECRET": "",
    }
    automation.db_manager = MagicMock()
    automation.db_manager.get_media_user_identity.return_value = {"id": 1}

    with patch("api_service.jobs.trakt_recommendations_automation.TraktAccountResolver") as resolver_cls:
        resolver_cls.return_value.resolve.return_value = {
            "id": 5,
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": 12345,
            "token_source": "manual_oauth",
        }
        client = automation._build_trakt_client()

    assert client.client_id == "cid"
    assert client.client_secret == ""


@pytest.mark.asyncio
async def test_fetch_tmdb_details_builds_full_image_urls():
    automation = TraktRecommendationsAutomation()
    automation.tmdb_client = MagicMock()
    automation.tmdb_client.tmdb_api_url = "https://api.themoviedb.org/3"
    automation.tmdb_client.api_key = "key"
    automation.tmdb_client.REQUEST_TIMEOUT = 10

    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value={
        "id": 27205,
        "title": "Inception",
        "vote_average": 8.8,
        "vote_count": 30000,
        "poster_path": "/inception.jpg",
        "backdrop_path": "/inception-bg.jpg",
        "overview": "A dream within a dream.",
        "release_date": "2010-07-16",
        "genres": [{"id": 28}],
        "original_language": "en",
    })

    class _Ctx:
        async def __aenter__(self):
            return response

        async def __aexit__(self, *args):
            return False

    session = MagicMock()
    session.get = MagicMock(return_value=_Ctx())
    automation.tmdb_client._get_session = AsyncMock(return_value=session)

    details = await automation._fetch_tmdb_details(27205, "movie")

    assert details["poster_path"] == "https://image.tmdb.org/t/p/w500/inception.jpg"
    assert details["backdrop_path"] == "https://image.tmdb.org/t/p/w1280/inception-bg.jpg"
    assert details["rating"] == 8.8


@pytest.mark.asyncio
async def test_enrich_and_filter_item_skips_excluded_streaming_provider():
    automation = TraktRecommendationsAutomation()
    automation.tmdb_client = MagicMock()
    automation.tmdb_client._apply_filters.return_value = {"passed": True}
    automation.tmdb_client.filter_min_runtime = None
    automation.tmdb_client.rating_source = "tmdb"
    automation.tmdb_client.omdb_client = None
    automation.tmdb_client.get_watch_providers = AsyncMock(return_value=(True, "Netflix"))

    item = {"media_type": "movie", "tmdb_id": "1", "title": "Blocked"}
    automation._fetch_tmdb_details = AsyncMock(return_value={
        "id": 1,
        "title": "Blocked",
        "vote_average": 8.0,
        "vote_count": 1000,
    })

    result = await automation._enrich_and_filter_item(item)

    assert result is None
    automation.tmdb_client.get_watch_providers.assert_awaited_once_with(1, "movie")


@pytest.mark.asyncio
async def test_filter_and_request_uses_local_content_for_downloaded_check():
    automation = TraktRecommendationsAutomation()
    automation.job_data = {"media_type": "movie"}
    automation.local_content = {"movie": {"27205"}}
    automation.db_manager = MagicMock()
    automation.db_manager.check_request_exists.return_value = False
    automation.seer_client = MagicMock()
    automation.seer_client.check_already_downloaded = AsyncMock(return_value=True)
    automation.seer_client.check_already_requested = AsyncMock(return_value=False)
    automation.seer_client.request_media = AsyncMock(return_value=True)

    requested_count, dry_run_items = await automation.filter_and_request([
        {"id": 27205, "title": "Inception", "media_type": "movie"},
    ])

    assert requested_count == 0
    assert dry_run_items is None
    automation.seer_client.check_already_downloaded.assert_awaited_once_with(
        27205,
        "movie",
        automation.local_content,
    )
    automation.seer_client.check_already_requested.assert_not_awaited()
    automation.seer_client.request_media.assert_not_awaited()


@pytest.mark.asyncio
async def test_initialize_components_skips_seer_cache_sync_in_dry_run():
    automation = TraktRecommendationsAutomation()
    automation.job_data = {"filters": {}, "media_type": "movie"}
    automation.env_vars = {
        "SEER_API_URL": "http://seer",
        "SEER_TOKEN": "token",
        "SEER_USER_NAME": "user",
        "SEER_USER_PSW": "pass",
        "SEER_SESSION_TOKEN": "session",
        "TMDB_API_KEY": "tmdb",
        "SELECTED_SERVICE": "jellyfin",
    }
    automation._load_existing_content = AsyncMock(return_value={})
    automation._build_trakt_client = MagicMock(return_value=MagicMock())

    with (
        patch("api_service.utils.clients.SeerClient") as seer_cls,
        patch("api_service.jobs.trakt_recommendations_automation.TMDbClient"),
    ):
        seer = seer_cls.return_value
        seer.init = AsyncMock()

        await automation._initialize_components(dry_run=True)

    seer.init.assert_not_awaited()


@pytest.mark.asyncio
async def test_filter_and_request_skips_seer_discovered_ids():
    automation = TraktRecommendationsAutomation()
    automation.job_data = {"media_type": "movie"}
    automation.local_content = {}
    automation.seer_discovered_ids = {"movie:27205"}
    automation.db_manager = MagicMock()
    automation.db_manager.check_request_exists.return_value = False
    automation.seer_client = MagicMock()
    automation.seer_client.check_already_downloaded = AsyncMock(return_value=False)
    automation.seer_client.check_already_requested = AsyncMock(return_value=False)
    automation.seer_client.request_media = AsyncMock(return_value=True)

    requested_count, dry_run_items = await automation.filter_and_request([
        {"id": 27205, "title": "Inception", "media_type": "movie"},
    ])

    assert requested_count == 0
    assert dry_run_items is None
    automation.seer_client.check_already_downloaded.assert_not_awaited()
    automation.seer_client.check_already_requested.assert_not_awaited()
    automation.seer_client.request_media.assert_not_awaited()
