"""Safety tests for the cleanup job: it deletes media, so every guard here protects user files."""
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.jobs import cleanup_automation as ca


def _candidates(count):
    return [{"tmdb_id": str(i), "media_type": "movie", "title": f"T{i}"} for i in range(1, count + 1)]


class FakeDB:
    """Minimal DatabaseManager stand-in recording what the job writes."""

    def __init__(self, candidates, dry_run=False, fail_log_actions=(), recent=None):
        self._candidates = candidates
        self._dry_run = dry_run
        self.fail_log_actions = set(fail_log_actions)
        self.recent = recent or set()
        self.logs, self.updates, self.deleted_rows = [], [], []
        self.state = {}  # persisted last_run_status / last_run_summary, like the real settings row

    def get_cleanup_settings(self):
        return {"enabled": True, "dry_run": self._dry_run, "grace_days": 7, **self.state}

    def get_suggestarr_requests_older_than(self, cutoff):
        return self._candidates

    def get_recently_watched_titles(self, since):
        return self.recent

    def update_cleanup_settings(self, **kwargs):
        self.updates.append(kwargs)
        self.state.update({k: v for k, v in kwargs.items() if k.startswith("last_run_")})

    def add_cleanup_log(self, **kwargs):
        if kwargs["action"] in self.fail_log_actions:
            raise RuntimeError("database is locked")
        self.logs.append(kwargs)

    def delete_request_row(self, tmdb_id, media_type):
        self.deleted_rows.append((tmdb_id, media_type))


ENV = {"SELECTED_SERVICE": "plex", "PLEX_API_URL": "http://plex", "PLEX_TOKEN": "t",
       "SEER_API_URL": "http://seer", "SEER_TOKEN": "s"}


async def run_job(db, favorite_map, env=None, **kwargs):
    """Run execute_cleanup_job against fakes; returns (result, seer_client_mock)."""
    seer = MagicMock()
    seer.delete_media_file_by_tmdb = AsyncMock(return_value=True)
    seer.close = AsyncMock()
    with patch.object(ca, "DatabaseManager", return_value=db), \
         patch.object(ca.ConfigService, "get_runtime_config", return_value=env or ENV), \
         patch.object(ca, "get_request_backend", return_value="seer"), \
         patch.object(ca, "_build_favorite_map", AsyncMock(return_value=favorite_map)), \
         patch.object(ca, "SeerClient", return_value=seer):
        result = await ca.execute_cleanup_job(force_run=True, **kwargs)
    return result, seer


class TestFavoriteMaps(unittest.IsolatedAsyncioTestCase):
    async def test_jellyfin_without_any_user_aborts_instead_of_listing_nothing_as_favorite(self):
        client = MagicMock()
        client.get_all_library_items = AsyncMock(return_value={"movie": [{"tmdb_id": "1"}]})
        client.get_all_users = AsyncMock(return_value=[])
        client.libraries = []
        client.close = AsyncMock()
        env = {"JELLYFIN_API_URL": "http://j", "JELLYFIN_TOKEN": "t", "SELECTED_USERS": []}
        with patch.object(ca, "JellyfinClient", return_value=client):
            with self.assertRaises(RuntimeError):
                await ca._build_jellyfin_favorite_map(env)
        client.close.assert_awaited()

    async def test_plex_title_in_two_libraries_keeps_the_favorite_rating(self):
        for order in ([10.0, 0.0], [0.0, 10.0]):
            plex = MagicMock()
            plex.get_all_library_items = AsyncMock(return_value={"movie": [
                {"tmdb_id": "603", "userRating": order[0]}, {"tmdb_id": "603", "userRating": order[1]}]})
            plex.close = AsyncMock()
            env = {"PLEX_API_URL": "http://p", "PLEX_TOKEN": "t"}
            with patch.object(ca, "PlexClient", return_value=plex):
                ratings = await ca._build_plex_favorite_map(env)
            self.assertEqual(ratings[("movie", "603")], 10.0, order)


class TestPerCandidateIsolation(unittest.IsolatedAsyncioTestCase):
    async def test_log_failure_in_a_non_deletion_branch_does_not_stop_later_candidates(self):
        db = FakeDB(_candidates(2), fail_log_actions={"kept_favorited"})
        ratings = {("movie", "1"): 10.0, ("movie", "2"): 0.0}
        result, seer = await run_job(db, ratings)
        seer.delete_media_file_by_tmdb.assert_awaited_once_with(2, "movie")
        self.assertEqual(db.deleted_rows, [("2", "movie")])
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(db.updates[-1]["last_run_status"], "completed_with_errors")

    async def test_dry_run_with_errors_is_not_reported_as_clean(self):
        db = FakeDB(_candidates(2), dry_run=True, fail_log_actions={"kept_favorited"})
        result, _ = await run_job(db, {("movie", "1"): 10.0, ("movie", "2"): 0.0})
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(db.updates[-1]["last_run_status"], "completed_with_errors")

    async def test_db_error_after_a_delete_does_not_abort_the_run_and_closes_clients(self):
        db = FakeDB(_candidates(2))
        db.delete_request_row = MagicMock(side_effect=[RuntimeError("locked"), None])
        ratings = {("movie", "1"): 0.0, ("movie", "2"): 0.0}
        result, seer = await run_job(db, ratings)
        self.assertEqual(seer.delete_media_file_by_tmdb.await_count, 2)
        seer.close.assert_awaited()
        self.assertEqual(result["status"], "completed_with_errors")

    async def test_unexpected_error_still_closes_clients(self):
        db = FakeDB(_candidates(1))
        db.add_cleanup_log = MagicMock(side_effect=KeyboardInterrupt)  # not an Exception: must still close
        with self.assertRaises(KeyboardInterrupt):
            await run_job(db, {("movie", "1"): 0.0})


class FakeArr:
    """ArrClient stand-in: `owned` maps tmdb_id -> find_owned status."""
    instances = []

    def __init__(self, service, url, token):
        self.service = service
        self.owned = {}
        self.deleted = []
        self.close = AsyncMock(side_effect=self.close_effect)
        self.close_effect_error = None
        FakeArr.instances.append(self)

    async def close_effect(self):
        if self.close_effect_error:
            raise self.close_effect_error

    async def find_owned(self, tmdb_id):
        return self.owned.get(str(tmdb_id), "not_found"), None

    async def delete(self, tmdb_id):
        status = self.owned.get(str(tmdb_id), "not_found")
        if status != "ok":  # like the real client: untagged or missing titles are never deleted
            return status
        self.deleted.append(str(tmdb_id))
        return "deleted"


async def run_arr_job(db, favorite_map, owned_by_type, **kwargs):
    FakeArr.instances = []
    env = {"SELECTED_SERVICE": "plex", "PLEX_API_URL": "http://p", "PLEX_TOKEN": "t",
           "RADARR_API_URL": "http://r", "RADARR_TOKEN": "x"}
    instances = {"radarr": ("RADARR_API_URL", "RADARR_TOKEN", "movie")}

    def make(service, url, token):
        client = FakeArr(service, url, token)
        client.owned = owned_by_type
        return client

    with patch.object(ca, "DatabaseManager", return_value=db),          patch.object(ca.ConfigService, "get_runtime_config", return_value=env),          patch.object(ca, "get_request_backend", return_value="arr"),          patch.object(ca, "ARR_INSTANCES", instances),          patch.object(ca, "_build_favorite_map", AsyncMock(return_value=favorite_map)),          patch.object(ca, "ArrClient", side_effect=make):
        return await ca.execute_cleanup_job(force_run=True, **kwargs)


class TestDirectDeliveryBreaker(unittest.IsolatedAsyncioTestCase):
    async def test_untagged_or_missing_titles_do_not_trip_the_breaker(self):
        db = FakeDB(_candidates(30))
        ratings = {("movie", str(i)): 0.0 for i in range(1, 31)}
        owned = {str(i): "not_tagged" for i in range(1, 25)}  # 24 untagged, 6 not in Radarr
        result = await run_arr_job(db, ratings, owned)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(FakeArr.instances[0].deleted, [])

    async def test_only_tagged_titles_count_towards_the_breaker(self):
        db = FakeDB(_candidates(30))
        ratings = {("movie", str(i)): 0.0 for i in range(1, 31)}
        owned = {str(i): "ok" for i in range(1, 22)}  # 21 tagged -> blocked
        result = await run_arr_job(db, ratings, owned)
        self.assertEqual(result["status"], "blocked_large_run")
        self.assertEqual(FakeArr.instances[0].deleted, [])
        FakeArr.instances[0].close.assert_awaited()

    async def test_one_failing_close_does_not_hide_the_summary(self):
        db = FakeDB(_candidates(1))
        FakeArr.instances = []

        async def go():
            return await run_arr_job(db, {("movie", "1"): 0.0}, {"1": "ok"})
        with patch.object(FakeArr, "close_effect", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await go()
        self.assertEqual(result["status"], "ok")
        self.assertIn("deleted=1", result["summary"])
        self.assertEqual(db.updates[-1]["last_run_status"], "ok")


class TestSeerConfigCheck(unittest.IsolatedAsyncioTestCase):
    async def test_missing_seer_config_in_a_real_run_is_reported_not_raised(self):
        db = FakeDB(_candidates(1))
        env = {k: v for k, v in ENV.items() if not k.startswith("SEER")}
        result, _ = await run_job(db, {("movie", "1"): 0.0}, env=env)
        self.assertEqual(result["status"], "not_configured")


class TestSafetyBreaker(unittest.IsolatedAsyncioTestCase):
    def test_threshold_boundaries(self):
        block = ca._is_large_run
        for deletions, total, expected in [
            (20, 100, False), (21, 100, True), (20, 20, True), (5, 16, True),
            (5, 17, False), (4, 4, False), (10, 500, False), (0, 0, False),
        ]:
            self.assertEqual(block(deletions, total), expected, (deletions, total))

    async def test_large_run_deletes_nothing_and_is_reported(self):
        db = FakeDB(_candidates(21))
        ratings = {("movie", str(i)): 0.0 for i in range(1, 22)}
        result, seer = await run_job(db, ratings)
        seer.delete_media_file_by_tmdb.assert_not_awaited()
        self.assertEqual(result["status"], "blocked_large_run")
        self.assertEqual(db.updates[-1]["last_run_status"], "blocked_large_run")

    async def test_confirm_large_runs_the_blocked_run(self):
        db = FakeDB(_candidates(21))
        ratings = {("movie", str(i)): 0.0 for i in range(1, 22)}
        blocked, _ = await run_job(db, ratings)
        self.assertEqual(blocked["status"], "blocked_large_run")
        result, seer = await run_job(db, ratings, confirm_large=True)
        self.assertEqual(seer.delete_media_file_by_tmdb.await_count, 21)
        self.assertEqual(result["status"], "ok")

    async def test_confirmation_does_not_cover_a_bigger_run(self):
        db = FakeDB(_candidates(21))
        await run_job(db, {("movie", str(i)): 0.0 for i in range(1, 22)})  # blocked at 21
        db._candidates = _candidates(40)  # more titles became eligible meanwhile
        result, seer = await run_job(db, {("movie", str(i)): 0.0 for i in range(1, 41)}, confirm_large=True)
        seer.delete_media_file_by_tmdb.assert_not_awaited()
        self.assertEqual(result["status"], "blocked_large_run")
        self.assertIn("would delete 40 of 40", result["message"])

    async def test_confirmation_without_a_previous_block_is_ignored(self):
        db = FakeDB(_candidates(21))
        result, seer = await run_job(db, {("movie", str(i)): 0.0 for i in range(1, 22)}, confirm_large=True)
        seer.delete_media_file_by_tmdb.assert_not_awaited()
        self.assertEqual(result["status"], "blocked_large_run")

    async def test_dry_run_is_never_blocked_but_reports_it(self):
        db = FakeDB(_candidates(21), dry_run=True)
        ratings = {("movie", str(i)): 0.0 for i in range(1, 22)}
        result, _ = await run_job(db, ratings)
        self.assertEqual(result["status"], "ok")
        self.assertIn("would_block", result["summary"])

    async def test_favorites_do_not_count_as_deletions(self):
        db = FakeDB(_candidates(40))
        ratings = {("movie", str(i)): (10.0 if i > 5 else 0.0) for i in range(1, 41)}
        result, seer = await run_job(db, ratings)  # only 5 of 40 would be deleted: 12.5%
        self.assertEqual(seer.delete_media_file_by_tmdb.await_count, 5)


class TestRecentActivityKeep(unittest.IsolatedAsyncioTestCase):
    async def test_recently_watched_title_is_kept(self):
        db = FakeDB(_candidates(2), recent={("movie", "1")})
        ratings = {("movie", "1"): 0.0, ("movie", "2"): 0.0}
        result, seer = await run_job(db, ratings)
        seer.delete_media_file_by_tmdb.assert_awaited_once_with(2, "movie")
        self.assertIn("kept_recent_activity", [row["action"] for row in db.logs])


class TestRecentlyWatchedQuery(unittest.TestCase):
    """watched_at is written by Python (ISO 'T' text on SQLite), so the cutoff is compared as a datetime."""

    def test_same_day_boundary(self):
        import sqlite3
        from api_service.db.components.cleanup_mixin import CleanupMixin
        conn = sqlite3.connect(":memory:")
        sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())  # what DatabaseManager registers
        conn.execute("CREATE TABLE recap_titles (media_type TEXT, tmdb_id TEXT, watched_at TIMESTAMP)")
        conn.executemany("INSERT INTO recap_titles VALUES ('movie', ?, ?)",
                         [("1", "2026-11-05T11:00:00"), ("2", "2026-11-05T13:00:00"), ("3", None)])

        class Db(CleanupMixin):
            db_type = "sqlite"

            def get_connection(self):
                class Ctx:
                    def __enter__(self_inner):
                        return conn

                    def __exit__(self_inner, *args):
                        return False
                return Ctx()

        self.assertEqual(Db().get_recently_watched_titles(datetime(2026, 11, 5, 12, 0, 0)), {("movie", "2")})


if __name__ == "__main__":
    unittest.main()
