"""Tests for centralized filter normalization helpers."""

import unittest

from api_service.services.filter_normalization import build_tmdb_params, normalize_filters


class TestNormalizeFilters(unittest.TestCase):

    def test_normalizes_aliases_to_canonical_fields(self):
        filters = {
            "release_year_gte": "1995",
            "release_year_lte": "2001",
            "vote_average_gte": "7.5",
            "with_original_language": "EN",
            "with_genres": [28, "Thriller"],
        }

        normalized = normalize_filters(filters)

        self.assertEqual(normalized["year_from"], 1995)
        self.assertEqual(normalized["year_to"], 2001)
        self.assertEqual(normalized["min_rating"], 7.5)
        self.assertEqual(normalized["language"], "en")
        self.assertEqual(normalized["genres"], [28, 53])

    def test_normalizes_genre_name_list_to_tmdb_ids(self):
        normalized = normalize_filters({"genres": ["Action", "Science Fiction", "Unknown"]})
        self.assertEqual(normalized["genres"], [28, 878])


class TestBuildTmdbParams(unittest.TestCase):

    def test_builds_tmdb_params_from_canonical_filters(self):
        canonical = {
            "year_from": 2000,
            "year_to": 2005,
            "genres": [28, 53],
            "min_rating": 7.2,
            "language": "it",
        }

        params = build_tmdb_params(canonical)

        self.assertEqual(params["primary_release_date_gte"], "2000-01-01")
        self.assertEqual(params["primary_release_date_lte"], "2005-12-31")
        self.assertEqual(params["with_genres"], "28|53")
        self.assertEqual(params["vote_average_gte"], 7.2)
        self.assertEqual(params["with_original_language"], "it")

    def test_builds_tmdb_params_from_legacy_aliases(self):
        params = build_tmdb_params(
            {
                "release_year_gte": "2012",
                "release_year_lte": "2018",
                "vote_average_gte": 6.5,
                "with_genres": "Comedy,Crime",
                "original_language": "en",
            }
        )

        self.assertEqual(params["primary_release_date_gte"], "2012-01-01")
        self.assertEqual(params["primary_release_date_lte"], "2018-12-31")
        self.assertEqual(params["vote_average_gte"], 6.5)
        self.assertEqual(params["with_genres"], "35|80")
        self.assertEqual(params["with_original_language"], "en")
