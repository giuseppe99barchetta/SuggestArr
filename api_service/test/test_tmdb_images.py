"""Tests for TMDB image URL normalization."""

from api_service.utils.tmdb_images import tmdb_image_url


def test_builds_poster_url_from_relative_path():
    assert tmdb_image_url("/abc.jpg", "w500") == "https://image.tmdb.org/t/p/w500/abc.jpg"


def test_builds_backdrop_url_from_relative_path():
    assert tmdb_image_url("/bg.jpg", "w1280") == "https://image.tmdb.org/t/p/w1280/bg.jpg"


def test_returns_absolute_url_unchanged():
    url = "https://image.tmdb.org/t/p/w500/abc.jpg"
    assert tmdb_image_url(url, "w500") == url


def test_returns_none_for_empty_path():
    assert tmdb_image_url(None, "w500") is None
    assert tmdb_image_url("", "w500") is None
