"""Tests for request source tag helpers."""
from api_service.services.request_sources import (
    DISCOVER_SOURCE,
    TRAKT_RECOMMENDATIONS_SOURCE,
    is_tmdb_metadata_source_id,
    request_source_title_sql,
)


def test_trakt_source_is_not_metadata_id():
    assert is_tmdb_metadata_source_id(TRAKT_RECOMMENDATIONS_SOURCE) is False
    assert is_tmdb_metadata_source_id(DISCOVER_SOURCE) is False
    assert is_tmdb_metadata_source_id("27205") is True
    assert is_tmdb_metadata_source_id("ai_search") is False


def test_request_source_title_sql_includes_trakt_label():
    sql = request_source_title_sql("r")
    assert "trakt_recommendations" in sql
    assert "Trakt Recommendations" in sql
    assert "discover" in sql
    assert "Discover" in sql
