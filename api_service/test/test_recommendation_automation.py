"""Tests for recommendation jobs: year-range normalization, Seer discovery, library exclusion."""

import logging
import unittest
from unittest.mock import AsyncMock, MagicMock

from api_service.handler.jellyfin_handler import JellyfinHandler
from api_service.jobs.recommendation_automation import (
    RecommendationAutomation,
    _extract_year_from_filter_value,
    _resolve_honor_seer_discovery,
    _resolve_year_range_filters,
)


class TestRecommendationYearRangeParsing(unittest.TestCase):

    def test_extract_year_from_numeric_and_date_values(self):
        self.assertEqual(_extract_year_from_filter_value(2025), 2025)
        self.assertEqual(_extract_year_from_filter_value("2024"), 2024)
        self.assertEqual(_extract_year_from_filter_value("2023-05-01"), 2023)

    def test_extract_year_returns_none_for_empty_or_invalid(self):
        self.assertIsNone(_extract_year_from_filter_value(""))
        self.assertIsNone(_extract_year_from_filter_value(None))
        self.assertIsNone(_extract_year_from_filter_value("not-a-year"))

    def test_resolve_year_range_from_job_date_filters(self):
        job_filters = {
            "primary_release_date_gte": "2020-01-01",
            "primary_release_date_lte": "2024-12-31",
        }
        from_year, to_year = _resolve_year_range_filters(job_filters, {"FILTER_RELEASE_YEAR": "0"})
        self.assertEqual(from_year, 2020)
        self.assertEqual(to_year, 2024)

    def test_resolve_year_range_from_year_keys(self):
        job_filters = {"release_year_gte": "2021", "release_year_lte": "2022"}
        from_year, to_year = _resolve_year_range_filters(job_filters, {"FILTER_RELEASE_YEAR": "0"})
        self.assertEqual(from_year, 2021)
        self.assertEqual(to_year, 2022)

    def test_resolve_from_year_falls_back_to_global_filter(self):
        from_year, to_year = _resolve_year_range_filters({}, {"FILTER_RELEASE_YEAR": "2018"})
        self.assertEqual(from_year, 2018)
        self.assertIsNone(to_year)


class TestHonorSeerDiscoveryResolution(unittest.TestCase):

    def test_job_filter_overrides_global_true(self):
        value = _resolve_honor_seer_discovery(
            {"honor_jellyseer_discovery": True},
            {"HONOR_JELLYSEER_DISCOVERY": False},
        )
        self.assertTrue(value)

    def test_job_filter_overrides_global_false(self):
        value = _resolve_honor_seer_discovery(
            {"honor_jellyseer_discovery": False},
            {"HONOR_JELLYSEER_DISCOVERY": True},
        )
        self.assertFalse(value)

    def test_global_fallback_used_when_job_filter_missing(self):
        value = _resolve_honor_seer_discovery(
            {},
            {"HONOR_JELLYSEER_DISCOVERY": True},
        )
        self.assertTrue(value)


class TestSeerAvailabilityExclusion(unittest.IsolatedAsyncioTestCase):
    """Titles Seer reports as available are skipped even without a TMDB ID in Jellyfin."""

    USER = {"id": "user-1", "name": "Alice"}

    def _automation(self, exclude_downloaded=True):
        jellyfin_client = MagicMock()
        # The library holds Game of Thrones (1399), but Jellyfin only has a TVDB ID for it.
        jellyfin_client.existing_content = {"movie": [{"tmdb_id": "11"}], "tv": []}

        seer_client = MagicMock()
        seer_client.exclude_downloaded = exclude_downloaded
        seer_client.queue_context = {}
        seer_client.get_available_tmdb_ids = AsyncMock(return_value={"movie": set(), "tv": {"1399"}})
        seer_client.check_requests_exist_batch = AsyncMock(return_value=set())
        seer_client.request_media = AsyncMock(return_value=True)

        tmdb_client = MagicMock()
        tmdb_client.get_watch_providers = AsyncMock(return_value=(False, None))

        handler = JellyfinHandler(
            jellyfin_client, seer_client, tmdb_client, logging.getLogger("test"),
            max_similar_movie=2, max_similar_tv=2,
            selected_users=[self.USER], use_llm=False,
        )

        async def process_recent_items():
            await handler.request_similar_media(
                [{"id": 1399, "name": "Game of Thrones"}, {"id": 1396, "name": "Breaking Bad"}],
                "tv", 2, {"id": 22, "name": "Severance"}, self.USER,
            )

        handler.process_recent_items = process_recent_items

        automation = RecommendationAutomation()
        automation.job_id = 1
        automation.job_data = {"id": 1, "name": "Recommendations"}
        automation.repository = MagicMock()
        automation.media_handler = handler
        return automation, seer_client

    async def test_seer_available_titles_are_not_requested(self):
        automation, seer_client = self._automation()

        result = await automation.run()

        self.assertTrue(result.success)
        requested_ids = [call.kwargs["media"]["id"] for call in seer_client.request_media.await_args_list]
        self.assertEqual(requested_ids, [1396])
        seer_client.get_available_tmdb_ids.assert_awaited_once()

    async def test_seer_is_not_queried_when_exclude_downloaded_is_off(self):
        automation, seer_client = self._automation(exclude_downloaded=False)

        await automation.run()

        seer_client.get_available_tmdb_ids.assert_not_awaited()
