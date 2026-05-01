import json
import logging
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api_service.handler.base_handler import BaseMediaHandler
from api_service.handler.jellyfin_handler import JellyfinHandler
from api_service.handler.plex_handler import PlexHandler
from api_service.jobs import recommendation_automation as recommendation_module
from api_service.jobs.recommendation_automation import RecommendationAutomation
from api_service.services.llm.llm_service import interpret_search_query


USER = {"id": "user-1", "name": "Alice"}

PLEX_RECENT_ITEMS = [
    {
        "type": "movie",
        "title": "Inception",
        "year": 2010,
        "key": "/library/metadata/1",
        "librarySectionID": "1",
    },
    {
        "type": "episode",
        "title": "Secrets",
        "grandparentTitle": "Dark",
        "year": 2017,
        "grandparentKey": "/library/metadata/2",
        "librarySectionID": "2",
    },
]

JELLYFIN_RECENT_ITEMS = {
    "Movies": [
        {
            "Type": "Movie",
            "Name": "Arrival",
            "ProductionYear": 2016,
            "ProviderIds": {"Tmdb": "11"},
        }
    ],
    "Series": [
        {
            "Type": "Episode",
            "Name": "Pilot",
            "SeriesName": "Severance",
            "ProductionYear": 2022,
            "SeriesId": "series-22",
            "SeriesProviderIds": {"Tmdb": "22"},
        }
    ],
}

MOVIE_RECOMMENDATIONS = [
    {
        "title": "Tenet",
        "year": 2020,
        "source_title": "Inception",
        "rationale": "Shared cerebral blockbuster energy.",
    },
    {
        "title": "Blade Runner 2049",
        "year": 2017,
        "source_title": "Arrival",
        "rationale": "Another reflective modern sci-fi film.",
    },
]

TV_RECOMMENDATIONS = [
    {
        "title": "1899",
        "year": 2022,
        "source_title": "Dark - S01E01",
        "rationale": "Dense mystery with a similar tone.",
    },
    {
        "title": "Silo",
        "year": 2023,
        "source_title": "Severance - S01E01",
        "rationale": "Stylized suspense built around a hidden system.",
    },
]

MOVIE_SEARCH_RESULTS = {
    "Inception": {
        "id": 10,
        "title": "Inception",
        "release_date": "2010-07-16",
        "original_language": "en",
        "overview": "Dream infiltration thriller.",
        "vote_average": 8.4,
        "vote_count": 1000,
        "poster_path": "/inception.jpg",
    },
    "Arrival": {
        "id": 11,
        "title": "Arrival",
        "release_date": "2016-11-11",
        "original_language": "en",
        "overview": "First contact drama.",
        "vote_average": 8.1,
        "vote_count": 800,
        "poster_path": "/arrival.jpg",
    },
    "Tenet": {
        "id": 110,
        "title": "Tenet",
        "release_date": "2020-08-26",
        "original_language": "en",
        "overview": "Time inversion espionage.",
        "vote_average": 7.6,
        "vote_count": 900,
        "poster_path": "/tenet.jpg",
    },
    "Blade Runner 2049": {
        "id": 111,
        "title": "Blade Runner 2049",
        "release_date": "2017-10-06",
        "original_language": "en",
        "overview": "Neo-noir sci-fi mystery.",
        "vote_average": 8.0,
        "vote_count": 850,
        "poster_path": "/br2049.jpg",
    },
}

TV_SEARCH_RESULTS = {
    "Dark": {
        "id": 20,
        "name": "Dark",
        "first_air_date": "2017-12-01",
        "original_language": "de",
        "overview": "Time-bending family mystery.",
        "vote_average": 8.7,
        "vote_count": 700,
        "poster_path": "/dark.jpg",
    },
    "Severance": {
        "id": 22,
        "name": "Severance",
        "first_air_date": "2022-02-18",
        "original_language": "en",
        "overview": "Office thriller with split memories.",
        "vote_average": 8.6,
        "vote_count": 600,
        "poster_path": "/severance.jpg",
    },
    "1899": {
        "id": 220,
        "name": "1899",
        "first_air_date": "2022-11-17",
        "original_language": "de",
        "overview": "A mystery at sea.",
        "vote_average": 7.4,
        "vote_count": 400,
        "poster_path": "/1899.jpg",
    },
    "Silo": {
        "id": 221,
        "name": "Silo",
        "first_air_date": "2023-05-05",
        "original_language": "en",
        "overview": "Life inside an underground silo.",
        "vote_average": 8.1,
        "vote_count": 500,
        "poster_path": "/silo.jpg",
    },
}


class AsyncContextClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSeerClient(AsyncContextClient):
    def __init__(self):
        self.init = AsyncMock()
        self.check_already_requested = AsyncMock(return_value=False)
        self.check_already_downloaded = AsyncMock(return_value=False)
        self.check_requests_exist_batch = AsyncMock(return_value=set())


class FakeTMDbClient(AsyncContextClient):
    def __init__(self, language_filter=None):
        self.language_filter = language_filter or []
        self.release_year_filter = 0
        self.release_year_filter_to = None
        self.tmdb_threshold = None
        self.omdb_client = None
        self.movie_calls = []
        self.tv_calls = []

    async def search_movie(self, title, year=None):
        self.movie_calls.append((title, year))
        item = MOVIE_SEARCH_RESULTS.get(title)
        return [deepcopy(item)] if item else []

    async def search_tv(self, title, year=None):
        self.tv_calls.append((title, year))
        item = TV_SEARCH_RESULTS.get(title)
        return [deepcopy(item)] if item else []

    async def get_watch_providers(self, source_tmdb_id, media_type):
        return False, None

    def _apply_filters(self, item, item_type):
        return {"passed": True}


class FakePlexClient(AsyncContextClient):
    def __init__(self, recent_items=None):
        self.recent_items = recent_items or deepcopy(PLEX_RECENT_ITEMS)
        self.existing_content = {}
        self.init_existing_content = AsyncMock()

    async def get_recent_items(self):
        return deepcopy(self.recent_items)


class FakeJellyfinClient(AsyncContextClient):
    def __init__(self, recent_items_by_library=None):
        self.recent_items_by_library = recent_items_by_library or deepcopy(JELLYFIN_RECENT_ITEMS)
        self.existing_content = {}
        self.init_existing_content = AsyncMock()
        self.get_all_users = AsyncMock(return_value=[deepcopy(USER)])

    async def get_recent_items(self, user):
        return deepcopy(self.recent_items_by_library)


class RecordingHandler(BaseMediaHandler):
    def __init__(self, seer_client, tmdb_client, logger):
        super().__init__(
            seer_client=seer_client,
            tmdb_client=tmdb_client,
            logger=logger,
            max_similar_movie=2,
            max_similar_tv=2,
            use_llm=True,
            dry_run=True,
        )
        self.recorded_requests = []

    def _populate_existing_content_sets(self):
        self.existing_content_sets = {}

    async def _request_llm_recommendation(self, media, item_type, source_obj, user=None):
        self.recorded_requests.append(
            {
                "media": media,
                "item_type": item_type,
                "source": source_obj,
                "user": user,
            }
        )


class FakeJobRepository:
    def __init__(self, job_data):
        self.job_data = deepcopy(job_data)
        self.log_execution_start = AsyncMock()
        self.log_execution_end = AsyncMock()

    def get_job(self, job_id):
        return deepcopy(self.job_data)

    def log_execution_start(self, job_id):
        return 101

    def log_execution_end(self, **kwargs):
        return None


class FakeDatabaseManager:
    pass


def build_runtime_config(selected_service):
    return {
        "SELECTED_SERVICE": selected_service,
        "SELECTED_USERS": [deepcopy(USER)],
        "MAX_CONTENT_CHECKS": 10,
        "MAX_SIMILAR_MOVIE": "2",
        "MAX_SIMILAR_TV": "2",
        "SEARCH_SIZE": "20",
        "FILTER_NUM_SEASONS": None,
        "FILTER_TMDB_THRESHOLD": "60",
        "FILTER_TMDB_MIN_VOTES": "20",
        "FILTER_INCLUDE_NO_RATING": True,
        "FILTER_RELEASE_YEAR": "0",
        "FILTER_LANGUAGE": [],
        "FILTER_GENRES_EXCLUDE": [],
        "FILTER_REGION_PROVIDER": None,
        "FILTER_STREAMING_SERVICES": [],
        "FILTER_MIN_RUNTIME": None,
        "FILTER_RATING_SOURCE": "tmdb",
        "FILTER_IMDB_THRESHOLD": None,
        "FILTER_IMDB_MIN_VOTES": None,
        "FILTER_INCLUDE_TVOD": False,
        "OMDB_API_KEY": "",
        "EXCLUDE_DOWNLOADED": True,
        "EXCLUDE_REQUESTED": True,
        "SEER_API_URL": "http://seer.local",
        "SEER_TOKEN": "seer-token",
        "SEER_USER_NAME": "admin",
        "SEER_USER_PSW": "pass",
        "SEER_SESSION_TOKEN": "",
        "SEER_ANIME_PROFILE_CONFIG": {},
        "TMDB_API_KEY": "tmdb-token",
        "JELLYFIN_API_URL": "http://jellyfin.local",
        "JELLYFIN_TOKEN": "jellyfin-token",
        "JELLYFIN_LIBRARIES": [
            {"name": "Movies", "is_anime": False},
            {"name": "Series", "is_anime": False},
        ],
        "PLEX_API_URL": "http://plex.local",
        "PLEX_TOKEN": "plex-token",
        "PLEX_LIBRARIES": [
            {"id": "1", "is_anime": False},
            {"id": "2", "is_anime": False},
        ],
        "HONOR_JELLYSEER_DISCOVERY": False,
        "OPENAI_API_KEY": "fake-openai-key",
        "OPENAI_MODEL": "gpt-4o-mini",
        "OPENAI_BASE_URL": None,
        "LLM_MAX_RETRIES": 0,
    }


def build_job_data(name):
    return {
        "id": 1,
        "name": name,
        "job_type": "recommendation",
        "user_ids": [USER["id"]],
        "media_type": "both",
        "max_results": 10,
        "filters": {
            "use_llm": True,
            "max_similar_movie": 1,
            "max_similar_tv": 1,
        },
    }


def make_llm_side_effect():
    async def _side_effect(history_items, max_results, item_type, filters=None):
        assert isinstance(history_items, list)
        assert max_results > 0
        assert item_type in {"movie", "tv"}
        assert isinstance(filters, dict)
        assert all("title" in item for item in history_items)
        assert all(item.get("year") is None or isinstance(item.get("year"), int) for item in history_items)
        watched_titles = {item["title"] for item in history_items}
        if item_type == "movie":
            if "Arrival" in watched_titles:
                return deepcopy(MOVIE_RECOMMENDATIONS[1:2])
            return deepcopy(MOVIE_RECOMMENDATIONS[:max_results])
        if "Severance" in watched_titles:
            return deepcopy(TV_RECOMMENDATIONS[1:2])
        return deepcopy(TV_RECOMMENDATIONS[:max_results])

    return AsyncMock(side_effect=_side_effect)


def make_openai_response(payload):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
    )


@pytest.fixture
def test_logger(caplog):
    logger_name = "test.media_handler.integration"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    caplog.set_level(logging.INFO, logger=logger_name)
    return logger


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("item_type", "use_user"),
    [("movie", False), ("tv", False), ("movie", True), ("tv", True)],
)
async def test_base_media_handler_accepts_legacy_and_user_aware_signatures(test_logger, item_type, use_user):
    handler = RecordingHandler(FakeSeerClient(), FakeTMDbClient(), test_logger)
    llm_mock = make_llm_side_effect()

    history_items = [
        {"title": "Inception", "year": 2010},
        {"title": "Dark", "year": 2017},
    ]

    with patch("api_service.handler.base_handler.get_recommendations_from_history", llm_mock):
        if use_user:
            await handler.process_llm_recommendations(deepcopy(USER), history_items, item_type, 1)
        else:
            await handler.process_llm_recommendations(history_items, item_type, 1)

    assert llm_mock.await_count == 1
    assert len(handler.recorded_requests) == 1
    assert handler.recorded_requests[0]["item_type"] == item_type
    assert handler.recorded_requests[0]["user"] == (USER if use_user else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("use_user", [False, True])
async def test_base_media_handler_skips_llm_when_max_results_is_zero(test_logger, use_user):
    handler = RecordingHandler(FakeSeerClient(), FakeTMDbClient(), test_logger)
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called when max_results is zero"))
    history_items = [{"title": "Inception", "year": 2010}]

    with patch("api_service.handler.base_handler.get_recommendations_from_history", llm_mock):
        if use_user:
            await handler.process_llm_recommendations(deepcopy(USER), history_items, "movie", 0)
        else:
            await handler.process_llm_recommendations(history_items, "movie", 0)

    llm_mock.assert_not_awaited()
    assert handler.recorded_requests == []


@pytest.mark.asyncio
async def test_plex_handler_process_recent_items_runs_real_llm_flow_without_type_error(caplog, test_logger):
    handler = PlexHandler(
        plex_client=FakePlexClient(),
        seer_client=FakeSeerClient(),
        tmdb_client=FakeTMDbClient(),
        logger=test_logger,
        max_similar_movie=1,
        max_similar_tv=1,
        use_llm=True,
        dry_run=True,
    )
    llm_mock = make_llm_side_effect()

    with patch("api_service.handler.base_handler.get_recommendations_from_history", llm_mock):
        await handler.process_recent_items()

    assert llm_mock.await_count == 2
    assert handler.request_count == 2
    assert {item["media_type"] for item in handler.dry_run_items} == {"movie", "tv"}
    assert {item["title"] for item in handler.dry_run_items} == {"Tenet", "1899"}
    assert ("Dark", None) in handler.tmdb_client.tv_calls
    assert "TypeError" not in caplog.text


@pytest.mark.asyncio
async def test_jellyfin_handler_process_recent_items_runs_real_llm_flow_without_type_error(caplog, test_logger):
    handler = JellyfinHandler(
        jellyfin_client=FakeJellyfinClient(),
        seer_client=FakeSeerClient(),
        tmdb_client=FakeTMDbClient(),
        logger=test_logger,
        max_similar_movie=1,
        max_similar_tv=1,
        selected_users=[deepcopy(USER)],
        use_llm=True,
        dry_run=True,
    )
    llm_mock = make_llm_side_effect()

    with patch("api_service.handler.base_handler.get_recommendations_from_history", llm_mock):
        await handler.process_recent_items()

    assert llm_mock.await_count == 2
    assert handler.request_count == 2
    assert {item["media_type"] for item in handler.dry_run_items} == {"movie", "tv"}
    assert {item["title"] for item in handler.dry_run_items} == {"Blade Runner 2049", "Silo"}
    assert ("Severance", None) in handler.tmdb_client.tv_calls
    assert "TypeError" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selected_service", "expected_titles"),
    [
        ("plex", {"Tenet", "1899"}),
        ("jellyfin", {"Blade Runner 2049", "Silo"}),
    ],
)
async def test_recommendation_automation_dry_run_preserves_async_flow_and_logs(monkeypatch, caplog, selected_service, expected_titles):
    caplog.set_level(logging.INFO)
    runtime_config = build_runtime_config(selected_service)
    fake_repo = FakeJobRepository(build_job_data(f"{selected_service}-dry-run"))
    fake_tmdb = FakeTMDbClient()
    fake_seer = FakeSeerClient()
    fake_plex = FakePlexClient()
    fake_jellyfin = FakeJellyfinClient()
    llm_mock = make_llm_side_effect()

    monkeypatch.setattr(recommendation_module.LoggerManager, "get_logger", lambda name: logging.getLogger(name))
    monkeypatch.setattr(recommendation_module.ConfigService, "get_runtime_config", lambda: deepcopy(runtime_config))
    monkeypatch.setattr(recommendation_module, "JobRepository", lambda: fake_repo)
    monkeypatch.setattr(recommendation_module, "DatabaseManager", lambda: FakeDatabaseManager())
    monkeypatch.setattr(recommendation_module, "SeerClient", lambda *args, **kwargs: fake_seer)
    monkeypatch.setattr(recommendation_module, "TMDbClient", lambda *args, **kwargs: fake_tmdb)
    monkeypatch.setattr(recommendation_module, "PlexClient", lambda *args, **kwargs: fake_plex)
    monkeypatch.setattr(recommendation_module, "JellyfinClient", lambda *args, **kwargs: fake_jellyfin)

    with patch("api_service.handler.base_handler.get_recommendations_from_history", llm_mock):
        automation = await RecommendationAutomation.create(job_id=1, dry_run=True)
        result = await automation.run(dry_run=True)

    assert result.success is True
    assert result.error_message is None
    assert result.requested_count == 2
    assert {item["title"] for item in result.dry_run_items} == expected_titles
    assert llm_mock.await_count == 2
    assert "Starting recommendation job" in caplog.text
    assert "Advanced Algorithm enabled. Generating recommendations using LLM." in caplog.text
    assert "Job completed: 2 would be requested" in caplog.text
    assert "TypeError" not in caplog.text


@pytest.mark.asyncio
async def test_recommendation_automation_dry_run_respects_job_max_results(monkeypatch):
    runtime_config = build_runtime_config("jellyfin")
    job_data = build_job_data("jellyfin-capped-dry-run")
    job_data["max_results"] = 1
    fake_repo = FakeJobRepository(job_data)
    fake_tmdb = FakeTMDbClient()
    fake_seer = FakeSeerClient()
    fake_jellyfin = FakeJellyfinClient()
    llm_mock = make_llm_side_effect()

    monkeypatch.setattr(recommendation_module.LoggerManager, "get_logger", lambda name: logging.getLogger(name))
    monkeypatch.setattr(recommendation_module.ConfigService, "get_runtime_config", lambda: deepcopy(runtime_config))
    monkeypatch.setattr(recommendation_module, "JobRepository", lambda: fake_repo)
    monkeypatch.setattr(recommendation_module, "DatabaseManager", lambda: FakeDatabaseManager())
    monkeypatch.setattr(recommendation_module, "SeerClient", lambda *args, **kwargs: fake_seer)
    monkeypatch.setattr(recommendation_module, "TMDbClient", lambda *args, **kwargs: fake_tmdb)
    monkeypatch.setattr(recommendation_module, "JellyfinClient", lambda *args, **kwargs: fake_jellyfin)

    with patch("api_service.handler.base_handler.get_recommendations_from_history", llm_mock):
        automation = await RecommendationAutomation.create(job_id=1, dry_run=True)
        result = await automation.run(dry_run=True)

    assert result.success is True
    assert result.requested_count == 1
    assert sum(1 for item in result.dry_run_items if item["would_request"]) == 1
    assert any(
        item.get("filter_results", {}).get("request_limit", {}).get("passed") is False
        for item in result.dry_run_items
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language_payload", "history_items", "expected_language"),
    [
        ("it", [{"title": "Gomorra", "year": 2008}], "it"),
        (["it", "en"], [{"title": "Gomorra", "year": 2008}], "it"),
        ("ja", [], "ja"),
    ],
)
async def test_interpret_search_query_coerces_original_language_and_accepts_empty_history(language_payload, history_items, expected_language):
    payload = json.dumps(
        {
            "discover_params": {
                "genres": ["Thriller"],
                "original_language": language_payload,
                "year_from": 1990,
            },
            "suggested_titles": [
                {"title": "Film 1", "year": 2001, "rationale": "Matches the prompt."}
            ],
        }
    )
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(return_value=make_openai_response(payload))
            )
        )
    )
    config = {
        "OPENAI_MODEL": "gpt-4o-mini",
        "OPENAI_API_KEY": "fake-openai-key",
        "OPENAI_BASE_URL": None,
        "LLM_MAX_RETRIES": 0,
    }

    with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), patch(
        "api_service.services.llm.llm_service.ConfigService.get_runtime_config",
        return_value=config,
    ):
        result = await interpret_search_query("international thriller", history_items)

    assert result["discover_params"]["original_language"] == expected_language
    assert result["suggested_titles"][0]["title"] == "Film 1"
