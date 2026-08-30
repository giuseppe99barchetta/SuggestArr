"""A job preview must show which watch tracker seeded each suggestion.

Without this, a Simkl- or Trakt-seeded recommendation is indistinguishable
from a media-server one in the preview, so there is no way to confirm a
tracker is actually feeding a job short of reading the logs.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from api_service.handler.jellyfin_handler import JellyfinHandler
from api_service.handler.plex_handler import PlexHandler


def _seer():
    seer = MagicMock()
    seer.check_already_requested = AsyncMock(return_value=False)
    seer.check_already_downloaded = AsyncMock(return_value=False)
    return seer


def _tmdb():
    tmdb = MagicMock()
    tmdb.get_watch_providers = AsyncMock(return_value=(False, None))
    return tmdb


def make_plex_handler():
    handler = PlexHandler(
        plex_client=MagicMock(), seer_client=_seer(), tmdb_client=_tmdb(),
        logger=MagicMock(), max_similar_movie=5, max_similar_tv=5,
        use_llm=False, dry_run=True, selected_users=[{"id": "1"}],
    )
    handler.existing_content_sets = {}
    return handler


def make_jellyfin_handler():
    handler = JellyfinHandler(
        jellyfin_client=MagicMock(), seer_client=_seer(), tmdb_client=_tmdb(),
        logger=MagicMock(), max_similar_movie=5, max_similar_tv=5,
        selected_users=[{"id": "1"}], use_llm=False, dry_run=True,
    )
    handler.existing_content_sets = {}
    return handler


HANDLERS = {"plex": make_plex_handler, "jellyfin": make_jellyfin_handler}

CANDIDATE = {"id": 500, "title": "A Similar Show", "poster_path": "/p.jpg"}


def preview_item(handler, origin):
    """Run one dry-run request and return the recorded preview item."""
    source_obj = {"id": 78, "title": "Dateline", "poster_path": "/s.jpg"}
    if origin:
        source_obj["_source_origin"] = origin
    asyncio.run(
        handler.request_similar_media([CANDIDATE], "tv", 5, source_obj, False, "1")
    )
    assert handler.dry_run_items, "expected the dry run to record an item"
    return handler.dry_run_items[0]


@pytest.mark.parametrize("provider", sorted(HANDLERS))
@pytest.mark.parametrize(
    "origin", ["simkl_history", "trakt_history"],
)
def test_a_tracker_seeded_preview_item_reports_its_origin(provider, origin):
    item = preview_item(HANDLERS[provider](), origin)
    assert item["source"]["source_origin"] == origin


@pytest.mark.parametrize("provider", sorted(HANDLERS))
def test_a_media_server_seed_reports_no_tracker_origin(provider):
    # The badge must not appear for ordinary media-server history.
    item = preview_item(HANDLERS[provider](), None)
    assert item["source"]["source_origin"] is None


@pytest.mark.parametrize("provider", sorted(HANDLERS))
def test_the_origin_does_not_disturb_the_rest_of_the_source(provider):
    item = preview_item(HANDLERS[provider](), "simkl_history")
    assert item["source"]["title"] == "Dateline"
    assert item["source"]["tmdb_id"] == 78
    assert item["source"]["poster_path"] == "/s.jpg"
