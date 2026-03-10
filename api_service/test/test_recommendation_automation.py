"""Tests for recommendation year-range normalization in recommendation jobs."""

import unittest

from api_service.jobs.recommendation_automation import (
    _extract_year_from_filter_value,
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
