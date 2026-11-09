"""Already-handled titles are named in the AI Search prompt instead of only filtered afterwards."""

import asyncio
import logging
import sqlite3
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.db.components.ai_search_mixin import AiSearchMixin
from api_service.db.components.request_mixin import RequestMixin
from api_service.db.components.schema_manager import SchemaManager
from api_service.db.components.suggestion_feedback_mixin import SuggestionFeedbackMixin
from api_service.services.ai_search.ai_search_service import AiSearchService
from api_service.services.llm.llm_service import MAX_EXCLUSION_ITEMS


class MemoryDB(AiSearchMixin, RequestMixin, SuggestionFeedbackMixin):
    db_type = 'sqlite'
    logger = logging.getLogger('exclusions-test')

    def __init__(self):
        self.connection = sqlite3.connect(':memory:')
        SchemaManager(self).initialize_db()

    @contextmanager
    def get_connection(self):
        yield self.connection

    def add_metadata(self, media_id, media_type, title, released=None):
        self.connection.execute(
            "INSERT INTO metadata(media_id, media_type, title, release_date) VALUES(?,?,?,?)",
            (str(media_id), media_type, title, released))
        self.connection.commit()


@pytest.fixture
def db():
    memory = MemoryDB()
    yield memory
    memory.connection.close()


def test_titles_for_ids_skip_unknown_placeholder_and_other_media_type(db):
    db.add_metadata(1, 'movie', 'Se7en', '1995-09-22')
    db.add_metadata(2, 'movie', None)
    db.add_metadata(3, 'movie', 'Unknown Title')
    db.add_metadata(4, 'movie', '   ')
    db.add_metadata(5, 'tv', 'A Show', '2010-01-01')
    assert db.get_titles_for_tmdb_ids('movie', ['1', '2', '3', '4', '5', '999']) == [{'title': 'Se7en', 'year': 1995}]
    assert db.get_titles_for_tmdb_ids('tv', ['5']) == [{'title': 'A Show', 'year': 2010}]


def test_titles_for_ids_respect_limit_and_span_several_chunks(db):
    for i in range(1, 1201):
        db.add_metadata(i, 'movie', f'Film {i}')
    assert len(db.get_titles_for_tmdb_ids('movie', range(1, 1201), limit=1200)) == 1200
    assert len(db.get_titles_for_tmdb_ids('movie', range(1, 1201), limit=7)) == 7


def test_requested_ids_by_type_only_returns_that_type_and_suggestarr_requests(db):
    db.connection.executemany(
        "INSERT INTO requests(tmdb_request_id, media_type, requested_by) VALUES(?,?,?)",
        [('10', 'movie', 'SuggestArr'), ('11', 'tv', 'SuggestArr'), ('12', 'movie', 'someone-else')])
    db.connection.commit()
    assert db.get_requested_tmdb_ids_by_type('movie') == {'10'}
    assert db.get_requested_tmdb_ids_by_type('tv') == {'11'}
    # One id can only be requested once, so a movie id never shows up under tv.
    assert '10' not in db.get_requested_tmdb_ids_by_type('tv')


def test_negative_feedback_titles_exclude_interested_and_saved(db):
    db.connection.execute("INSERT INTO auth_users(id, username, password_hash) VALUES(5, 'u', 'x')")
    for tmdb_id, feedback, title in [('1', 'already_seen', 'Seen One'), ('2', 'interested', 'Want It'),
                                     ('3', 'save_for_later', 'Saved'), ('4', 'not_interested', None)]:
        db.set_media_feedback(5, '', tmdb_id, 'movie', feedback, None, None, title, None)
    rows = db.list_negative_feedback_titles(5, '', 'movie')
    assert sorted((row['tmdb_id'], row['title']) for row in rows) == [('1', 'Seen One'), ('4', None)]
    assert db.list_negative_feedback_titles(6, '', 'movie') == []


class FakeDb:
    """The slice of the database `_build_excluded_titles` reads."""

    def __init__(self, **kwargs):
        self.data = {'feedback': [], 'dislikes': [], 'requested': set(), 'seen': set(), 'titles': {}}
        self.data.update(kwargs)

    def list_negative_feedback_titles(self, user_id, media_user_id, media_type):
        return self.data['feedback']

    def get_ai_dislikes(self, media_type):
        return self.data['dislikes']

    def get_requested_tmdb_ids_by_type(self, media_type):
        return self.data['requested']

    def get_ai_seen_ids(self, media_type):
        return self.data['seen']

    def get_titles_for_tmdb_ids(self, media_type, ids, limit=150):
        known = self.data['titles']
        return [{'title': known[i], 'year': 2000} for i in sorted(ids) if i in known][:limit]


def _build(db, **overrides):
    args = dict(history=[], exclude_watched=True, exclude_seen=False, feedback_scope=(5, ''), owned_ids=set())
    args.update(overrides)
    return AiSearchService._build_excluded_titles(
        db, 'movie', args['history'], args['exclude_watched'], args['exclude_seen'],
        args['feedback_scope'], args['owned_ids'])


def test_excluded_titles_follow_priority_and_dedupe_case_insensitively():
    db = FakeDb(
        feedback=[{'tmdb_id': '1', 'title': 'Dismissed', 'year': 1999}, {'tmdb_id': '2', 'title': None, 'year': None}],
        dislikes=[{'title': 'dismissed', 'year': 1999}, {'title': 'Legacy', 'year': 2001}],
        requested={'3'}, seen={'5'},
        titles={'2': 'Named Later', '3': 'Requested', '4': 'Owned', '5': 'Seen Before'})
    titles = [entry['title'] for entry in _build(db, owned_ids={'4'}, exclude_seen=True)]
    assert titles == ['Dismissed', 'Named Later', 'Legacy', 'Requested', 'Owned', 'Seen Before']
    assert 'Seen Before' not in [entry['title'] for entry in _build(db, owned_ids={'4'})]


def test_overlapping_groups_do_not_starve_later_titles():
    # 100 dismissed titles are also the first 100 requested ones; the 50 free slots must
    # still be filled from the distinct requested titles after them.
    titles = {str(i): f'Film {i:03d}' for i in range(200)}
    feedback = [{'tmdb_id': str(i), 'title': f'Film {i:03d}', 'year': 2000} for i in range(100)]
    db = FakeDb(feedback=feedback, requested=set(titles), titles=titles)
    result = _build(db)
    assert len(result) == MAX_EXCLUSION_ITEMS
    assert result[-1]['title'] == 'Film 149'


def test_titles_already_in_the_prompt_history_and_placeholders_are_not_repeated():
    history = [{'title': 'Seen Recently', 'year': 2020}]
    db = FakeDb(feedback=[{'tmdb_id': '1', 'title': 'seen recently', 'year': 2020},
                          {'tmdb_id': '2', 'title': 'Unknown Title', 'year': None},
                          {'tmdb_id': '3', 'title': 'Real Dismissed', 'year': 2001}],
                requested={'4'}, titles={'4': 'Unknown Title'})
    assert [entry['title'] for entry in _build(db, history=history)] == ['Real Dismissed']


def test_watched_beyond_the_prompts_history_only_listed_when_watched_are_excluded():
    # 20 episodes of one show come first; the prompt dedupes them to ONE entry, so the
    # titles after it are still inside the prompt's own first 20 and must not be repeated.
    history = [{'title': 'Show', 'year': 2010}] * 20 + [{'title': f'Film {i}', 'year': 2000} for i in range(25)]
    listed = [entry['title'] for entry in _build(FakeDb(), history=history)]
    assert listed == [f'Film {i}' for i in range(19, 25)]
    assert _build(FakeDb(), history=history, exclude_watched=False) == []


def test_excluded_titles_are_one_clean_line_and_capped():
    db = FakeDb(feedback=[{'tmdb_id': str(i), 'title': f'Evil\nTitle {i}', 'year': 2000} for i in range(400)])
    result = _build(db)
    assert len(result) == MAX_EXCLUSION_ITEMS
    assert all('\n' not in entry['title'] for entry in result)
    assert result[0]['title'] == 'Evil Title 0'


def _tmdb_item(tmdb_id):
    return {'id': tmdb_id, 'title': f'Film {tmdb_id}', 'release_date': '2000-01-01', 'overview': '', 'vote_average': 7.0,
            'genre_ids': [], 'poster_path': None, 'backdrop_path': None, 'original_language': 'en'}


class TestSearchSinglePromptWiring:
    """`_search_single` asks for headroom and does not wait for a slow library."""

    @staticmethod
    def _service():
        with patch.object(AiSearchService, '__init__', lambda self: None):
            service = AiSearchService()
        service.config = {}
        return service

    async def _run(self, max_results, owned_ids=None, timeout=None):
        service = self._service()
        interpret = AsyncMock(return_value={'discover_params': {}, 'suggested_titles': []})
        mock_tmdb = MagicMock()
        mock_tmdb.omdb_client = None
        mock_tmdb.__aenter__ = AsyncMock(return_value=mock_tmdb)
        mock_tmdb.__aexit__ = AsyncMock(return_value=False)
        with patch('api_service.services.ai_search.ai_search_service.interpret_search_query', interpret), \
             patch.object(service, '_get_history', AsyncMock(return_value=[])), \
             patch.object(service, '_make_tmdb_client', return_value=mock_tmdb), \
             patch.object(service, '_excluded_titles_for_prompt', wraps=service._excluded_titles_for_prompt), \
             patch('api_service.services.ai_search.ai_search_service._OWNED_PROMPT_TIMEOUT', timeout or 5.0), \
             patch('api_service.db.database_manager.DatabaseManager') as MockDB:
            MockDB.return_value.get_requested_tmdb_ids.return_value = set()
            MockDB.return_value.get_ai_dislike_ids.return_value = []
            MockDB.return_value.get_ai_likes.return_value = []
            MockDB.return_value.get_ai_dislikes.return_value = []
            MockDB.return_value.get_requested_tmdb_ids_by_type.return_value = set()
            MockDB.return_value.get_titles_for_tmdb_ids.return_value = [{'title': 'Owned Film', 'year': 1999}]
            result = await service._search_single('q', 'movie', None, max_results, owned_ids=owned_ids)
        return interpret, result

    @pytest.mark.asyncio
    @pytest.mark.parametrize('requested, expected', [(4, 12), (12, 18), (24, 36), (50, 50), (10**400, 10**400)])
    async def test_candidate_count_has_headroom_but_never_drops_below_max_results(self, requested, expected):
        interpret, _ = await self._run(requested)
        assert interpret.call_args.kwargs['max_suggestions'] == expected

    @pytest.mark.asyncio
    async def test_owned_titles_reach_the_prompt(self):
        interpret, _ = await self._run(12, owned_ids={'movie': {'7'}})
        assert interpret.call_args.kwargs['excluded_titles'] == [{'title': 'Owned Film', 'year': 1999}]

    @pytest.mark.asyncio
    async def test_slow_library_does_not_block_the_prompt_but_still_filters_later(self):
        async def slow():
            await asyncio.sleep(0.3)
            return {'movie': {'7'}}

        future = asyncio.ensure_future(slow())
        interpret, _ = await self._run(12, owned_ids=future, timeout=0.05)
        assert interpret.call_args.kwargs['excluded_titles'] == []
        assert future.done() and future.result() == {'movie': {'7'}}  # the filter step awaited it

    @pytest.mark.asyncio
    async def test_failed_library_load_does_not_break_the_search(self):
        async def broken():
            raise RuntimeError('library offline')

        interpret, result = await self._run(12, owned_ids=asyncio.ensure_future(broken()))
        assert interpret.call_args.kwargs['excluded_titles'] == []
        assert result['results'] == []


def test_ai_search_queries_use_mysql_placeholders_for_mariadb(db):
    db.db_type = 'mariadb'
    statements = []

    class Cursor:
        def execute(self, sql, params=()):
            statements.append(sql)

        def fetchall(self):
            return []

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        yield Conn()

    db.get_connection = connection
    db.get_ai_dislikes('movie')
    db.get_ai_seen_ids('movie')
    db.get_titles_for_tmdb_ids('movie', ['1'])
    assert statements and all('?' not in sql and '%s' in sql for sql in statements)
