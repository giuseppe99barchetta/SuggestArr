"""
Tests for LLM service pure functions and async wrappers.

Covers (pure/sync):
- _deduplicate_history(): removes duplicates, preserves order, handles empty/None titles
- _normalize_title(): strips episode notation, year suffix, plain titles, both decorations
- _is_duplicate_of_history(): exact match, substring (long), short title no match, no match
- _strip_markdown_fences(): fenced with ```json, plain ```, none
- _repair_title_qualifiers(): common LLM title quirk

Covers (_call_with_validation — async):
- Valid structured response passes on first attempt
- Invalid schema triggers retry with corrective system message
- Retries exhausted → raises LLMValidationError
- JSON decode error triggers retry → raises LLMValidationError

Covers (get_recommendations_from_history — async):
- No LLM client → []
- No history → []
- Valid wrapped response ("recommendations" key) → parsed list
- Duplicate recommendation filtered against watch history
- LLMValidationError caught internally → [] returned (automation resilience)
- Markdown code fences stripped before validation

Covers (interpret_search_query — async):
- No LLM client → {}
- Valid response → parsed dict
- LLMValidationError propagates to caller (interactive path)
"""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

from api_service.exceptions.api_exceptions import LLMValidationError
from api_service.services.llm.llm_service import (
    _call_with_validation,
    _deduplicate_history,
    _is_duplicate_of_history,
    _normalize_title,
    _repair_title_qualifiers,
    _strip_markdown_fences,
    get_recommendations_from_history,
    interpret_search_query,
)
from api_service.services.llm.schemas import RecommendationList, SearchQueryInterpretation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = {"LLM_MODEL": "gpt-4o-mini", "LLM_MAX_RETRIES": 2}


def _mock_openai_response(content: str):
    """Build a mock OpenAI chat completion response."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


def _wrap_recs(recs: list) -> str:
    """Wrap a list of recommendation dicts in the expected {"recommendations": [...]} envelope."""
    return json.dumps({"recommendations": recs})


# ---------------------------------------------------------------------------
# _strip_markdown_fences
# ---------------------------------------------------------------------------

class TestStripMarkdownFences(unittest.TestCase):

    def test_strips_json_fence(self):
        text = "```json\n{}\n```"
        self.assertEqual(_strip_markdown_fences(text), "{}")

    def test_strips_plain_fence(self):
        text = "```\n{}\n```"
        self.assertEqual(_strip_markdown_fences(text), "{}")

    def test_no_fence_unchanged(self):
        text = '{"key": "value"}'
        self.assertEqual(_strip_markdown_fences(text), text)

    def test_strips_whitespace(self):
        text = "  {}  "
        self.assertEqual(_strip_markdown_fences(text), "{}")


# ---------------------------------------------------------------------------
# _repair_title_qualifiers
# ---------------------------------------------------------------------------

class TestRepairTitleQualifiers(unittest.TestCase):

    def test_merges_trailing_parenthetical(self):
        text = '"True Detective" (Season 1)'
        result = _repair_title_qualifiers(text)
        self.assertIn("True Detective (Season 1)", result)

    def test_leaves_normal_json_unchanged(self):
        text = '{"title": "Se7en", "year": 1995}'
        self.assertEqual(_repair_title_qualifiers(text), text)


# ---------------------------------------------------------------------------
# _deduplicate_history
# ---------------------------------------------------------------------------

class TestDeduplicateHistory(unittest.TestCase):

    def test_removes_exact_duplicates(self):
        history = [{"title": "Inception"}, {"title": "Inception"}, {"title": "Interstellar"}]
        result = _deduplicate_history(history)
        self.assertEqual(len(result), 2)

    def test_preserves_insertion_order(self):
        history = [{"title": "C"}, {"title": "A"}, {"title": "B"}]
        result = _deduplicate_history(history)
        self.assertEqual([r["title"] for r in result], ["C", "A", "B"])

    def test_case_insensitive_dedup(self):
        history = [{"title": "inception"}, {"title": "Inception"}]
        self.assertEqual(len(_deduplicate_history(history)), 1)

    def test_uses_name_key_as_fallback(self):
        history = [{"name": "Breaking Bad"}, {"name": "Breaking Bad"}]
        self.assertEqual(len(_deduplicate_history(history)), 1)

    def test_handles_empty_list(self):
        self.assertEqual(_deduplicate_history([]), [])

    def test_skips_items_with_empty_title(self):
        history = [{"title": ""}, {"title": None}]
        self.assertEqual(len(_deduplicate_history(history)), 0)


# ---------------------------------------------------------------------------
# _normalize_title
# ---------------------------------------------------------------------------

class TestNormalizeTitle(unittest.TestCase):

    def test_strips_episode_notation(self):
        self.assertEqual(_normalize_title("Show - S02E12 Title"), "show")

    def test_strips_trailing_year_suffix(self):
        self.assertEqual(_normalize_title("Manchester by the Sea (2016)"), "manchester by the sea")

    def test_strips_both_decorations(self):
        self.assertEqual(_normalize_title("Show - S01E01 (2020)"), "show")

    def test_plain_title_is_lowercased(self):
        self.assertEqual(_normalize_title("Breaking Bad"), "breaking bad")

    def test_strips_whitespace(self):
        self.assertEqual(_normalize_title("  Dune  "), "dune")


# ---------------------------------------------------------------------------
# _is_duplicate_of_history
# ---------------------------------------------------------------------------

class TestIsDuplicateOfHistory(unittest.TestCase):

    def test_returns_true_on_exact_match(self):
        self.assertTrue(_is_duplicate_of_history("inception", {"inception", "interstellar"}))

    def test_returns_true_on_substring_match_long_title(self):
        self.assertTrue(_is_duplicate_of_history("breaking bad season 1", {"breaking bad"}))

    def test_returns_false_for_short_watched_title_substring(self):
        # 'dark' has len 4 < 5 → substring logic NOT applied
        self.assertFalse(_is_duplicate_of_history("darkest hour", {"dark"}))

    def test_returns_false_when_no_match(self):
        self.assertFalse(_is_duplicate_of_history("dune", {"inception", "interstellar"}))

    def test_skips_empty_watched_titles(self):
        self.assertFalse(_is_duplicate_of_history("dune", {"", "inception"}))


# ---------------------------------------------------------------------------
# _call_with_validation
# ---------------------------------------------------------------------------

class TestCallWithValidation(unittest.IsolatedAsyncioTestCase):

    def _make_client(self, *responses):
        """Return a mock client whose create coroutine returns *responses* in order."""
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=list(responses))
        return mock_client

    async def test_valid_response_passes_first_attempt(self):
        payload = json.dumps({"recommendations": [
            {"title": "Dune", "year": 2021, "rationale": "Epic sci-fi", "source_title": None}
        ]})
        client = self._make_client(_mock_openai_response(payload))

        result = await _call_with_validation(
            client=client,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "recommend"}],
            schema_cls=RecommendationList,
            max_retries=2,
        )

        self.assertIsInstance(result, RecommendationList)
        self.assertEqual(len(result.recommendations), 1)
        self.assertEqual(result.recommendations[0].title, "Dune")
        # Only one API call should have been made
        self.assertEqual(client.chat.completions.create.call_count, 1)

    async def test_invalid_schema_triggers_retry_and_succeeds(self):
        bad_payload = json.dumps({"wrong_key": []})  # missing "recommendations"
        good_payload = json.dumps({"recommendations": [
            {"title": "Se7en", "year": 1995, "rationale": "Dark.", "source_title": None}
        ]})
        client = self._make_client(
            _mock_openai_response(bad_payload),
            _mock_openai_response(good_payload),
        )

        result = await _call_with_validation(
            client=client,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "recommend"}],
            schema_cls=RecommendationList,
            max_retries=2,
        )

        self.assertEqual(result.recommendations[0].title, "Se7en")
        # Two calls: first failure + one retry
        self.assertEqual(client.chat.completions.create.call_count, 2)

    async def test_retry_injects_corrective_system_message(self):
        bad_payload = json.dumps({"wrong_key": []})
        good_payload = json.dumps({"recommendations": [
            {"title": "Tenet", "year": 2020, "rationale": "Great.", "source_title": None}
        ]})
        client = self._make_client(
            _mock_openai_response(bad_payload),
            _mock_openai_response(good_payload),
        )
        original_messages = [{"role": "user", "content": "recommend"}]

        await _call_with_validation(
            client=client,
            model="gpt-4o-mini",
            messages=original_messages,
            schema_cls=RecommendationList,
            max_retries=2,
        )

        # Second call's messages should include the corrective system message at the front
        second_call_messages = client.chat.completions.create.call_args_list[1][1]["messages"]
        self.assertEqual(second_call_messages[0]["role"], "system")
        self.assertIn("schema", second_call_messages[0]["content"].lower())

    async def test_retries_exhausted_raises_llm_validation_error(self):
        bad_payload = json.dumps({"wrong_key": []})
        client = self._make_client(
            _mock_openai_response(bad_payload),
            _mock_openai_response(bad_payload),
            _mock_openai_response(bad_payload),
        )

        with self.assertRaises(LLMValidationError):
            await _call_with_validation(
                client=client,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "recommend"}],
                schema_cls=RecommendationList,
                max_retries=2,
            )

        # 1 original + 2 retries = 3 total attempts
        self.assertEqual(client.chat.completions.create.call_count, 3)

    async def test_json_decode_error_triggers_retry_then_raises(self):
        client = self._make_client(
            _mock_openai_response("not valid json {{{{"),
            _mock_openai_response("still not json"),
            _mock_openai_response("```"),
        )

        with self.assertRaises(LLMValidationError):
            await _call_with_validation(
                client=client,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "recommend"}],
                schema_cls=RecommendationList,
                max_retries=2,
            )

    async def test_strips_markdown_fences_before_validation(self):
        payload = json.dumps({"recommendations": [
            {"title": "Dune", "year": 2021, "rationale": "Epic.", "source_title": None}
        ]})
        fenced = f"```json\n{payload}\n```"
        client = self._make_client(_mock_openai_response(fenced))

        result = await _call_with_validation(
            client=client,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "recommend"}],
            schema_cls=RecommendationList,
            max_retries=0,
        )
        self.assertEqual(result.recommendations[0].title, "Dune")


# ---------------------------------------------------------------------------
# get_recommendations_from_history (async)
# ---------------------------------------------------------------------------

class TestGetRecommendationsFromHistory(unittest.IsolatedAsyncioTestCase):

    async def test_returns_empty_list_when_no_llm_client(self):
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=None):
            result = await get_recommendations_from_history([{"title": "Film A"}], max_results=3)
        self.assertEqual(result, [])

    async def test_returns_empty_list_when_no_history(self):
        mock_client = AsyncMock()
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=_DEFAULT_CONFIG):
            result = await get_recommendations_from_history([], max_results=3)
        self.assertEqual(result, [])

    async def test_returns_parsed_recommendations_on_success(self):
        recs = [
            {"title": "Interstellar", "year": 2014, "source_title": "Inception", "rationale": "similar themes"},
            {"title": "Tenet",        "year": 2020, "source_title": "Inception", "rationale": "same director"},
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(_wrap_recs(recs))
        )
        history = [{"title": "Inception", "year": 2010}]
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=_DEFAULT_CONFIG):
            result = await get_recommendations_from_history(history, max_results=5)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "Interstellar")

    async def test_filters_out_recs_that_are_in_watch_history(self):
        recs = [
            {"title": "Inception", "year": 2010, "source_title": "Inception", "rationale": "dupe"},
            {"title": "Tenet",     "year": 2020, "source_title": "Inception", "rationale": "good pick"},
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(_wrap_recs(recs))
        )
        history = [{"title": "Inception", "year": 2010}]
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=_DEFAULT_CONFIG):
            result = await get_recommendations_from_history(history, max_results=5)
        titles = [r["title"] for r in result]
        self.assertNotIn("Inception", titles)
        self.assertIn("Tenet", titles)

    async def test_llm_validation_error_caught_returns_empty_list(self):
        """Persistent validation failure should be logged and return [] for automation resilience."""
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response("not valid json")
        )
        history = [{"title": "Inception", "year": 2010}]
        # max_retries=0 → single attempt, then LLMValidationError caught internally
        config = {**_DEFAULT_CONFIG, "LLM_MAX_RETRIES": 0}
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=config):
            result = await get_recommendations_from_history(history, max_results=5)
        self.assertEqual(result, [])

    async def test_strips_markdown_code_fences(self):
        recs = [{"title": "Tenet", "year": 2020, "source_title": "Inception", "rationale": "ok"}]
        fenced = "```json\n" + _wrap_recs(recs) + "\n```"
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(fenced)
        )
        history = [{"title": "Inception", "year": 2010}]
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=_DEFAULT_CONFIG):
            result = await get_recommendations_from_history(history, max_results=5)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# interpret_search_query (async)
# ---------------------------------------------------------------------------

class TestInterpretSearchQuery(unittest.IsolatedAsyncioTestCase):

    def _valid_interpretation_payload(self, n_titles: int = 1) -> str:
        titles = [
            {"title": f"Film {i}", "year": 2000 + i, "rationale": "Good film."}
            for i in range(n_titles)
        ]
        return json.dumps({
            "discover_params": {"genres": ["Thriller"], "year_from": 1990, "sort_by": "vote_average.desc"},
            "suggested_titles": titles,
        })

    async def test_returns_empty_dict_when_no_llm_client(self):
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=None):
            result = await interpret_search_query("psychological thriller", [])
        self.assertEqual(result, {})

    async def test_returns_parsed_result_on_success(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(self._valid_interpretation_payload())
        )
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=_DEFAULT_CONFIG):
            result = await interpret_search_query("dark psychological thriller from 90s", [])

        self.assertIn("discover_params", result)
        self.assertIn("suggested_titles", result)
        self.assertEqual(result["suggested_titles"][0]["title"], "Film 0")

    async def test_llm_validation_error_propagates_to_caller(self):
        """On persistent failure, LLMValidationError should propagate (interactive path)."""
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response("not json")
        )
        config = {**_DEFAULT_CONFIG, "LLM_MAX_RETRIES": 0}
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=config):
            with self.assertRaises(LLMValidationError):
                await interpret_search_query("thriller", [])

    async def test_retry_succeeds_on_second_attempt(self):
        bad_payload = json.dumps({"wrong_key": []})
        good_payload = self._valid_interpretation_payload(2)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_openai_response(bad_payload),
                _mock_openai_response(good_payload),
            ]
        )
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=_DEFAULT_CONFIG):
            result = await interpret_search_query("thriller", [])

        self.assertEqual(len(result["suggested_titles"]), 2)
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)

    async def test_result_is_serialisable_dict(self):
        """model_dump() output must be JSON-serialisable (no Pydantic models inside)."""
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(self._valid_interpretation_payload())
        )
        with patch("api_service.services.llm.llm_service.get_llm_client", return_value=mock_client), \
             patch("api_service.services.llm.llm_service.load_env_vars", return_value=_DEFAULT_CONFIG):
            result = await interpret_search_query("thriller", [])

        # Should not raise
        serialised = json.dumps(result)
        self.assertIsInstance(serialised, str)


if __name__ == "__main__":
    unittest.main()
