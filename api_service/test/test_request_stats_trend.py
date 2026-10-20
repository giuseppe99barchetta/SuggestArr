"""Tests for the previous-period counts behind the Home trend figures."""
from datetime import datetime
from unittest.mock import patch

from api_service.db import database_manager as dm_mod
from api_service.db.components.ai_search_mixin import previous_period_counts
from api_service.db.database_manager import DatabaseManager

# Wednesday 2030-01-16, 15:00 UTC.
NOW = datetime(2030, 1, 16, 15, 0)


def test_previous_periods_stop_at_the_same_elapsed_time():
    moments = [
        datetime(2030, 1, 15, 10, 0),   # yesterday before 15:00 -> counts for today
        datetime(2030, 1, 15, 18, 0),   # yesterday after 15:00 -> too late in the day
        datetime(2030, 1, 8, 9, 0),     # last Tuesday -> within last week's first 2.6 days
        datetime(2030, 1, 10, 9, 0),    # last Thursday -> beyond the same point
        datetime(2029, 12, 3, 9, 0),    # early December -> within last month's first 15.6 days
        datetime(2029, 12, 20, 9, 0),   # late December -> beyond
    ]
    assert previous_period_counts(moments, NOW) == {'today': 1, 'this_week': 1, 'this_month': 1}


def test_previous_month_is_capped_at_its_own_end():
    # On the 31st, the previous month (February) ends before 31 elapsed days do.
    now = datetime(2030, 3, 31, 12, 0)
    moments = [datetime(2030, 2, 28, 23, 0), datetime(2030, 3, 1, 1, 0)]
    assert previous_period_counts(moments, now)['this_month'] == 1


def test_stats_include_previous_counts(tmp_path):
    db_file = str(tmp_path / "stats.db")
    with (
        patch.object(dm_mod, "DB_PATH", db_file),
        patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}),
    ):
        DatabaseManager._instance = None
        db = DatabaseManager()
        with db.get_connection() as conn:
            conn.execute("INSERT INTO requests (tmdb_request_id, media_type, requested_by, requested_at) "
                         "VALUES ('1', 'movie', 'SuggestArr', datetime('now', '-1 day'))")
            conn.commit()
        stats = db.get_requests_stats()
    DatabaseManager._instance = None
    assert set(stats['previous']) == {'today', 'this_week', 'this_month'}
    assert stats['previous']['today'] == 1
