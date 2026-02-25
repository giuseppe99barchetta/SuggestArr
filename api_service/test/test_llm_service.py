"""
Tests for LLM service pure functions and async wrappers.

Covers (pure/sync):
- _deduplicate_history(): removes duplicates, preserves order, handles empty/None titles
- _normalize_title(): strips episode notation, year suffix, plain titles, both decorations
- _is_duplicate_of_history(): exact match, substring (long), short title no match, no match

Covers (async):
- get_recommendations_from_history(): no LLM client → [], no history → [], success, JSON error
- interpret_search_query(): no LLM client → {}, success, JSON error, markdown stripping
"""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from api_service.services.llm.llm_service import (
    _deduplicate_history,
    _is_duplicate_of_history,
    _normalize_title,
    get_recommendations_from_history,
    interpret_search_query,
)


# ---------------------------------------------------------------------------
# _deduplicate_history
# ---------------------------------------------------------------------------

class TestDeduplicateHistory(unittest.TestCase):

    def test_removes_exact_duplicates(self):
        history = [
            {'title': 'Inception'},
            {'title': 'Inception'},
            {'title': 'Interstellar'},
        ]
        result = _deduplicate_history(history)
        self.assertEqual(len(result), 2)

    def test_preserves_insertion_order(self):
        history = [
            {'title': 'C'},
            {'title': 'A'},
            {'title': 'B'},
        ]
        result = _deduplicate_history(history)
        self.assertEqual([r['title'] for r in result], ['C', 'A', 'B'])

    def test_case_insensitive_dedup(self):
        history = [{'title': 'inception'}, {'title': 'Inception'}]
        result = _deduplicate_history(history)
        self.assertEqual(len(result), 1)

    def test_uses_name_key_as_fallback(self):
        history = [{'name': 'Breaking Bad'}, {'name': 'Breaking Bad'}]
        result = _deduplicate_history(history)
        self.assertEqual(len(result), 1)

    def test_handles_empty_list(self):
        self.assertEqual(_deduplicate_history([]), [])

    def test_skips_items_with_empty_title(self):
        """Items with blank/None title are all kept (no dedup key)."""
        history = [{'title': ''}, {'title': None}]
        result = _deduplicate_history(history)
        # Both items have falsy titles → skipped by the dedup logic → none added
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# _normalize_title
# ---------------------------------------------------------------------------

class TestNormalizeTitle(unittest.TestCase):

    def test_strips_episode_notation(self):
        self.assertEqual(_normalize_title('Show - S02E12 Title'), 'show')

    def test_strips_trailing_year_suffix(self):
        self.assertEqual(_normalize_title('Manchester by the Sea (2016)'), 'manchester by the sea')

    def test_strips_both_decorations(self):
        self.assertEqual(_normalize_title('Show - S01E01 (2020)'), 'show')

    def test_plain_title_is_lowercased(self):
        self.assertEqual(_normalize_title('Breaking Bad'), 'breaking bad')

    def test_strips_whitespace(self):
        self.assertEqual(_normalize_title('  Dune  '), 'dune')


# ---------------------------------------------------------------------------
# _is_duplicate_of_history
# ---------------------------------------------------------------------------

class TestIsDuplicateOfHistory(unittest.TestCase):

    def test_returns_true_on_exact_match(self):
        self.assertTrue(_is_duplicate_of_history('inception', {'inception', 'interstellar'}))

    def test_returns_true_on_substring_match_long_title(self):
        # 'breaking bad' (len 11) is in 'breaking bad season 1'
        self.assertTrue(_is_duplicate_of_history('breaking bad season 1', {'breaking bad'}))

    def test_returns_false_for_short_watched_title_substring(self):
        # 'dark' (len 4 < 5) should not trigger substring logic
        self.assertFalse(_is_duplicate_of_history('darkest hour', {'dark'}))

    def test_returns_false_when_no_match(self):
        self.assertFalse(_is_duplicate_of_history('dune', {'inception', 'interstellar'}))

    def test_skips_empty_watched_titles(self):
        self.assertFalse(_is_duplicate_of_history('dune', {'', 'inception'}))


# ---------------------------------------------------------------------------
# get_recommendations_from_history (async)
# ---------------------------------------------------------------------------

def _mock_openai_response(content: str):
    """Build a mock OpenAI chat completion response."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


class TestGetRecommendationsFromHistory(unittest.IsolatedAsyncioTestCase):

    async def test_returns_empty_list_when_no_llm_client(self):
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=None):
            result = await get_recommendations_from_history([{'title': 'Film A'}], max_results=3)
        self.assertEqual(result, [])

    async def test_returns_empty_list_when_no_history(self):
        mock_client = AsyncMock()
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=mock_client), \
             patch('api_service.services.llm.llm_service.load_env_vars', return_value={'LLM_MODEL': 'gpt-4o-mini'}):
            result = await get_recommendations_from_history([], max_results=3)
        self.assertEqual(result, [])

    async def test_returns_parsed_recommendations_on_success(self):
        recs = [
            {'title': 'Interstellar', 'year': 2014, 'source_title': 'Inception', 'rationale': 'similar themes'},
            {'title': 'Tenet',        'year': 2020, 'source_title': 'Inception', 'rationale': 'same director'},
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(json.dumps(recs))
        )
        history = [{'title': 'Inception', 'year': 2010}]
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=mock_client), \
             patch('api_service.services.llm.llm_service.load_env_vars', return_value={'LLM_MODEL': 'gpt-4o-mini'}):
            result = await get_recommendations_from_history(history, max_results=5)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['title'], 'Interstellar')

    async def test_filters_out_recs_that_are_in_watch_history(self):
        recs = [
            {'title': 'Inception', 'year': 2010, 'source_title': 'Inception', 'rationale': 'dupe'},
            {'title': 'Tenet',     'year': 2020, 'source_title': 'Inception', 'rationale': 'good pick'},
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(json.dumps(recs))
        )
        history = [{'title': 'Inception', 'year': 2010}]
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=mock_client), \
             patch('api_service.services.llm.llm_service.load_env_vars', return_value={'LLM_MODEL': 'gpt-4o-mini'}):
            result = await get_recommendations_from_history(history, max_results=5)
        titles = [r['title'] for r in result]
        self.assertNotIn('Inception', titles)
        self.assertIn('Tenet', titles)

    async def test_returns_empty_list_on_json_decode_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response('not valid json {{{{')
        )
        history = [{'title': 'Inception', 'year': 2010}]
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=mock_client), \
             patch('api_service.services.llm.llm_service.load_env_vars', return_value={'LLM_MODEL': 'gpt-4o-mini'}):
            result = await get_recommendations_from_history(history, max_results=5)
        self.assertEqual(result, [])

    async def test_strips_markdown_code_fences(self):
        recs = [
            {'title': 'Tenet', 'year': 2020, 'source_title': 'Inception', 'rationale': 'ok'},
        ]
        content = '```json\n' + json.dumps(recs) + '\n```'
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(content)
        )
        history = [{'title': 'Inception', 'year': 2010}]
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=mock_client), \
             patch('api_service.services.llm.llm_service.load_env_vars', return_value={'LLM_MODEL': 'gpt-4o-mini'}):
            result = await get_recommendations_from_history(history, max_results=5)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# interpret_search_query (async)
# ---------------------------------------------------------------------------

class TestInterpretSearchQuery(unittest.IsolatedAsyncioTestCase):

    async def test_returns_empty_dict_when_no_llm_client(self):
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=None):
            result = await interpret_search_query('psychological thriller', [])
        self.assertEqual(result, {})

    async def test_returns_parsed_result_on_success(self):
        response_content = json.dumps({
            'discover_params': {'genres': ['Thriller'], 'year_from': 1990, 'sort_by': 'vote_average.desc'},
            'suggested_titles': [
                {'title': 'Se7en', 'year': 1995, 'rationale': 'Dark thriller.'},
            ],
        })
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(response_content)
        )
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=mock_client), \
             patch('api_service.services.llm.llm_service.load_env_vars', return_value={'LLM_MODEL': 'gpt-4o-mini'}):
            result = await interpret_search_query('dark psychological thriller from 90s', [])

        self.assertIn('discover_params', result)
        self.assertIn('suggested_titles', result)
        self.assertEqual(result['suggested_titles'][0]['title'], 'Se7en')

    async def test_returns_empty_dict_on_json_decode_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response('not json {{{{')
        )
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=mock_client), \
             patch('api_service.services.llm.llm_service.load_env_vars', return_value={'LLM_MODEL': 'gpt-4o-mini'}):
            result = await interpret_search_query('thriller', [])
        self.assertEqual(result, {})

    async def test_filters_suggested_titles_without_required_keys(self):
        response_content = json.dumps({
            'discover_params': {},
            'suggested_titles': [
                {'title': 'Se7en', 'year': 1995, 'rationale': 'ok'},
                {'only_title': 'Incomplete'},   # missing 'year'
                {'year': 2001},                  # missing 'title'
            ],
        })
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(response_content)
        )
        with patch('api_service.services.llm.llm_service.get_llm_client', return_value=mock_client), \
             patch('api_service.services.llm.llm_service.load_env_vars', return_value={'LLM_MODEL': 'gpt-4o-mini'}):
            result = await interpret_search_query('thriller', [])
        self.assertEqual(len(result['suggested_titles']), 1)


if __name__ == '__main__':
    unittest.main()
