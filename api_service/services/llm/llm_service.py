import json
import re
from openai import AsyncOpenAI
from typing import List, Dict, Optional, Any
from api_service.config.logger_manager import LoggerManager
from api_service.config.config import load_env_vars

logger = LoggerManager.get_logger("LLMService")

# Maximum number of unique history items to send to the LLM.
# Caps prompt size and avoids over-weighting a single heavily-watched title.
MAX_HISTORY_ITEMS = 20


def get_llm_client() -> Optional[AsyncOpenAI]:
    """Initialize and return the OpenAI client if configured."""
    config = load_env_vars()
    api_key = config.get('OPENAI_API_KEY')
    base_url = config.get('OPENAI_BASE_URL') # Optional for proxy/alternative setups

    if not api_key:
        if base_url:
            # Local providers like Ollama don't require an API key; use a placeholder.
            logger.debug("OPENAI_API_KEY not set. Using placeholder for local provider at %s.", base_url)
            api_key = "ollama"
        else:
            logger.warning("OPENAI_API_KEY is not configured. LLM recommendations will be disabled.")
            return None

    try:
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = AsyncOpenAI(**client_kwargs)
        return client
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        return None


def _deduplicate_history(history_items: List[Dict]) -> List[Dict]:
    """Remove duplicate titles from history, preserving order (first occurrence wins).

    :param history_items: Raw history list, may contain repeated titles.
    :return: Deduplicated list.
    """
    seen = set()
    unique = []
    for item in history_items:
        title = (item.get("title") or item.get("name") or "").strip().lower()
        if title and title not in seen:
            seen.add(title)
            unique.append(item)
    return unique


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
        # Only apply substring logic for titles long enough to be unambiguous
        if len(watched) >= 5 and watched in rec_title:
            return True
        if len(rec_title) >= 5 and rec_title in watched:
            return True
    return False


async def get_recommendations_from_history(history_items: List[Dict], max_results: int = 5, item_type: str = "movie") -> List[Dict]:
    """Generate recommendations based on a user's watch history using an LLM.

    :param history_items: List of dicts with 'title' and ideally 'year'.
    :param max_results: Number of recommendations to generate.
    :param item_type: 'movie' or 'tv'.
    :return: List of recommendation dicts with 'title', 'year', 'rationale', 'source_title'.
    """
    client = get_llm_client()
    if not client:
        logger.info("Falling back to standard algorithms (LLM not configured).")
        return []

    if not history_items:
        logger.info("No history provided for LLM recommendations.")
        return []

    config = load_env_vars()
    model = config.get('LLM_MODEL', 'gpt-4o-mini')

    # Deduplicate and cap the history before sending to the LLM
    history_items = _deduplicate_history(history_items)[:MAX_HISTORY_ITEMS]
    if not history_items:
        logger.info("No unique history items after deduplication.")
        return []

    # Build a set of lowercase history titles for validation and duplicate detection
    history_titles_lower = {
        (item.get("title") or item.get("name") or "").strip().lower()
        for item in history_items
    }

    # Format the history into a readable list for the prompt
    list_type = "movies" if item_type == "movie" else "TV shows"
    history_text = "\n".join(
        f"- {item.get('title', item.get('name', 'Unknown'))} ({item.get('year', 'Unknown')})"
        for item in history_items
    )

    prompt = f"""
        You are an expert film and television recommendation system.
        The user has recently watched and enjoyed the following {list_type}:

        {history_text}

        Analyze the themes, genres, pacing, and tone of these {list_type} to build a taste profile.
        Based on this profile, recommend exactly {max_results} similar {list_type} that the user is highly likely to enjoy.

        Follow these strict rules:
        1. Do NOT recommend any of the {list_type} that the user has already watched (listed above).
        2. ONLY respond with a valid JSON array of objects.
        3. Each object MUST have: a "title" string, a "year" integer, a "rationale" string explaining why it was chosen, and a "source_title" string containing the EXACT title (from the list above) of the watched item that most inspired this recommendation.
        4. Do NOT wrap the JSON in markdown code blocks. Do not add any conversational text.
        5. The "title" field must be a plain JSON string. Do NOT add any text, qualifiers, or annotations outside the string (e.g., write "True Detective (Season 1)" NOT "True Detective" (Season 1)).

        Example format:
        [
          {{"title": "Example Movie", "year": 2023, "source_title": "Harry Potter", "rationale": "Because you enjoyed X and Y, this movie shares similar themes..."}},
          {{"title": "Another Great Catch", "year": 1999, "source_title": "The Matrix", "rationale": "A classic in the same genre as Z..."}}
        ]
    """

    try:
        logger.info(f"Sending LLM request to OpenAI ({model}) for {len(history_items)} unique {list_type} history items.")
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a specialized system that only outputs raw JSON arrays of media recommendations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )

        content = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model added them despite instructions
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Repair common LLM JSON mistake: "Some Title" (qualifier) → "Some Title (qualifier)"
        content = re.sub(r'"([^"]*?)"\s+(\([^)]*?\))', r'"\1 \2"', content)

        # Parse — some models wrap the array in a dict even without json_object mode
        parsed_json = json.loads(content)
        recommendations = []
        if isinstance(parsed_json, list):
            recommendations = parsed_json
        elif isinstance(parsed_json, dict):
            for val in parsed_json.values():
                if isinstance(val, list):
                    recommendations = val
                    break

        # Validate, filter duplicates, and log
        valid_recommendations = []
        for rec in recommendations:
            if not isinstance(rec, dict) or "title" not in rec or "year" not in rec:
                continue

            rec_title = rec["title"].strip().lower()

            if _is_duplicate_of_history(rec_title, history_titles_lower):
                logger.info(f"Filtered out duplicate recommendation already in watch history: {rec['title']}")
                continue

            # Validate source_title: must be one of the actual history titles.
            # Also strip episode notation (e.g. "Dan Da Dan - S02E12" → "Dan Da Dan")
            # before comparing, in case the history still contains raw episode strings.
            source_title = rec.get("source_title", "")
            if source_title:
                clean_source = re.sub(r'\s*[-–]\s*S\d+E\d+.*', '', source_title, flags=re.IGNORECASE).strip().lower()
                if clean_source not in history_titles_lower:
                    logger.warning(
                        f"LLM returned source_title '{source_title}' not found in history. Clearing."
                    )
                    rec["source_title"] = None
                else:
                    # Normalise to the clean version so handlers receive a searchable title
                    rec["source_title"] = re.sub(r'\s*[-–]\s*S\d+E\d+.*', '', source_title, flags=re.IGNORECASE).strip()

            rationale = rec.get("rationale", "No rationale provided by LLM.")
            logger.info(f"[{rec['title']} ({rec['year']})] LLM Rationale: {rationale}")
            valid_recommendations.append(rec)

        logger.info(f"Successfully generated {len(valid_recommendations)} LLM recommendations.")
        return valid_recommendations[:max_results]

    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM response as JSON. Raw response: {content}")
        return []
    except Exception as e:
        logger.error(f"Error communicating with LLM API: {str(e)}")
        return []


async def interpret_search_query(
    query: str,
    history_items: List[Dict],
    media_type: str = "movie",
    max_suggestions: int = 8
) -> Dict[str, Any]:
    """Interpret a natural language search query and return structured TMDB parameters.

    Uses the configured LLM to extract discover parameters and suggest specific titles
    that match the user's request, taking into account their viewing history.

    :param query: Natural language search description (e.g. "psychological thriller from the 90s").
    :param history_items: List of dicts with 'title' and 'year' representing already-watched content.
    :param media_type: 'movie' or 'tv'.
    :param max_suggestions: Number of specific title suggestions to request from the LLM.
    :return: Dict with 'discover_params' and 'suggested_titles', or {} on failure.
    """
    client = get_llm_client()
    if not client:
        logger.info("LLM not configured — cannot interpret search query.")
        return {}

    config = load_env_vars()
    model = config.get('LLM_MODEL', 'gpt-4o-mini')

    list_type = "movies" if media_type == "movie" else "TV shows"

    # Build the watched-titles section of the prompt
    deduped_history = _deduplicate_history(history_items)[:MAX_HISTORY_ITEMS]
    if deduped_history:
        history_text = "\n".join(
            f"- {item.get('title', item.get('name', 'Unknown'))} ({item.get('year', 'Unknown')})"
            for item in deduped_history
        )
        history_section = f"""
The user has already watched the following {list_type} (do NOT suggest any of these):
{history_text}

Use the viewing history to understand their taste and personalise suggestions.
"""
    else:
        history_section = ""

    prompt = f"""You are a {list_type} search assistant for a personal media server.
The user wants to find {list_type} that match this description:
"{query}"
{history_section}
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

    try:
        logger.info(
            "Sending AI search query to LLM (%s): '%s' (media_type=%s)", model, query[:80], media_type
        )
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a media search assistant that only outputs raw JSON objects for TMDB queries.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )

        content = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Repair common LLM JSON mistake: "Some Title" (qualifier) → "Some Title (qualifier)"
        content = re.sub(r'"([^"]*?)"\s+(\([^)]*?\))', r'"\1 \2"', content)

        parsed = json.loads(content)

        if not isinstance(parsed, dict):
            logger.error("LLM returned non-dict JSON for search query interpretation.")
            return {}

        # Normalise suggested_titles: ensure required keys exist
        raw_titles = parsed.get("suggested_titles", [])
        valid_titles = []
        for t in raw_titles:
            if isinstance(t, dict) and "title" in t and "year" in t:
                valid_titles.append({
                    "title": str(t["title"]).strip(),
                    "year": int(t["year"]) if t["year"] else None,
                    "rationale": str(t.get("rationale", "")).strip(),
                })
        parsed["suggested_titles"] = valid_titles

        logger.info(
            "LLM interpreted query: genres=%s, year=%s-%s, %d title suggestions",
            parsed.get("discover_params", {}).get("genres"),
            parsed.get("discover_params", {}).get("year_from"),
            parsed.get("discover_params", {}).get("year_to"),
            len(valid_titles),
        )
        return parsed

    except json.JSONDecodeError:
        logger.error("Failed to parse LLM search interpretation as JSON. Raw: %s", content[:300])
        return {}
    except Exception as e:
        logger.error("Error during LLM search query interpretation: %s", str(e))
        return {}
