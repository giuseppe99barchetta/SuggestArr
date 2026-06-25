"""LLM service — OpenAI-compatible async client with Pydantic-validated responses.

All LLM calls go through :func:`_call_with_validation`, which:

1. Sends the request with JSON-object mode enabled (where supported).
2. Parses the raw text as JSON.
3. Validates the parsed dict against the supplied Pydantic schema.
4. On failure retries up to ``LLM_MAX_RETRIES`` times with a corrective system
   message, then raises :class:`~api_service.exceptions.api_exceptions.LLMValidationError`.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

try:
    import litellm
    _HAS_LITELLM = True
except ImportError:
    _HAS_LITELLM = False

from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.api_exceptions import LLMValidationError
from api_service.services.config_service import ConfigService
from api_service.services.llm.schemas import (
    DiscoverParams,
    RecommendationList,
    SearchResultRationaleList,
    SearchQueryInterpretation,
    SuggestedTitle,
)

logger = LoggerManager.get_logger("LLMService")

# Maximum number of unique history items to send to the LLM.
MAX_HISTORY_ITEMS = 20

_T = TypeVar("_T", bound=BaseModel)

# System message injected on every retry attempt to steer the LLM back on track.
_RETRY_SYSTEM_MESSAGE = (
    "Your previous response did not match the required JSON schema. "
    "Return strictly valid JSON matching the schema. "
    "No markdown fences, no extra fields, no comments."
)

_RECOMMENDATION_SCHEMA_HINT = (
    'Required top-level shape: {"recommendations": ['
    '{"title": "Movie title", "year": 2023, '
    '"rationale": "Why this fits.", "source_title": "Watched title"}'
    "]}. Do not return {}, an array, or any other top-level key."
)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def get_llm_client(user_id: Optional[int] = None) -> Optional[AsyncOpenAI]:
    """Initialize and return the OpenAI-compatible async client if configured.

    Checks for user-specific OpenAI config first (if user_id provided and user has
    can_manage_ai permission), then falls back to global admin config.

    When ``LLM_PROVIDER`` is ``litellm``, returns a sentinel object (not
    ``None``) so callers know the LLM is configured.  Actual calls go through
    :func:`_litellm_completion` instead of the returned client.

    :param user_id: Optional user ID to check for per-user OpenAI config
    :return: Configured :class:`AsyncOpenAI` instance (or a sentinel when
        using LiteLLM), or ``None`` when the provider is not set up.
    """
    if _use_litellm():
        config = ConfigService.get_runtime_config()
        model = config.get("LLM_MODEL", "")
        if not model:
            logger.warning(
                "LLM_PROVIDER is 'litellm' but LLM_MODEL is not set. "
                "Set it to a litellm model string like 'anthropic/claude-sonnet-4-6'."
            )
            return None
        logger.debug("Using LiteLLM provider with model %s", model)
        return AsyncOpenAI(api_key="litellm-placeholder")

    api_key = None
    base_url = None

    # Try to load user-specific config first
    if user_id is not None:
        try:
            from api_service.db.database_manager import DatabaseManager
            db = DatabaseManager()
            token = db.get_user_media_profile_token(user_id, 'openai')
            if token:
                import json
                try:
                    user_config = json.loads(token)
                    api_key = user_config.get('api_key')
                    base_url = user_config.get('base_url')
                    if api_key or base_url:
                        logger.debug(f"Using per-user OpenAI config for user_id={user_id}")
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in user OpenAI config for user_id={user_id}")
        except Exception as e:
            logger.warning(f"Failed to load user OpenAI config for user_id={user_id}: {e}")

    # Fall back to global config if no user-specific config
    if not api_key and not base_url:
        config = ConfigService.get_runtime_config()
        api_key = config.get("OPENAI_API_KEY")
        base_url = config.get("OPENAI_BASE_URL")
        if api_key or base_url:
            logger.debug("Using global OpenAI config")

    if not api_key:
        if base_url:
            logger.debug(
                "OPENAI_API_KEY not set. Using placeholder for local provider at %s.", base_url
            )
            api_key = "ollama"
        else:
            logger.warning(
                "OPENAI_API_KEY is not configured. LLM recommendations will be disabled."
            )
            return None

    try:
        client_kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        return AsyncOpenAI(**client_kwargs)
    except Exception as exc:
        logger.error("Failed to initialize OpenAI client: %s", exc)
        return None


def _use_litellm() -> bool:
    """Return True when LiteLLM provider is selected and the package is installed."""
    config = ConfigService.get_runtime_config()
    provider = config.get("LLM_PROVIDER", "openai")
    if provider == "litellm":
        if not _HAS_LITELLM:
            logger.error(
                "LLM_PROVIDER is set to 'litellm' but the litellm package is not installed. "
                "Install it with: pip install litellm"
            )
            return False
        return True
    return False


def is_llm_configured(config: Optional[Dict[str, Any]] = None) -> bool:
    """Return True when LLM config is present without creating network clients."""
    cfg = config or ConfigService.get_runtime_config()
    api_key = cfg.get("OPENAI_API_KEY")
    base_url = cfg.get("OPENAI_BASE_URL")
    return bool(api_key or base_url)


async def _close_llm_client(client: AsyncOpenAI) -> None:
    """Close the LLM HTTP client and let transport callbacks finish."""
    try:
        await client.aclose()
    except Exception as exc:
        logger.debug("Ignoring LLM client close failure: %s", exc)
        return

    # httpx/anyio may schedule transport-close callbacks during aclose().
    # Short-lived job loops must run those callbacks before loop.close().
    await asyncio.sleep(0)
    await asyncio.sleep(0)


def _validation_retry_message(schema_cls: Type[BaseModel]) -> str:
    """Return schema-specific correction text for retry attempts."""
    if schema_cls is RecommendationList:
        return f"{_RETRY_SYSTEM_MESSAGE} {_RECOMMENDATION_SCHEMA_HINT}"
    return _RETRY_SYSTEM_MESSAGE


def _normalize_parsed_response(parsed: Any, schema_cls: Type[BaseModel]) -> Any:
    """Coerce common provider response shapes into the requested schema."""
    if schema_cls is not RecommendationList:
        return parsed

    if isinstance(parsed, list):
        return {"recommendations": parsed}

    if not isinstance(parsed, dict) or "recommendations" in parsed:
        return parsed

    for key in ("movies", "movie_recommendations", "tv", "tv_recommendations", "results"):
        value = parsed.get(key)
        if isinstance(value, list):
            normalized = dict(parsed)
            normalized["recommendations"] = value
            normalized.pop(key, None)
            return normalized

    return parsed


def _response_format_options(schema_cls: Type[BaseModel]) -> List[Optional[Dict[str, Any]]]:
    """Return structured-output formats from strictest to broadest."""
    return [
        {
            "type": "json_schema",
            "json_schema": {
                "name": schema_cls.__name__,
                "schema": schema_cls.model_json_schema(),
                "strict": True,
            },
        },
        {"type": "json_object"},
        None,
    ]


def _is_response_format_rejection(exc: Exception) -> bool:
    """Return True when provider rejects a response_format option."""
    if getattr(exc, "status_code", None) != 400:
        return False

    details: List[str] = [str(exc)]
    message = getattr(exc, "message", None)
    if message:
        details.append(str(message))

    body = getattr(exc, "body", None)
    if body is not None:
        if isinstance(body, dict):
            details.append(json.dumps(body, ensure_ascii=True))
        else:
            details.append(str(body))

    detail_text = " ".join(details).lower()
    return (
        "response_format" in detail_text
        or "json_object" in detail_text
        or "json_schema" in detail_text
    )


# ---------------------------------------------------------------------------
# Low-level helpers (pure / sync)
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences that some models add despite instructions.

    :param text: Raw LLM output string.
    :return: Text with fences stripped and whitespace normalised.
    """
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _repair_title_qualifiers(text: str) -> str:
    """Fix a common LLM JSON mistake: ``"Title" (qualifier)`` → ``"Title (qualifier)"``.

    :param text: JSON string potentially containing the malformed pattern.
    :return: Repaired JSON string.
    """
    return re.sub(r'"([^"]*?)"\s+(\([^)]*?\))', r'"\1 \2"', text)


def _extract_json_object(text: str) -> str:
    """Extract the first complete JSON object or array from text.

    Some providers prepend or append natural-language commentary even when
    instructed to return JSON only. This keeps only the content between the
    first JSON opener and its likely closing delimiter, then trims whitespace.

    :param text: LLM output that should contain JSON.
    :return: String narrowed to the JSON region when delimiters exist.
    """
    object_start = text.find("{")
    array_start = text.find("[")

    starts = [idx for idx in (object_start, array_start) if idx != -1]
    if not starts:
        return text.strip()

    start = min(starts)
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    end = text.rfind(closer)
    if end != -1 and end >= start:
        text = text[start: end + 1]
    else:
        text = text[start:]

    return text.strip()


def _deduplicate_history(history_items: List[Dict]) -> List[Dict]:
    """Remove duplicate titles from history, preserving order (first occurrence wins).

    :param history_items: Raw history list, may contain repeated titles.
    :return: Deduplicated list.
    """
    seen: set = set()
    unique: List[Dict] = []
    for item in history_items:
        title = (item.get("title") or item.get("name") or "").strip().lower()
        if title and title not in seen:
            seen.add(title)
            unique.append(item)
    return unique


def _normalize_title(title: str) -> str:
    """Normalize a title for comparison by stripping common decorations.

    Removes episode notation (e.g. ``"Show - S02E12"`` → ``"Show"``) and
    trailing release-year suffixes (e.g. ``"Manchester by the Sea (2016)"``
    → ``"Manchester by the Sea"``), then lowercases and strips whitespace.

    :param title: Raw title string.
    :return: Normalised, lowercased title suitable for set membership checks.
    """
    title = re.sub(r'\s*[-–]\s*S\d+E\d+.*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\((19|20)\d{2}\)\s*$', '', title)
    return title.strip().lower()


def _is_duplicate_of_history(rec_title: str, watched_titles: set) -> bool:
    """Check whether a recommendation title duplicates a watched title.

    Uses exact match for all titles, and substring containment only for titles
    longer than 4 characters to avoid false positives on short words like "Dark".

    :param rec_title: Lowercased recommended title.
    :param watched_titles: Set of lowercased watched titles.
    :return: True if the recommendation should be filtered out.
    """
    for watched in watched_titles:
        if not watched:
            continue
        if rec_title == watched:
            return True
        if len(watched) >= 5 and watched in rec_title:
            return True
        if len(rec_title) >= 5 and rec_title in watched:
            return True
    return False


# ---------------------------------------------------------------------------
# Core validation / retry engine
# ---------------------------------------------------------------------------

async def _litellm_completion(
    model: str,
    messages: List[Dict[str, str]],
    **kwargs: Any,
) -> Any:
    """Call litellm.acompletion with drop_params enabled.

    :param model: LiteLLM model string (e.g. ``"anthropic/claude-sonnet-4-6"``).
    :param messages: Chat messages in OpenAI format.
    :param kwargs: Additional kwargs forwarded to ``litellm.acompletion``.
    :return: LiteLLM ModelResponse (OpenAI-compatible).
    """
    return await litellm.acompletion(
        model=model,
        messages=messages,
        drop_params=True,
        **kwargs,
    )


async def _call_with_validation(
    client: Optional[AsyncOpenAI],
    model: str,
    messages: List[Dict[str, str]],
    schema_cls: Type[_T],
    temperature: float = 0.7,
    max_retries: int = 2,
) -> _T:
    """Call the LLM and validate the response against *schema_cls*, with retries.

    On every attempt the raw response is:

    * stripped of markdown fences,
    * repaired for common LLM JSON quirks,
    * narrowed to the first complete JSON object,
    * parsed as JSON,
    * validated against *schema_cls*.

    If validation fails a corrective system message is prepended for the next
    attempt.  After *max_retries + 1* total attempts :class:`LLMValidationError`
    is raised.

    Strict JSON-schema mode is tried first where supported. Providers that
    reject a ``response_format`` with a 400 response fall back to JSON-object
    mode, then to plain prompting without burning a validation retry.

    When ``LLM_PROVIDER`` is ``litellm``, calls go through
    :func:`_litellm_completion` (which uses ``litellm.acompletion`` with
    ``drop_params=True``) instead of the OpenAI client.

    :param client: Initialised async OpenAI-compatible client, or ``None``
        when using the LiteLLM provider.
    :param model: Model identifier string (e.g. ``"gpt-4o-mini"``).
    :param messages: Chat messages in OpenAI format.
    :param schema_cls: Pydantic model class to validate against.
    :param temperature: Sampling temperature.
    :param max_retries: Number of *additional* attempts after the first failure.
    :raises LLMValidationError: When all attempts are exhausted.
    :return: Validated Pydantic model instance.
    """
    use_litellm = _use_litellm()
    current_messages = list(messages)
    last_error: Exception = RuntimeError("No attempts made")

    for attempt in range(max_retries + 1):
        response = None
        for response_format in _response_format_options(schema_cls):
            request_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": current_messages,
                "temperature": temperature,
            }
            if response_format is not None:
                request_kwargs["response_format"] = response_format

            try:
                if use_litellm:
                    response = await _litellm_completion(**request_kwargs)
                else:
                    response = await client.chat.completions.create(**request_kwargs)
                break
            except Exception as exc:
                if response_format is not None and _is_response_format_rejection(exc):
                    logger.debug(
                        "Provider rejected %s response_format, trying next option",
                        response_format.get("type"),
                    )
                    continue
                raise

        if response is None:
            raise RuntimeError("LLM request did not return a response")

        raw = response.choices[0].message.content.strip()
        content = _extract_json_object(
            _repair_title_qualifiers(_strip_markdown_fences(raw))
        )

        try:
            parsed = json.loads(content)
            parsed = _normalize_parsed_response(parsed, schema_cls)
            validated = schema_cls.model_validate(parsed)
            return validated
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            preview = content.replace("\n", "\\n")[:200]
            logger.warning(
                "LLM response validation failed (attempt %d/%d): %s; response preview=%r",
                attempt + 1,
                max_retries + 1,
                str(exc)[:300],
                preview,
            )
            if attempt < max_retries:
                current_messages = [
                    {"role": "system", "content": _validation_retry_message(schema_cls)},
                    *messages,
                ]

    raise LLMValidationError(
        f"LLM response failed Pydantic validation after {max_retries + 1} attempt(s). "
        f"Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Public async functions
# ---------------------------------------------------------------------------

async def get_recommendations_from_history(
    history_items: List[Dict],
    max_results: int = 5,
    item_type: str = "movie",
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Generate recommendations based on a user's watch history using an LLM.

    :param history_items: List of dicts with 'title' and ideally 'year'.
    :param max_results: Number of recommendations to generate.
    :param item_type: 'movie' or 'tv'.
    :param filters: Optional recommendation constraints (e.g. language/year/rating).
    :raises LLMValidationError: When the LLM persistently returns invalid JSON.
    :return: List of recommendation dicts with 'title', 'year', 'rationale',
        and 'source_title'.
    """
    client = get_llm_client()
    if not client:
        logger.info("Falling back to standard algorithms (LLM not configured).")
        return []

    def _normalize_language_constraint(raw: Any) -> Optional[str]:
        if isinstance(raw, list):
            if not raw:
                return None
            raw = raw[0]
        if isinstance(raw, dict):
            raw = raw.get("iso_639_1") or raw.get("id") or raw.get("code")
        if not isinstance(raw, str):
            return None
        code = raw.strip().lower()
        if not code or not code.isalpha() or len(code) not in (2, 3):
            return None
        return code

    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    try:
        if not history_items:
            logger.info("No history provided for LLM recommendations.")
            return []

        config = ConfigService.get_runtime_config()
        model = config.get("LLM_MODEL", "gpt-4o-mini")
        max_retries = int(config.get("LLM_MAX_RETRIES", 2))

        history_items = _deduplicate_history(history_items)[:MAX_HISTORY_ITEMS]
        if not history_items:
            logger.info("No unique history items after deduplication.")
            return []

        history_titles_lower = {
            _normalize_title(item.get("title") or item.get("name") or "")
            for item in history_items
        }

        list_type = "movies" if item_type == "movie" else "TV shows"
        history_text = "\n".join(
            f"- {item.get('title', item.get('name', 'Unknown'))} ({item.get('year', 'Unknown')})"
            for item in history_items
        )

        constraint_lines: List[str] = []
        if filters:
            lang = _normalize_language_constraint(
                filters.get("with_original_language")
                or filters.get("original_language")
                or filters.get("language")
            )
            if lang:
                constraint_lines.append(
                    f"- ONLY recommend titles whose ORIGINAL language code is '{lang}'."
                )

            year_from = filters.get("release_year_gte") or filters.get("year_from")
            try:
                if year_from is not None:
                    constraint_lines.append(
                        f"- Only recommend titles released from year {int(year_from)} onward."
                    )
            except (TypeError, ValueError):
                pass

            year_to = filters.get("release_year_lte") or filters.get("year_to")
            try:
                if year_to is not None:
                    constraint_lines.append(
                        f"- Only recommend titles released up to year {int(year_to)}."
                    )
            except (TypeError, ValueError):
                pass

            min_rating = _to_float(filters.get("vote_average_gte") or filters.get("min_rating"))
            if min_rating is not None:
                if min_rating > 10:
                    min_rating = min_rating / 10
                constraint_lines.append(
                    f"- Only recommend titles with TMDB rating >= {min_rating:.1f}."
                )

        constraints_block = ""
        if constraint_lines:
            constraints_block = "\nApply these hard constraints:\n" + "\n".join(constraint_lines) + "\n"

        prompt = f"""
        You are an expert film and television recommendation system.
        The user has recently watched and enjoyed the following {list_type}:

        {history_text}
        {constraints_block}

        Analyze the themes, genres, pacing, and tone of these {list_type} to build a taste profile.
        Based on this profile, recommend exactly {max_results} similar {list_type} that the user is highly likely to enjoy.

        Follow these strict rules:
        1. Do NOT recommend any of the {list_type} that the user has already watched (listed above).
        2. ONLY respond with a valid JSON object with a single key "recommendations" containing an array of objects.
        3. Each object MUST have: a "title" string, a "year" integer, a "rationale" string explaining why it was chosen, and a "source_title" string containing the EXACT title (from the list above) of the watched item that most inspired this recommendation.
        4. Do NOT wrap the JSON in markdown code blocks. Do not add any conversational text.
        5. The "title" field must be a plain JSON string. Do NOT add any text, qualifiers, or annotations outside the string (e.g., write "True Detective (Season 1)" NOT "True Detective" (Season 1)).

        Example format:
        {{
          "recommendations": [
            {{"title": "Example Movie", "year": 2023, "source_title": "Harry Potter", "rationale": "Because you enjoyed X and Y, this movie shares similar themes..."}},
            {{"title": "Another Great Catch", "year": 1999, "source_title": "The Matrix", "rationale": "A classic in the same genre as Z..."}}
          ]
        }}
    """

        messages = [
            {
                "role": "system",
                "content": "You are a specialized system that only outputs raw JSON objects for media recommendations.",
            },
            {"role": "user", "content": prompt},
        ]

        logger.debug(
            "Sending LLM request (%s) for %d unique %s history items.",
            model,
            len(history_items),
            list_type,
        )

        try:
            validated: RecommendationList = await _call_with_validation(
                client=client,
                model=model,
                messages=messages,
                schema_cls=RecommendationList,
                temperature=0.7,
                max_retries=max_retries,
            )
        except LLMValidationError as exc:
            logger.error(
                "LLM recommendation request failed after retries — falling back to standard algorithm. %s",
                exc,
            )
            return []

        valid_recommendations: List[Dict] = []
        for rec in validated.recommendations:
            rec_title = rec.title.strip().lower()

            if _is_duplicate_of_history(rec_title, history_titles_lower):
                logger.debug(
                    "Filtered duplicate recommendation already in watch history: %s", rec.title
                )
                continue

            source_title = rec.source_title
            if source_title:
                clean_source = _normalize_title(source_title)
                if clean_source not in history_titles_lower:
                    logger.warning(
                        "LLM returned source_title '%s' not found in history. Clearing.",
                        source_title,
                    )
                    source_title = None
                else:
                    stripped = re.sub(r'\s*[-–]\s*S\d+E\d+.*', '', source_title, flags=re.IGNORECASE)
                    stripped = re.sub(r'\s*\((19|20)\d{2}\)\s*$', '', stripped)
                    source_title = stripped.strip()

            rec_dict: Dict[str, Any] = {
                "title": rec.title,
                "year": rec.year,
                "rationale": rec.rationale or "No rationale provided by LLM.",
                "source_title": source_title,
            }
            logger.debug(
                "[%s (%s)] LLM Rationale: %s", rec.title, rec.year, rec_dict["rationale"]
            )
            valid_recommendations.append(rec_dict)

        logger.info("Successfully generated %d LLM recommendations.", len(valid_recommendations))
        return valid_recommendations[:max_results]
    finally:
        await _close_llm_client(client)


async def interpret_search_query(
    query: str,
    history_items: List[Dict],
    media_type: str = "movie",
    max_suggestions: int = 8,
    liked_titles: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Interpret a natural language search query and return structured TMDB parameters.

    Uses the configured LLM to extract discover parameters and suggest specific titles
    that match the user's request, taking into account their viewing history.

    :param query: Natural language search description (e.g. "psychological thriller from the 90s").
    :param history_items: List of dicts with 'title' and 'year' representing already-watched content.
    :param media_type: 'movie' or 'tv'.
    :param max_suggestions: Number of specific title suggestions to request from the LLM.
    :raises LLMValidationError: When the LLM persistently returns invalid JSON.
    :return: Dict with 'discover_params' and 'suggested_titles', or ``{}`` when
        the LLM is not configured.
    """
    client = get_llm_client()
    if not client:
        logger.info("LLM not configured — cannot interpret search query.")
        return {}

    try:
        config = ConfigService.get_runtime_config()
        model = config.get("LLM_MODEL", "gpt-4o-mini")
        max_retries = int(config.get("LLM_MAX_RETRIES", 2))

        list_type = "movies" if media_type == "movie" else "TV shows"

        deduped_history = _deduplicate_history(history_items)[:MAX_HISTORY_ITEMS]
        if deduped_history:
            history_text = "\n".join(
                f"- {item.get('title', item.get('name', 'Unknown'))} ({item.get('year', 'Unknown')})"
                for item in deduped_history
            )
            history_section = (
                f"\nThe user has already watched the following {list_type} "
                f"(do NOT suggest any of these):\n{history_text}\n\n"
                "Use the viewing history to understand their taste and personalise suggestions.\n"
            )
        else:
            history_section = ""

        liked_section = ""
        if liked_titles:
            liked_text = chr(10).join(
                f"- {t.get('title')} ({t.get('year') or 'Unknown'})"
                for t in liked_titles[:50] if t.get('title')
            )
            if liked_text:
                _nl = chr(10)
                liked_section = (
                    f"{_nl}The user has explicitly LIKED the following {list_type} "
                    f"and considers them strong examples of their taste:{_nl}{liked_text}{_nl}{_nl}"
                    f"Lean strongly toward {list_type} similar in tone, themes, mood, era or style. "
                    f"Do NOT include the liked titles themselves in the suggestions.{_nl}"
                )

        prompt = f"""You are a {list_type} search assistant for a personal media server.
The user wants to find {list_type} that match this description:
"{query}"
{history_section}{liked_section}
Return ONLY a single valid JSON object (no markdown, no explanation) with exactly these two keys:

1. "discover_params": TMDB discover filter parameters:
   - "genres": list of genre names (e.g. ["Thriller", "Crime"])
   - "year_from": optional integer minimum release year
   - "year_to": optional integer maximum release year
   - "original_language": optional ISO 639-1 language code (e.g. "en", "it", "ja")
   - "sort_by": choose based on query intent:
       * "vote_average.desc" — when the query implies quality, prestige or acclaim (e.g. "best", "greatest", "top rated", "masterpiece", "must-see", "critically acclaimed", "classic", "award-winning", "all time")
       * "popularity.desc" — for mood, genre, or style searches with no quality implication (e.g. "something relaxing", "sci-fi adventure", "Italian comedy")
   - "min_rating": optional float 0–10. Set a minimum TMDB average rating when quality is implied:
       * 8.0 for "best ever", "all-time greatest", "masterpiece", "perfect"
       * 7.5 for "best", "top", "must-see", "critically acclaimed"
       * 7.0 for "good", "great", "worth watching", "hidden gem"
       * omit (null) for mood/genre/style searches with no quality implication

2. "suggested_titles": list of exactly {max_suggestions} specific {list_type} that exist on TMDB:
   - "title": exact title as it appears on TMDB
   - "year": integer release year
   - "rationale": 1-2 sentence explanation of why it matches the user's request

Rules:
- suggested_titles must be real {list_type} verifiable on TMDB
- Do NOT suggest titles from the user's watch history
- When min_rating is set, suggested_titles must also respect it (only suggest highly rated {list_type})
- Provide sensible discover_params even if you also suggest specific titles
- All fields must be valid JSON types (no undefined, no trailing commas)

Example format:
{{
  "discover_params": {{"genres": ["Thriller"], "year_from": 1990, "year_to": 1999, "sort_by": "vote_average.desc", "min_rating": 7.5}},
  "suggested_titles": [
    {{"title": "Se7en", "year": 1995, "rationale": "Dark psychological thriller with a shocking twist ending."}},
    {{"title": "The Silence of the Lambs", "year": 1991, "rationale": "Acclaimed psychological thriller with strong suspense."}}
  ]
}}"""

        messages = [
            {
                "role": "system",
                "content": "You are a media search assistant that only outputs raw JSON objects for TMDB queries.",
            },
            {"role": "user", "content": prompt},
        ]

        logger.info(
            "Sending AI search query to LLM (%s): '%s' (media_type=%s)",
            model,
            query[:80],
            media_type,
        )

        validated: SearchQueryInterpretation = await _call_with_validation(
            client=client,
            model=model,
            messages=messages,
            schema_cls=SearchQueryInterpretation,
            temperature=0.8,
            max_retries=max_retries,
        )

        result: Dict[str, Any] = validated.model_dump()
        logger.info(
            "LLM interpreted query: genres=%s, year=%s-%s, %d title suggestions",
            validated.discover_params.genres,
            validated.discover_params.year_from,
            validated.discover_params.year_to,
            len(validated.suggested_titles),
        )
        return result
    finally:
        await _close_llm_client(client)


async def generate_search_result_rationales(
    query: str,
    media_type: str,
    discover_params: Dict[str, Any],
    results: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Generate concise, per-result rationales for AI-search TMDB results.

    :param query: Original user search query.
    :param media_type: 'movie' or 'tv'.
    :param discover_params: Parsed interpretation filters used during discover.
    :param results: Final or candidate TMDB result dicts with title/name and optional year.
    :return: Mapping keyed as ``"{normalized_title}|{year_or_empty}"`` to rationale text.
    """
    if not results:
        return {}

    client = get_llm_client()
    if not client:
        logger.info("LLM not configured — skipping per-result rationale generation.")
        return {}

    try:
        config = ConfigService.get_runtime_config()
        model = config.get("LLM_MODEL", "gpt-4o-mini")
        max_retries = int(config.get("LLM_MAX_RETRIES", 2))
        list_type = "movies" if media_type == "movie" else "TV shows"

        input_items: List[Dict[str, Any]] = []
        for item in results:
            title = (item.get("title") or item.get("name") or "").strip()
            if not title:
                continue

            year = item.get("year")
            if year is None:
                date_value = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
                year_text = str(date_value).split("-")[0] if date_value else ""
                year = int(year_text) if year_text.isdigit() else None

            input_items.append({"title": title, "year": year})

        if not input_items:
            return {}

        discover_summary = {
            "genres": discover_params.get("genres"),
            "year_from": discover_params.get("year_from"),
            "year_to": discover_params.get("year_to"),
            "min_rating": discover_params.get("min_rating"),
        }

        prompt = f"""You are writing short, personalized recommendation rationales for {list_type}.

        User query:
        \"{query}\"
        
        Interpreted filters:
        {json.dumps(discover_summary, ensure_ascii=True)}
        
        Generate one rationale for each candidate below:
        {json.dumps(input_items, ensure_ascii=True)}
        
        Return ONLY valid JSON with this exact shape:
        {{
          \"rationales\": [
            {{\"title\": \"...\", \"year\": 2020, \"rationale\": \"...\"}}
          ]
        }}
        
        Rules:
        - Include exactly one entry per input item (same title/year pairs).
        - rationale must be exactly one sentence.
        - Keep each rationale natural, recommendation-like, and <= 20 words.
        - Vary wording across items; do not repeat the same sentence structure.
        - Mention concrete fit to the user's query or filters when possible.
        - Do not include markdown or any text outside JSON.
        """

        messages = [
            {
                "role": "system",
                "content": "You produce strict JSON only for media rationale generation.",
            },
            {"role": "user", "content": prompt},
        ]

        validated: SearchResultRationaleList = await _call_with_validation(
            client=client,
            model=model,
            messages=messages,
            schema_cls=SearchResultRationaleList,
            temperature=0.8,
            max_retries=max_retries,
        )

        rationale_map: Dict[str, str] = {}
        for item in validated.rationales:
            title_key = _normalize_title(item.title)
            if not title_key:
                continue
            year_key = str(item.year) if item.year is not None else ""
            key = f"{title_key}|{year_key}"
            rationale = str(item.rationale or "").strip()
            if rationale and key not in rationale_map:
                rationale_map[key] = rationale

        return rationale_map
    except Exception as exc:
        logger.warning("Failed generating per-result LLM rationales: %s", exc)
        return {}
    finally:
        await _close_llm_client(client)
