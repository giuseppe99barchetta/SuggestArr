"""
Tests for cron expression parsing in cron_jobs.py and JobManager._cron_to_trigger / _preset_to_trigger.

Key regression covered: APScheduler OR-logic bug where CronTrigger(day='1', day_of_week='*')
fires every day instead of only on the 1st of the month.
"""
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from apscheduler.triggers.cron import CronTrigger

from api_service.config.cron_jobs import parse_cron_expression


def _next_fire(trigger: CronTrigger, now: datetime) -> datetime:
    """Return the next fire time for a trigger after the given 'now'."""
    return trigger.get_next_fire_time(None, now)


class TestParseCronExpression(unittest.TestCase):
    """Tests for api_service.config.cron_jobs.parse_cron_expression."""

    def test_returns_cron_trigger(self):
        trigger = parse_cron_expression('0 0 * * *')
        self.assertIsInstance(trigger, CronTrigger)

    def test_daily_midnight(self):
        trigger = parse_cron_expression('0 0 * * *')
        now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertEqual(nxt.hour, 0)
        self.assertEqual(nxt.minute, 0)
        self.assertEqual(nxt.day, 16)

    def test_first_of_month_does_not_fire_daily(self):
        """Regression: '0 0 1 * *' must NOT fire every day."""
        trigger = parse_cron_expression('0 0 1 * *')
        # now = 2nd of Feb 2026 at 01:00
        now = datetime(2026, 2, 2, 1, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        # Must jump to 1st March, not 3rd February
        self.assertEqual(nxt.month, 3, "Expected next fire in March, not next day")
        self.assertEqual(nxt.day, 1)
        self.assertEqual(nxt.hour, 0)

    def test_specific_day_of_week(self):
        """'0 0 * * mon' must fire only on Monday."""
        # Use named day to avoid APScheduler vs standard-cron numeric offset ambiguity
        trigger = parse_cron_expression('0 0 * * mon')
        # Wednesday 2026-02-18 — next Monday is 2026-02-23
        now = datetime(2026, 2, 18, 1, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertEqual(nxt.weekday(), 0)  # Python weekday: 0 = Monday

    def test_every_12_hours(self):
        trigger = parse_cron_expression('0 */12 * * *')
        now = datetime(2026, 2, 15, 1, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        # Fires at minute 0 of an hour that is a multiple of 12 (0 or 12)
        self.assertEqual(nxt.minute, 0)
        self.assertIn(nxt.hour % 12, [0])  # hour must be 0 or 12

    def test_invalid_expression_falls_back_to_daily(self):
        """A malformed expression should fall back to '0 0 * * *'."""
        trigger = parse_cron_expression('not a valid cron')
        self.assertIsInstance(trigger, CronTrigger)
        now = datetime(2026, 2, 15, 1, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        # Fallback is daily at midnight
        self.assertEqual(nxt.hour, 0)
        self.assertEqual(nxt.minute, 0)

    def test_none_expression_falls_back_to_daily(self):
        trigger = parse_cron_expression(None)
        self.assertIsInstance(trigger, CronTrigger)

    def test_empty_expression_falls_back_to_daily(self):
        trigger = parse_cron_expression('')
        self.assertIsInstance(trigger, CronTrigger)

    def test_monthly_on_15th(self):
        trigger = parse_cron_expression('0 8 15 * *')
        now = datetime(2026, 2, 16, 0, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertEqual(nxt.day, 15)
        self.assertEqual(nxt.hour, 8)
        self.assertEqual(nxt.month, 3)


class TestJobManagerCronTrigger(unittest.TestCase):
    """Tests for JobManager._cron_to_trigger and _preset_to_trigger."""

    def setUp(self):
        """Instantiate JobManager with mocked dependencies."""
        with patch('api_service.jobs.job_manager.JobRepository'):
            from api_service.jobs.job_manager import JobManager
            # Reset singleton so each test gets a fresh instance
            JobManager._instance = None
            self.manager = JobManager()

    def tearDown(self):
        from api_service.jobs.job_manager import JobManager
        JobManager._instance = None

    # --- _cron_to_trigger ---

    def test_cron_trigger_returns_cron_trigger_instance(self):
        trigger = self.manager._cron_to_trigger('0 0 * * *')
        self.assertIsInstance(trigger, CronTrigger)

    def test_cron_trigger_invalid_returns_none(self):
        trigger = self.manager._cron_to_trigger('bad expression')
        self.assertIsNone(trigger)

    def test_cron_trigger_wrong_parts_returns_none(self):
        trigger = self.manager._cron_to_trigger('0 0 *')
        self.assertIsNone(trigger)

    def test_cron_trigger_first_of_month_does_not_fire_daily(self):
        """Regression: '0 0 1 * *' must NOT fire every day."""
        trigger = self.manager._cron_to_trigger('0 0 1 * *')
        now = datetime(2026, 2, 2, 1, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertEqual(nxt.month, 3, "Expected next fire in March, not next day")
        self.assertEqual(nxt.day, 1)

    def test_cron_trigger_day_and_dow_both_wildcard(self):
        """'0 0 * * *' with both day and day_of_week as '*' fires daily."""
        trigger = self.manager._cron_to_trigger('0 0 * * *')
        now = datetime(2026, 2, 15, 1, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertEqual(nxt.day, 16)

    def test_cron_trigger_specific_month(self):
        """'0 0 1 6 *' fires on June 1st only."""
        trigger = self.manager._cron_to_trigger('0 0 1 6 *')
        now = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertEqual(nxt.month, 6)
        self.assertEqual(nxt.day, 1)

    # --- _preset_to_trigger ---

    def test_preset_daily(self):
        trigger = self.manager._preset_to_trigger('daily')
        self.assertIsInstance(trigger, CronTrigger)
        now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertEqual(nxt.hour, 0)
        self.assertEqual(nxt.minute, 0)

    def test_preset_weekly(self):
        trigger = self.manager._preset_to_trigger('weekly')
        self.assertIsInstance(trigger, CronTrigger)
        now = datetime(2026, 2, 17, 1, 0, 0, tzinfo=timezone.utc)  # Tuesday
        nxt = _next_fire(trigger, now)
        self.assertEqual(nxt.weekday(), 0)  # Monday

    def test_preset_every_12h(self):
        trigger = self.manager._preset_to_trigger('every_12h')
        self.assertIsInstance(trigger, CronTrigger)
        now = datetime(2026, 2, 15, 1, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertIn(nxt.hour, [0, 12])

    def test_preset_every_6h(self):
        trigger = self.manager._preset_to_trigger('every_6h')
        self.assertIsInstance(trigger, CronTrigger)
        now = datetime(2026, 2, 15, 1, 0, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        self.assertIn(nxt.hour, [0, 6, 12, 18])

    def test_preset_every_hour(self):
        trigger = self.manager._preset_to_trigger('every_hour')
        self.assertIsInstance(trigger, CronTrigger)
        now = datetime(2026, 2, 15, 1, 30, 0, tzinfo=timezone.utc)
        nxt = _next_fire(trigger, now)
        # Next fire must always land on the top of the hour
        self.assertEqual(nxt.minute, 0)
        self.assertGreater(nxt, now)

    def test_preset_unknown_returns_none(self):
        trigger = self.manager._preset_to_trigger('nonexistent_preset')
        self.assertIsNone(trigger)

    def test_preset_case_insensitive(self):
        trigger = self.manager._preset_to_trigger('DAILY')
        self.assertIsInstance(trigger, CronTrigger)

    # --- _create_trigger dispatch ---

    def test_create_trigger_dispatches_preset(self):
        trigger = self.manager._create_trigger('preset', 'daily')
        self.assertIsInstance(trigger, CronTrigger)

    def test_create_trigger_dispatches_cron(self):
        trigger = self.manager._create_trigger('cron', '0 0 1 * *')
        self.assertIsInstance(trigger, CronTrigger)

    def test_create_trigger_unknown_type_returns_none(self):
        trigger = self.manager._create_trigger('interval', '60')
        self.assertIsNone(trigger)


if __name__ == '__main__':
    unittest.main()
