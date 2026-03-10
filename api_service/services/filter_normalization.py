"""Centralized filter normalization and TMDb discover parameter helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


TMDB_GENRE_MAP = {
    "Action": 28,
    "Adventure": 12,
    "Animation": 16,
    "Comedy": 35,
    "Crime": 80,
    "Documentary": 99,
    "Drama": 18,
    "Family": 10751,
    "Fantasy": 14,
    "History": 36,
    "Horror": 27,
    "Music": 10402,
    "Mystery": 9648,
    "Romance": 10749,
    "Sci-Fi": 878,
    "Science Fiction": 878,
    "Thriller": 53,
    "War": 10752,
    "Western": 37,
}

_GENRE_NAME_TO_ID = {name.lower(): genre_id for name, genre_id in TMDB_GENRE_MAP.items()}


def _parse_int(value: Any) -> Optional[int]:
    """Parse an integer from common scalar input forms."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return int(raw)
        if len(raw) >= 4 and raw[:4].isdigit():
            return int(raw[:4])

    return None


def _parse_float(value: Any) -> Optional[float]:
    """Parse a float from common scalar input forms."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    return None


def _normalize_language(value: Any) -> Optional[str]:
    """Normalize language to lower-case 2/3-char alphabetic code when possible."""
    if isinstance(value, list):
        if not value:
            return None
        return _normalize_language(value[0])

    if isinstance(value, dict):
        for key in ("iso_639_1", "id", "code"):
            if key in value:
                return _normalize_language(value.get(key))
        return None

    if value is None:
        return None

    text = str(value).strip().lower()
    if not text or text in ("any", "all", "any language"):
        return None
    if text.isalpha() and len(text) in (2, 3):
        return text
    return None


def _normalize_genres(value: Any) -> Optional[List[int]]:
    """Normalize genre filters into TMDb numeric genre IDs."""
    if value is None:
        return None

    values = value
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",") if v.strip()]
    elif isinstance(values, (int, float)):
        values = [values]
    elif not isinstance(values, list):
        return None

    genre_ids: List[int] = []

    for genre in values:
        if isinstance(genre, bool):
            continue

        if isinstance(genre, int):
            genre_ids.append(genre)
            continue

        if isinstance(genre, float):
            genre_ids.append(int(genre))
            continue

        if isinstance(genre, dict):
            maybe_id = _parse_int(genre.get("id"))
            if maybe_id is not None:
                genre_ids.append(maybe_id)
                continue
            name = genre.get("name")
            if isinstance(name, str):
                mapped = _GENRE_NAME_TO_ID.get(name.strip().lower())
                if mapped is not None:
                    genre_ids.append(mapped)
            continue

        if isinstance(genre, str):
            raw = genre.strip()
            if not raw:
                continue
            if raw.isdigit():
                genre_ids.append(int(raw))
                continue

            mapped = _GENRE_NAME_TO_ID.get(raw.lower())
            if mapped is not None:
                genre_ids.append(mapped)

    if not genre_ids:
        return None

    # Keep stable order while removing duplicates.
    return list(dict.fromkeys(genre_ids))


def normalize_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize incoming aliases into the canonical filter structure."""
    source = filters or {}

    normalized: Dict[str, Any] = {
        "year_from": _parse_int(source.get("year_from") or source.get("release_year_gte") or source.get("primary_release_date_gte") or source.get("first_air_date_gte")),
        "year_to": _parse_int(source.get("year_to") or source.get("release_year_lte") or source.get("primary_release_date_lte") or source.get("first_air_date_lte")),
        "genres": _normalize_genres(source.get("genres") or source.get("with_genres")),
        "min_rating": _parse_float(source.get("min_rating") if source.get("min_rating") is not None else source.get("vote_average_gte")),
        "language": _normalize_language(source.get("language") if source.get("language") is not None else source.get("original_language") or source.get("with_original_language")),
    }

    return normalized


def build_tmdb_params(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Build TMDb discover query parameters from canonical filters."""
    canonical = normalize_filters(filters)
    params: Dict[str, Any] = {}

    if canonical.get("year_from"):
        params["primary_release_date_gte"] = f"{canonical['year_from']}-01-01"

    if canonical.get("year_to"):
        params["primary_release_date_lte"] = f"{canonical['year_to']}-12-31"

    if canonical.get("genres"):
        params["with_genres"] = "|".join(map(str, canonical["genres"]))

    if canonical.get("min_rating") is not None:
        params["vote_average_gte"] = canonical["min_rating"]

    if canonical.get("language"):
        params["with_original_language"] = canonical["language"]

    return params
