"""Pydantic schemas for structured LLM responses.

All models use ``extra="forbid"`` so that unexpected fields returned by the LLM
trigger a ``ValidationError``, which causes the retry mechanism in
``_call_with_validation`` to kick in with a corrective system message.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# get_recommendations_from_history schemas
# ---------------------------------------------------------------------------

class RecommendationItem(BaseModel):
    """A single media recommendation produced by the LLM."""

    model_config = ConfigDict(extra="forbid")

    title: str
    year: int
    rationale: str
    source_title: Optional[str] = None


class RecommendationList(BaseModel):
    """Top-level wrapper for the LLM recommendation response.

    Wrapping the array in an object is required so that JSON-object mode (used
    by OpenAI-compatible providers) can be activated — those APIs require the
    root JSON value to be an object, not a bare array.
    """

    model_config = ConfigDict(extra="forbid")

    recommendations: list[RecommendationItem]


# ---------------------------------------------------------------------------
# interpret_search_query schemas
# ---------------------------------------------------------------------------

class DiscoverParams(BaseModel):
    """TMDB discover filter parameters extracted from the user's natural-language query."""

    # Extra fields the LLM might include are silently ignored: the TMDB client
    # only reads known keys, so unknown extras are harmless.
    model_config = ConfigDict(extra="ignore")

    genres: Optional[list[str]] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    original_language: Optional[str] = None
    sort_by: Optional[str] = None
    min_rating: Optional[float] = None


class SuggestedTitle(BaseModel):
    """A single specific title suggestion produced by the LLM for AI search."""

    model_config = ConfigDict(extra="forbid")

    title: str
    year: Optional[int] = None
    rationale: str


class SearchQueryInterpretation(BaseModel):
    """Top-level response model for :func:`interpret_search_query`."""

    model_config = ConfigDict(extra="forbid")

    discover_params: DiscoverParams
    suggested_titles: list[SuggestedTitle]
