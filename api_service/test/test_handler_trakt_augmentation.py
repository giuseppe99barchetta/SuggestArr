import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.handler.jellyfin_handler import JellyfinHandler
from api_service.services.trakt.media_user_augmentor import TraktAugmentation


def _jellyfin_handler(augmentor):
    jf_client = MagicMock()
    jf_client.existing_content = {"movie": [], "tv": []}
    handler = JellyfinHandler(
        jf_client, MagicMock(), MagicMock(), logging.getLogger("test"),
        max_similar_movie=2, max_similar_tv=2,
        selected_users=[{"id": "jf-1", "name": "alice"}],
        use_llm=False,
        trakt_augmentor=augmentor,
    )
    return handler


def test_seed_and_skip_merge_for_linked_user():
    augmentor = MagicMock()
    augmentor.augment = AsyncMock(return_value=TraktAugmentation(
        seed_items=[{"tmdb_id": "11", "media_type": "movie", "title": "A"}],
        watched_ids={"movie": {"99"}, "tv": {"77"}},
    ))
    handler = _jellyfin_handler(augmentor)

    seeds = asyncio.run(handler._augment_user_trakt(1))

    # Trakt fully-watched ids joined the skip set
    assert "99" in handler.existing_content_sets["movie"]
    assert "77" in handler.existing_content_sets["tv"]
    # Seeds are returned for the caller to process additively
    assert len(seeds) == 1
    assert seeds[0]["tmdb_id"] == "11"
    assert seeds[0]["source_origin"] == "trakt_history"


def test_unlinked_user_is_noop():
    augmentor = MagicMock()
    augmentor.augment = AsyncMock(return_value=None)
    handler = _jellyfin_handler(augmentor)

    seeds = asyncio.run(handler._augment_user_trakt(1))

    assert seeds == []
    assert handler.existing_content_sets.get("movie", set()) == set()


def test_no_augmentor_is_noop():
    handler = _jellyfin_handler(None)
    seeds = asyncio.run(handler._augment_user_trakt(1))
    assert seeds == []


def test_seed_processing_failure_propagates():
    """_process_seed propagates tmdb failures to the caller."""
    handler = _jellyfin_handler(MagicMock())
    handler.tmdb_client.get_metadata = AsyncMock(side_effect=RuntimeError("tmdb down"))
    handler.request_similar_media = AsyncMock()

    seed = {"tmdb_id": "11", "media_type": "movie", "title": "A", "source_origin": "trakt_history"}
    with pytest.raises(RuntimeError, match="tmdb down"):
        asyncio.run(handler._process_seed({"id": "jf-1"}, seed))
    handler.request_similar_media.assert_not_awaited()


def test_process_seed_requests_similar():
    """_process_seed resolves, finds similar, and requests via Seer."""
    augmentor = MagicMock()
    augmentor.augment = AsyncMock(return_value=TraktAugmentation(
        seed_items=[{"tmdb_id": "11", "media_type": "movie", "title": "A"}],
        watched_ids={"movie": set(), "tv": set()},
    ))
    handler = _jellyfin_handler(augmentor)
    handler.tmdb_client.get_metadata = AsyncMock(return_value={"id": 11})
    handler.tmdb_client.find_similar_movies = AsyncMock(return_value=[{"id": 22}])
    handler.request_similar_media = AsyncMock()

    seed = {"tmdb_id": "11", "media_type": "movie", "title": "A", "source_origin": "trakt_history"}
    asyncio.run(handler._process_seed({"id": "jf-1"}, seed))

    handler.request_similar_media.assert_awaited_once()
    awaited_args = handler.request_similar_media.await_args.args
    assert awaited_args[1] == "movie"
    assert awaited_args[3]["_source_origin"] == "trakt_history"


def test_collect_trakt_seeds_returns_seeds_not_processes():
    """_collect_trakt_seeds_for_user fetches but does NOT process seeds."""
    augmentor = MagicMock()
    augmentor.augment = AsyncMock(return_value=TraktAugmentation(
        seed_items=[{"tmdb_id": "11", "media_type": "movie", "title": "A"}],
        watched_ids={"movie": {"99"}, "tv": set()},
    ))
    handler = _jellyfin_handler(augmentor)

    with patch("api_service.handler.jellyfin_handler.DatabaseManager") as DM:
        DM.return_value.upsert_media_user_identity.return_value = {"id": 1}
        seeds = asyncio.run(handler._collect_trakt_seeds_for_user(
            {"id": "jf-1", "name": "alice"}
        ))

    assert len(seeds) == 1
    assert seeds[0]["tmdb_id"] == "11"
    # Watched IDs should be merged into skip set by _augment_user_trakt
    assert "99" in handler.existing_content_sets["movie"]


def test_merge_seeds_dedup_and_sort():
    """_merge_seeds deduplicates by (media_type, tmdb_id) and sorts by date."""
    handler = _jellyfin_handler(None)
    seeds = [
        {"tmdb_id": "1", "media_type": "movie", "date": 1000, "title": "Old"},
        {"tmdb_id": "2", "media_type": "movie", "date": 3000, "title": "New"},
        {"tmdb_id": "1", "media_type": "movie", "date": 2000, "title": "Dup"},  # dupe tmdb_id, newer
        {"tmdb_id": "3", "media_type": "tv", "date": 500, "title": "TV"},
    ]
    merged = handler._merge_seeds(seeds)
    assert len(merged) == 3
    # Newest first, dupe keeps newest entry
    assert merged[0]["title"] == "New"
    assert merged[1]["title"] == "Dup"
    assert merged[2]["title"] == "TV"


def test_merge_seeds_caps_to_max_content():
    """_merge_seeds respects max_content cap."""
    handler = _jellyfin_handler(None)
    handler.max_content = 2
    seeds = [
        {"tmdb_id": str(i), "media_type": "movie", "date": i}
        for i in range(10)
    ]
    merged = handler._merge_seeds(seeds)
    assert len(merged) == 2
    # Newest first (highest date)
    assert merged[0]["date"] == 9
    assert merged[1]["date"] == 8
