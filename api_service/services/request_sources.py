"""Canonical request-source tags for non-TMDb automation origins."""

DISCOVER_SOURCE = "discover"
TRAKT_RECOMMENDATIONS_SOURCE = "trakt_recommendations"

REQUEST_SOURCE_LABELS = {
    DISCOVER_SOURCE: "Discover",
    TRAKT_RECOMMENDATIONS_SOURCE: "Trakt Recommendations",
}


def is_tmdb_metadata_source_id(source_id) -> bool:
    """Return True when *source_id* should be stored in the metadata table."""
    if source_id is None:
        return False
    text = str(source_id)
    if text in REQUEST_SOURCE_LABELS or text == "ai_search":
        return False
    return text.isdigit()


def request_source_title_sql(source_alias: str = "r") -> str:
    """Build a SQL CASE expression for grouped request source titles."""
    when_clauses = "\n                ".join(
        f"WHEN {source_alias}.tmdb_source_id = '{tag}' THEN '{label}'"
        for tag, label in REQUEST_SOURCE_LABELS.items()
    )
    return f"""CASE
                WHEN s.title IS NOT NULL THEN s.title
                {when_clauses}
                ELSE 'LLM Recommendation'
            END"""
