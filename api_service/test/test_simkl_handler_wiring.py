"""Tests that the handlers treat Simkl as a peer of Trakt.

The risk this guards is asymmetry: a user linked to both providers should
contribute from each, and neither should be able to break the other.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.handler.base_handler import BaseMediaHandler
from api_service.services.simkl.media_user_augmentor import SimklAugmentation
from api_service.services.trakt.media_user_augmentor import TraktAugmentation


class Handler(BaseMediaHandler):
    """Minimal concrete handler; the base class is abstract."""

    def _populate_existing_content_sets(self):
        self.existing_content_sets = {}

    async def _request_llm_recommendation(self, *args, **kwargs):
        return None


def make_handler(**kwargs):
    handler = Handler(
        seer_client=MagicMock(), tmdb_client=MagicMock(), logger=MagicMock(),
        max_similar_movie=5, max_similar_tv=5, use_llm=False, **kwargs,
    )
    handler.existing_content_sets = {}
    return handler


class FakeAugmentor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def augment(self, identity_id):
        self.calls.append(identity_id)
        return self.result


SIMKL_RESULT = SimklAugmentation(
    seed_items=[{"tmdb_id": "78", "media_type": "tv", "title": "Dateline", "watched_at": 300}],
    watched_ids={"movie": {"120"}, "tv": {"70453"}},
)
TRAKT_RESULT = TraktAugmentation(
    seed_items=[{"tmdb_id": "99", "media_type": "movie", "title": "Trakt Film", "watched_at": 400}],
    watched_ids={"movie": {"555"}, "tv": set()},
)


def test_simkl_seeds_are_tagged_with_their_own_origin():
    handler = make_handler(simkl_augmentor=FakeAugmentor(SIMKL_RESULT))
    seeds = asyncio.run(handler._augment_user_simkl(1))

    assert seeds[0]["source_origin"] == "simkl_history"


def test_simkl_watched_ids_join_the_skip_set():
    handler = make_handler(simkl_augmentor=FakeAugmentor(SIMKL_RESULT))
    asyncio.run(handler._augment_user_simkl(1))

    assert handler.existing_content_sets["movie"] == {"120"}
    assert handler.existing_content_sets["tv"] == {"70453"}


def test_both_providers_contribute_to_the_same_skip_set():
    handler = make_handler(
        trakt_augmentor=FakeAugmentor(TRAKT_RESULT),
        simkl_augmentor=FakeAugmentor(SIMKL_RESULT),
    )
    asyncio.run(handler._augment_user_trakt(1))
    asyncio.run(handler._augment_user_simkl(1))

    assert handler.existing_content_sets["movie"] == {"555", "120"}


def test_each_provider_is_a_no_op_when_the_other_is_configured_alone():
    handler = make_handler(trakt_augmentor=FakeAugmentor(TRAKT_RESULT))
    assert asyncio.run(handler._augment_user_simkl(1)) == []

    handler = make_handler(simkl_augmentor=FakeAugmentor(SIMKL_RESULT))
    assert asyncio.run(handler._augment_user_trakt(1)) == []


def test_an_augmentor_returning_none_yields_no_seeds():
    handler = make_handler(simkl_augmentor=FakeAugmentor(None))
    assert asyncio.run(handler._augment_user_simkl(1)) == []


def test_no_identity_short_circuits_before_calling_the_augmentor():
    augmentor = FakeAugmentor(SIMKL_RESULT)
    handler = make_handler(simkl_augmentor=augmentor)

    assert asyncio.run(handler._augment_user_simkl(None)) == []
    assert augmentor.calls == []


def test_merging_dedupes_a_title_both_providers_report_keeping_the_newer():
    handler = make_handler(max_content=10)
    merged = handler._merge_seeds([
        {"tmdb_id": "78", "media_type": "tv", "date": 100, "source_origin": "trakt_history"},
        {"tmdb_id": "78", "media_type": "tv", "date": 300, "source_origin": "simkl_history"},
        {"tmdb_id": "99", "media_type": "movie", "date": 200, "source_origin": "simkl_history"},
    ])

    assert len(merged) == 2
    assert merged[0]["source_origin"] == "simkl_history"
    assert merged[0]["date"] == 300


def test_the_same_tmdb_id_under_different_media_types_is_not_deduped():
    handler = make_handler(max_content=10)
    merged = handler._merge_seeds([
        {"tmdb_id": "78", "media_type": "tv", "date": 100},
        {"tmdb_id": "78", "media_type": "movie", "date": 200},
    ])
    assert len(merged) == 2


# ---- Origin attribution through the LLM path ---------------------------------

def resolve_origin(history_items, source_title):
    """Run the LLM flow far enough to read the origin off the source object.

    The LLM answers with titles rather than the seed objects it was handed, so
    the origin has to be matched back by title; without that, a request shows
    no provenance in the UI.
    """
    handler = make_handler()
    source_obj = {"id": 1}
    recommendation = {"title": "New Show", "year": 2024, "source_title": source_title}

    async def fake_llm(*args, **kwargs):
        return [recommendation]

    with patch("api_service.handler.base_handler.get_recommendations_from_history", fake_llm), \
         patch.object(Handler, "_resolve_llm_source", new=AsyncMock(return_value=source_obj)), \
         patch.object(Handler, "_history_key", side_effect=lambda i: (
             str(i.get("title", "")).strip().lower(), "tv")):
        handler.tmdb_client.search_tv = AsyncMock(return_value=[])
        asyncio.run(handler.process_llm_recommendations(
            {"id": "u1"}, history_items, "tv", 5,
        ))
    return source_obj.get("_source_origin")


def test_a_simkl_seeded_recommendation_keeps_its_origin():
    origin = resolve_origin(
        [{"title": "Dateline", "source_origin": "simkl_history"}], "Dateline",
    )
    assert origin == "simkl_history"


def test_a_trakt_seeded_recommendation_keeps_its_origin():
    origin = resolve_origin(
        [{"title": "Dateline", "source_origin": "trakt_history"}], "Dateline",
    )
    assert origin == "trakt_history"


def test_a_media_server_seed_is_not_attributed_to_a_watch_tracker():
    origin = resolve_origin([{"title": "Dateline"}], "Dateline")
    assert origin is None
