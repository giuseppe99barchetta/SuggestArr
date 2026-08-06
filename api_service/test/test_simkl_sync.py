"""Tests for the activities-gated Simkl watch-history sync.

The behaviour under test is mostly about *restraint*: Simkl suspends client IDs
that poll the library endpoints without a gating signal, so most of these
assert that a call did not happen.
"""
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from api_service.services.simkl.simkl_client import SimklAuthError, SimklClient, SimklError
from api_service.services.simkl.watch_history_sync import (
    CACHED_STATUSES,
    EXCLUSION_STATUSES,
    SEED_STATUSES,
    SimklWatchHistorySync,
)


def activities(**buckets):
    """Build an activities payload with the live shape and null defaults."""
    base = {
        "all": "2026-08-05T22:55:26Z",
        "tv_shows": {"watching": None, "completed": None, "hold": None,
                     "dropped": None, "removed_from_list": None},
        "anime": {"watching": None, "completed": None, "hold": None,
                  "dropped": None, "removed_from_list": None},
        "movies": {"completed": None, "dropped": None, "removed_from_list": None},
    }
    for key, value in buckets.items():
        base[key].update(value)
    return base


def show_entry(simkl_id, status="watching", tmdb="100", watched="2026-05-09T21:22:45Z", **extra):
    entry = {
        "last_watched_at": watched,
        "status": status,
        "show": {"title": f"Show {simkl_id}", "year": 2020,
                 "ids": {"simkl": simkl_id, "tmdb": tmdb, "tvdb": "900"}},
    }
    entry.update(extra)
    return entry


class FakeClient:
    """Stands in for SimklClient, recording every bucket it was asked for."""

    def __init__(self, activities_payload, items=None, raise_on_activities=None):
        self.activities_payload = activities_payload
        self.items = items or {}
        self.raise_on_activities = raise_on_activities
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get_activities(self):
        self.calls.append(("activities", None, None))
        if self.raise_on_activities:
            raise self.raise_on_activities
        return self.activities_payload

    async def get_all_items(self, media_type, status, *, date_from=None, ids_only=False):
        self.calls.append((media_type, status, date_from))
        return self.items.get((media_type, status), [])

    @property
    def pulls(self):
        return [c for c in self.calls if c[0] != "activities"]


class ClientFactory:
    """Returns the fake instance while preserving SimklClient's class constants.

    The sync module reads STATUSES_BY_TYPE and ACTIVITIES_KEY_BY_TYPE off the
    class, so a plain lambda substitute would hide them.
    """
    STATUSES_BY_TYPE = SimklClient.STATUSES_BY_TYPE
    ACTIVITIES_KEY_BY_TYPE = SimklClient.ACTIVITIES_KEY_BY_TYPE

    def __init__(self, client):
        self._client = client

    def __call__(self, *args, **kwargs):
        return self._client


def make_sync(monkeypatch, client, db=None):
    db = db or MagicMock()
    db.get_simkl_watched_cache.return_value = []
    sync = SimklWatchHistorySync("cid", db=db)
    monkeypatch.setattr(
        "api_service.services.simkl.watch_history_sync.SimklClient",
        ClientFactory(client),
    )
    return sync, db


LINK = {"id": 7}


# ---- Cooldown ----------------------------------------------------------------

def test_inside_the_cooldown_no_http_call_is_made_at_all(monkeypatch):
    client = FakeClient(activities())
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": 1, "last_activities_check_at": int(time.time()),
    }

    assert asyncio.run(sync.ensure_synced(LINK, "tok")) is True
    assert client.calls == []


def test_outside_the_cooldown_activities_is_checked(monkeypatch):
    client = FakeClient(activities())
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": 1,
        "last_activities_check_at": int(time.time()) - SimklWatchHistorySync.ACTIVITIES_COOLDOWN_SECONDS - 1,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    assert client.calls[0][0] == "activities"


def test_a_never_synced_link_is_not_blocked_by_the_cooldown(monkeypatch):
    client = FakeClient(activities())
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    assert client.calls


# ---- Gating ------------------------------------------------------------------

def test_unchanged_activities_costs_exactly_one_request(monkeypatch):
    stored = activities(tv_shows={"watching": "2026-08-05T21:27:57Z"})
    client = FakeClient(stored)
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": stored, "last_full_sync_at": 100, "last_activities_check_at": 0,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    assert client.pulls == []


def test_only_the_bucket_whose_timestamp_moved_is_refetched(monkeypatch):
    stored = activities(
        tv_shows={"watching": "2026-08-01T00:00:00Z", "completed": "2026-08-01T00:00:00Z"},
    )
    current = activities(
        tv_shows={"watching": "2026-08-05T21:27:57Z", "completed": "2026-08-01T00:00:00Z"},
    )
    client = FakeClient(current, items={("shows", "watching"): [show_entry(1)]})
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": stored, "last_full_sync_at": 100, "last_activities_check_at": 0,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    assert client.pulls == [("shows", "watching", "2026-08-01T00:00:00Z")]


def test_a_delta_pull_passes_the_previously_stored_timestamp_as_date_from(monkeypatch):
    stored = activities(movies={"completed": "2026-07-01T00:00:00Z"})
    current = activities(movies={"completed": "2026-08-05T02:20:43Z"})
    client = FakeClient(current)
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": stored, "last_full_sync_at": 100, "last_activities_check_at": 0,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    assert client.pulls == [("movies", "completed", "2026-07-01T00:00:00Z")]


def test_first_sync_pulls_every_populated_bucket_without_date_from(monkeypatch):
    current = activities(
        tv_shows={"watching": "2026-08-05T21:27:57Z", "completed": "2026-08-05T06:15:51Z"},
        movies={"completed": "2026-08-05T02:20:43Z"},
    )
    client = FakeClient(current)
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    assert sorted(client.pulls) == [
        ("movies", "completed", None),
        ("shows", "completed", None),
        ("shows", "watching", None),
    ]


def test_buckets_the_user_has_never_used_are_never_requested(monkeypatch):
    """Simkl reports null for an unused list; a pull there would be wasted."""
    current = activities(tv_shows={"watching": "2026-08-05T21:27:57Z"})
    client = FakeClient(current)
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    assert client.pulls == [("shows", "watching", None)]


def test_movies_are_never_asked_for_watching_or_hold(monkeypatch):
    """Those buckets do not exist for movies and answer {} with HTTP 200."""
    current = activities(
        movies={"completed": "2026-08-05T02:20:43Z", "dropped": "2026-08-05T02:20:43Z"},
    )
    client = FakeClient(current)
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    requested = {(t, s) for t, s, _ in client.pulls}
    assert ("movies", "watching") not in requested
    assert ("movies", "hold") not in requested


def test_plantowatch_is_never_cached(monkeypatch):
    """Caching a wishlist as watched would suppress the very titles a user wants."""
    assert "plantowatch" not in CACHED_STATUSES

    current = activities(tv_shows={"plantowatch": "2026-08-05T21:27:57Z"})
    client = FakeClient(current)
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    assert client.pulls == []


def test_activities_are_stored_only_after_every_pull_succeeded(monkeypatch):
    """A partial save would permanently skip the deltas that failed."""
    current = activities(tv_shows={"watching": "2026-08-05T21:27:57Z"})

    class Failing(FakeClient):
        async def get_all_items(self, *a, **k):
            raise SimklError("boom")

    client = Failing(current)
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))

    saved_activities = [
        call for call in db.update_simkl_sync_state.call_args_list
        if call.kwargs.get("activities") is not None
    ]
    assert saved_activities == []


# ---- Reconcile ---------------------------------------------------------------

def test_removed_from_list_advancing_triggers_a_reconcile(monkeypatch):
    stored = activities(tv_shows={"removed_from_list": "2026-08-01T00:00:00Z"})
    current = activities(tv_shows={"removed_from_list": "2026-08-05T00:00:00Z"})
    client = FakeClient(current, items={("shows", ""): [show_entry(1)]})
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": stored, "last_full_sync_at": 100, "last_activities_check_at": 0,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))

    db.reconcile_simkl_watched_cache.assert_called_once()
    args = db.reconcile_simkl_watched_cache.call_args[0]
    assert args[1] == "shows"
    assert args[2] == ["1"]


def test_a_static_removed_from_list_triggers_no_reconcile(monkeypatch):
    """The sweep is driven by an actual removal signal, not a timer."""
    stored = activities(tv_shows={"removed_from_list": "2026-08-01T00:00:00Z"})
    client = FakeClient(activities(tv_shows={"removed_from_list": "2026-08-01T00:00:00Z"}))
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": stored, "last_full_sync_at": 100, "last_activities_check_at": 0,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    db.reconcile_simkl_watched_cache.assert_not_called()


def _removal_sweep(monkeypatch, entries):
    """Run a sync whose only work is a removal sweep returning ``entries``."""
    stored = activities(tv_shows={"removed_from_list": "2026-08-01T00:00:00Z"})
    current = activities(tv_shows={"removed_from_list": "2026-08-05T00:00:00Z"})
    client = FakeClient(current, items={("shows", ""): entries})
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": stored, "last_full_sync_at": 100, "last_activities_check_at": 0,
    }
    asyncio.run(sync.ensure_synced(LINK, "tok"))
    return db


def test_an_emptied_list_is_swept_because_that_is_a_real_removal(monkeypatch):
    """{} from Simkl means the list is empty, and the cache should follow."""
    db = _removal_sweep(monkeypatch, [])
    db.reconcile_simkl_watched_cache.assert_called_once()
    assert db.reconcile_simkl_watched_cache.call_args[0][2] == []


def test_an_unreadable_sweep_response_does_not_wipe_the_cache(monkeypatch):
    """Entries we cannot read are not evidence that the library is empty.

    Deltas only re-add a title once its own timestamp moves, so deleting on a
    misread response would outlive the response itself.
    """
    db = _removal_sweep(monkeypatch, [{"unexpected": "shape"}, {"also": "wrong"}])
    db.reconcile_simkl_watched_cache.assert_not_called()


def test_a_skipped_sweep_keeps_the_old_removal_clock_so_it_retries(monkeypatch):
    """Storing the new timestamp would consume the only retry signal."""
    db = _removal_sweep(monkeypatch, [{"unexpected": "shape"}])

    saved = [
        call for call in db.update_simkl_sync_state.call_args_list
        if call.kwargs.get("activities") is not None
    ]
    stored_activities = saved[-1].kwargs["activities"]
    assert stored_activities["tv_shows"]["removed_from_list"] == "2026-08-01T00:00:00Z"


def test_a_completed_sweep_advances_the_removal_clock(monkeypatch):
    db = _removal_sweep(monkeypatch, [show_entry(1)])

    saved = [
        call for call in db.update_simkl_sync_state.call_args_list
        if call.kwargs.get("activities") is not None
    ]
    stored_activities = saved[-1].kwargs["activities"]
    assert stored_activities["tv_shows"]["removed_from_list"] == "2026-08-05T00:00:00Z"


def test_a_skipped_sweep_leaves_other_types_clocks_alone(monkeypatch):
    """Holding one type back must not roll the rest of the payload back too."""
    stored = activities(
        tv_shows={"removed_from_list": "2026-08-01T00:00:00Z"},
        movies={"removed_from_list": "2026-08-01T00:00:00Z"},
    )
    current = activities(
        tv_shows={"removed_from_list": "2026-08-05T00:00:00Z"},
        movies={"removed_from_list": "2026-08-05T00:00:00Z"},
    )
    client = FakeClient(current, items={
        ("shows", ""): [{"unexpected": "shape"}],
        ("movies", ""): [{"movie": {"ids": {"simkl": 5}}}],
    })
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": stored, "last_full_sync_at": 100, "last_activities_check_at": 0,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))

    saved = [
        call for call in db.update_simkl_sync_state.call_args_list
        if call.kwargs.get("activities") is not None
    ][-1].kwargs["activities"]
    assert saved["tv_shows"]["removed_from_list"] == "2026-08-01T00:00:00Z"
    assert saved["movies"]["removed_from_list"] == "2026-08-05T00:00:00Z"


# ---- First sync of an empty account ------------------------------------------

def test_an_empty_library_still_records_its_first_sync(monkeypatch):
    """Otherwise the UI says "linked but never synced" forever.

    A fresh Simkl account reports null for every bucket, so the sync plans no
    work at all — which is indistinguishable from "nothing changed" unless the
    first sync is recorded on the way out.
    """
    client = FakeClient(activities())
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    assert asyncio.run(sync.ensure_synced(LINK, "tok")) is True

    full_syncs = [
        call for call in db.update_simkl_sync_state.call_args_list
        if call.kwargs.get("mark_full_sync")
    ]
    assert len(full_syncs) == 1


def test_an_unchanged_library_does_not_re_record_a_full_sync(monkeypatch):
    """The empty-account path must not fire again on every later run."""
    stored = activities(tv_shows={"watching": "2026-08-05T21:27:57Z"})
    client = FakeClient(stored)
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": stored, "last_full_sync_at": 100, "last_activities_check_at": 0,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))

    assert not [
        call for call in db.update_simkl_sync_state.call_args_list
        if call.kwargs.get("activities") is not None or call.kwargs.get("mark_full_sync")
    ]


# ---- Normalization -----------------------------------------------------------

def test_anime_folds_to_tv_or_movie_based_on_anime_type():
    sync = SimklWatchHistorySync("cid", db=MagicMock())
    entries = [
        show_entry(1, anime_type="tv"),
        show_entry(2, anime_type="movie"),
        show_entry(3),
    ]
    items, _ = sync._normalize_entries(entries, "anime")

    assert [i["media_type"] for i in items] == ["tv", "movie", "tv"]
    assert all(i["simkl_type"] == "anime" for i in items)


def test_anime_entries_are_unwrapped_from_the_show_key_like_tv():
    sync = SimklWatchHistorySync("cid", db=MagicMock())
    items, skipped = sync._normalize_entries([show_entry(38960, tmdb="42509")], "anime")

    assert skipped == 0
    assert items[0]["tmdb_id"] == "42509"
    assert items[0]["title"] == "Show 38960"


def test_movies_are_unwrapped_from_the_movie_key():
    sync = SimklWatchHistorySync("cid", db=MagicMock())
    entry = {
        "last_watched_at": "2024-01-03T16:57:27Z", "status": "completed",
        "movie": {"title": "LOTR", "year": 2001, "ids": {"simkl": 53226, "tmdb": "120"}},
    }
    items, _ = sync._normalize_entries([entry], "movies")

    assert items[0]["media_type"] == "movie"
    assert items[0]["tmdb_id"] == "120"
    assert items[0]["title"] == "LOTR"


def test_last_watched_at_is_converted_to_epoch_seconds():
    expected = int(datetime(2026, 5, 9, 21, 22, 45, tzinfo=timezone.utc).timestamp())
    sync = SimklWatchHistorySync("cid", db=MagicMock())
    items, _ = sync._normalize_entries([show_entry(1, watched="2026-05-09T21:22:45Z")], "shows")
    assert items[0]["last_watched_at"] == expected


def test_a_naive_timestamp_is_read_as_utc_not_local_time():
    """Simkl always sends UTC; interpreting it locally would shift seed ordering."""
    expected = int(datetime(2026, 5, 9, 21, 22, 45, tzinfo=timezone.utc).timestamp())
    assert SimklWatchHistorySync._parse_iso("2026-05-09T21:22:45") == expected


def test_an_unparseable_timestamp_becomes_zero_rather_than_raising():
    assert SimklWatchHistorySync._parse_iso("not-a-date") == 0
    assert SimklWatchHistorySync._parse_iso(None) == 0


def test_a_missing_last_watched_at_falls_back_to_the_watchlist_date():
    sync = SimklWatchHistorySync("cid", db=MagicMock())
    entry = show_entry(1, watched=None)
    entry["added_to_watchlist_at"] = "2026-08-05T02:20:43Z"
    items, _ = sync._normalize_entries([entry], "shows")
    assert items[0]["last_watched_at"] > 0


def test_entries_without_a_simkl_id_are_counted_as_skipped():
    sync = SimklWatchHistorySync("cid", db=MagicMock())
    items, skipped = sync._normalize_entries([{"show": {"ids": {}}}, "junk"], "shows")
    assert items == []
    assert skipped == 2


def test_entries_without_a_tmdb_id_never_reach_the_cache(monkeypatch):
    """A row with no TMDb id cannot seed or exclude anything downstream."""
    current = activities(tv_shows={"watching": "2026-08-05T21:27:57Z"})
    entry = show_entry(1, tmdb=None)
    entry["show"]["ids"] = {"simkl": 1}
    client = FakeClient(current, items={("shows", "watching"): [entry]})
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    asyncio.run(sync.ensure_synced(LINK, "tok"))
    db.upsert_simkl_watched_cache.assert_called_once_with(7, [])


# ---- TVDb -> TMDb fallback ---------------------------------------------------

def _unmapped(tvdb_id):
    """A normalized item Simkl gave a TVDb id but no TMDb id."""
    return {"simkl_id": tvdb_id, "tmdb_id": None, "tvdb_id": tvdb_id}


def make_tvdb_sync(monkeypatch, resolver):
    """A sync whose TVDb lookup is `resolver`, recording each id it is asked."""
    sync = SimklWatchHistorySync("cid", db=MagicMock(), tmdb_api_key="tmdb-key")
    asked = []

    async def fake_lookup(_session, tvdb_id):
        asked.append(tvdb_id)
        return resolver(tvdb_id)

    monkeypatch.setattr(sync, "_find_tmdb_from_tvdb", fake_lookup)
    return sync, asked


def test_unmapped_entries_are_resolved_through_tvdb(monkeypatch):
    sync, asked = make_tvdb_sync(monkeypatch, lambda tvdb_id: f"tmdb-{tvdb_id}")
    items = asyncio.run(sync._resolve_missing_tmdb_ids([_unmapped("900"), _unmapped("901")]))

    assert asked == ["900", "901"]
    assert [i["tmdb_id"] for i in items] == ["tmdb-900", "tmdb-901"]


def test_a_repeated_tvdb_id_is_only_looked_up_once(monkeypatch):
    """The same title reappears across status buckets within one sync."""
    sync, asked = make_tvdb_sync(monkeypatch, lambda tvdb_id: "555")
    asyncio.run(sync._resolve_missing_tmdb_ids([_unmapped("900")]))
    asyncio.run(sync._resolve_missing_tmdb_ids([_unmapped("900"), _unmapped("901")]))

    assert asked == ["900", "901"]


def test_a_failed_lookup_is_remembered_so_it_is_not_retried_per_bucket(monkeypatch):
    """Unresolvable titles are the common case, and the costly one to retry."""
    sync, asked = make_tvdb_sync(monkeypatch, lambda _tvdb_id: None)
    items = asyncio.run(sync._resolve_missing_tmdb_ids([_unmapped("900")]))
    asyncio.run(sync._resolve_missing_tmdb_ids([_unmapped("900")]))

    assert asked == ["900"]
    assert items[0]["tmdb_id"] is None


def test_the_fallback_is_skipped_entirely_without_a_tmdb_key(monkeypatch):
    sync = SimklWatchHistorySync("cid", db=MagicMock(), tmdb_api_key="")
    called = False

    async def fake_lookup(*_args):
        nonlocal called
        called = True

    monkeypatch.setattr(sync, "_find_tmdb_from_tvdb", fake_lookup)
    asyncio.run(sync._resolve_missing_tmdb_ids([_unmapped("900")]))
    assert called is False


def test_lookups_stay_within_the_concurrency_bound(monkeypatch):
    """A first anime sync can leave hundreds unmapped; TMDb should not see them at once."""
    sync = SimklWatchHistorySync("cid", db=MagicMock(), tmdb_api_key="tmdb-key")
    in_flight = 0
    peak = 0

    async def fake_lookup(_session, tvdb_id):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return None

    monkeypatch.setattr(sync, "_find_tmdb_from_tvdb", fake_lookup)
    asyncio.run(sync._resolve_missing_tmdb_ids([_unmapped(str(i)) for i in range(50)]))

    assert peak <= SimklWatchHistorySync.TVDB_LOOKUP_CONCURRENCY


# ---- Failure handling --------------------------------------------------------

def test_an_auth_error_propagates_so_the_link_can_be_flagged(monkeypatch):
    client = FakeClient(activities(), raise_on_activities=SimklAuthError("401"))
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": None, "last_activities_check_at": None,
    }

    with pytest.raises(SimklAuthError):
        asyncio.run(sync.ensure_synced(LINK, "tok"))


def test_a_transient_failure_falls_back_to_stale_cache(monkeypatch):
    client = FakeClient(activities(), raise_on_activities=SimklError("503"))
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": 1, "last_activities_check_at": 0,
    }
    db.get_simkl_watched_cache.return_value = [{"tmdb_id": "1"}]

    assert asyncio.run(sync.ensure_synced(LINK, "tok")) is True


def test_a_transient_failure_with_an_empty_cache_reports_unusable(monkeypatch):
    client = FakeClient(activities(), raise_on_activities=SimklError("503"))
    sync, db = make_sync(monkeypatch, client)
    db.get_simkl_sync_state.return_value = {
        "activities": {}, "last_full_sync_at": 1, "last_activities_check_at": 0,
    }
    db.get_simkl_watched_cache.return_value = []

    assert asyncio.run(sync.ensure_synced(LINK, "tok")) is False


# ---- Status split ------------------------------------------------------------

def test_seeds_span_in_progress_titles_while_exclusions_stay_finished_only():
    """On the live account this is 109 seed titles against 5 completed shows."""
    assert SEED_STATUSES == ("watching", "completed")
    assert EXCLUSION_STATUSES == ("completed",)
    assert "watching" not in EXCLUSION_STATUSES
