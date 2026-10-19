"""Recap behavior against isolated SQLite, including concurrent browser sessions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from decimal import Decimal

import pytest
from flask import Flask, g

from api_service.db.recap_repository import (
    RecapRepository, badge_progress, initialize_recap_schema, insert_ignore,
)

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
ADMIN = {'id': 1, 'role': 'admin'}
USER = {'id': 2, 'role': 'user'}


@pytest.fixture
def db(tmp_path):
    import api_service.db.database_manager as module
    previous = module.DatabaseManager._instance
    module.DatabaseManager._instance = None
    with patch.object(module, 'DB_PATH', str(tmp_path / 'recap.db')), \
            patch.object(module, 'load_env_vars', return_value={'DB_TYPE': 'sqlite'}):
        database = module.DatabaseManager()
        yield database
    module.DatabaseManager._instance = previous


def seed(db, count=100, age=20, user_id='alice', start=0, requested_by='SuggestArr'):
    with db.get_connection() as conn:
        conn.cursor().executemany(
            'INSERT INTO requests (tmdb_request_id,media_type,user_id,requested_at,requested_by) VALUES (?,?,?,?,?)',
            [(str(i), 'movie' if i % 2 == 0 else 'tv', user_id,
              (NOW - timedelta(days=age)).replace(tzinfo=None), requested_by) for i in range(start, start + count)],
        )
        conn.commit()
    initialize_recap_schema(db)


def summary(db, user=ADMIN, env=None, **kwargs):
    return RecapRepository(db).summary(user, env or {}, now=NOW, **kwargs)


def test_backfill_is_idempotent_excludes_seer_and_preserves_cleanup(db):
    seed(db, 10)
    seed(db, 5, start=10, requested_by='Seer')
    initialize_recap_schema(db)
    result = summary(db)
    assert (result['total'], result['movies'], result['tv']) == (10, 5, 5)
    with db.get_connection() as conn:
        conn.execute('DELETE FROM requests')
        conn.commit()
    initialize_recap_schema(db)
    assert summary(db)['total'] == 10


def test_successful_save_is_transactional_and_deduplicated(db):
    db.save_request('movie', '42', 'source', 'alice')
    db.save_request('movie', '42', 'another-source', 'bob')
    assert summary(db)['total'] == 1
    db.delete_request_row('42', 'movie')
    assert summary(db)['total'] == 1
    with db.get_connection() as conn:
        assert conn.execute('SELECT user_id FROM recap_titles').fetchone()[0] == 'alice'
    db.save_request('movie', '42', 'source', 'alice')
    assert summary(db)['total'] == 1


def test_ledger_failure_rolls_back_canonical_insert(db):
    with db.get_connection() as conn:
        conn.execute('DROP TABLE recap_titles')
        conn.commit()
    with pytest.raises(Exception, match='recap_titles'):
        db.save_request('movie', '42', 'source')
    with db.get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 0


def test_skipped_failed_and_imported_titles_never_enter_ledger(db):
    seed(db, 1, requested_by='Seer')
    db.save_request('movie', '0', 'source')  # An ignored insert must not relabel an imported request.
    assert summary(db)['total'] == 0


@pytest.mark.parametrize('mode', ['all', 'own', 'own_all'])
def test_regular_users_only_get_their_linked_profiles_in_all_modes(db, mode):
    seed(db, 3)
    seed(db, 4, start=3, user_id='bob')
    with patch.object(db, 'get_user_media_profiles', return_value=[{'provider': 'plex', 'external_user_id': 'alice'}]):
        result = summary(db, USER, {'REQUEST_VISIBILITY': mode})
    assert result['scope'] == 'personal'
    assert result['total'] == 3


def test_no_links_means_empty_recap_and_admin_own_all_is_restricted(db):
    seed(db)
    with patch.object(db, 'get_user_media_profiles', return_value=[]):
        result = summary(db, USER)
        assert result['total'] == 0
        assert result['has_linked_profiles'] is False
        assert summary(db, ADMIN, {'REQUEST_VISIBILITY': 'own_all'})['total'] == 0
    assert summary(db, ADMIN, {'REQUEST_VISIBILITY': 'own'})['total'] == 100


def test_poster_data_is_opt_in_and_scoped(db):
    seed(db, 2)
    seed(db, 1, start=2, user_id='bob')
    with db.get_connection() as conn:
        conn.executemany('INSERT INTO metadata(media_id,media_type,poster_path) VALUES (?,?,?)',
                         [('0', 'movie', '/alice.jpg'), ('2', 'movie', '/bob.jpg')])
        conn.commit()
    with patch.object(db, 'get_user_media_profiles', return_value=[{'provider': 'plex', 'external_user_id': 'alice'}]):
        assert summary(db, USER)['posters'] == []
        assert [p['poster_path'] for p in summary(db, USER, include_posters=True)['posters']] == ['/alice.jpg']


def test_featured_covers_are_the_four_highest_rated_titles_in_the_callers_scope(db):
    seed(db, 6)
    seed(db, 1, start=6, user_id='bob')
    with db.get_connection() as conn:
        conn.executemany('INSERT INTO metadata(media_id,media_type,poster_path,title,rating) VALUES (?,?,?,?,?)',
                         [(str(i), 'movie' if i % 2 == 0 else 'tv', f'/poster-{i}.jpg', f'Title {i}', i + 1)
                          for i in range(7)])
        conn.commit()
    with patch.object(db, 'get_user_media_profiles', return_value=[{'provider': 'plex', 'external_user_id': 'alice'}]):
        posters = summary(db, USER, include_posters=True)['posters']
    assert [p['title'] for p in posters] == ['Title 5', 'Title 4', 'Title 3', 'Title 2']
    assert [p['rating'] for p in posters] == [6.0, 5.0, 4.0, 3.0]


def test_anniversary_and_title_badges_use_exact_boundaries():
    badges, next_badge = badge_progress(100, NOW - timedelta(days=365), NOW)
    assert [b['id'] for b in badges if b['unlocked']] == ['titles_10', 'titles_100', 'one_year']
    assert next_badge['threshold'] == 500
    assert not badge_progress(9, NOW - timedelta(days=365) + timedelta(seconds=1), NOW)[0][-1]['unlocked']


@pytest.mark.parametrize('count,age,eligible', [(99, 30, False), (100, 13, False), (100, 14, True), (1000, 50, True)])
def test_first_prompt_threshold_age_and_highest_milestone(db, count, age, eligible):
    seed(db, count, age=age)
    prompt = RecapRepository(db).claim_prompt(ADMIN, {}, NOW)
    assert bool(prompt) == eligible
    if prompt:
        assert prompt['milestone'] == (1000 if count == 1000 else 100)
        assert RecapRepository(db).claim_prompt(ADMIN, {}, NOW) is None


def test_new_threshold_waits_90_days_and_semester_waits_180(db):
    seed(db)
    repo = RecapRepository(db)
    assert repo.claim_prompt(ADMIN, {}, NOW)
    seed(db, 400, start=100)
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=89)) is None
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=90))['milestone'] == 500
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=269)) is None
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=270))['milestone'] == 500


def test_snooze_repeats_same_invitation_after_30_days_even_when_new_threshold_exists(db):
    seed(db)
    repo = RecapRepository(db)
    repo.claim_prompt(ADMIN, {}, NOW)
    repo.update_preferences(ADMIN, {}, 'remind_later', NOW)
    seed(db, 400, start=100)
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=29)) is None
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=30))['milestone'] == 100
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=119)) is None
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=120))['milestone'] == 500


def test_dismiss_archives_prompt_until_next_milestone_or_semester(db):
    seed(db)
    repo = RecapRepository(db)
    repo.claim_prompt(ADMIN, {}, NOW)
    repo.update_preferences(ADMIN, {}, 'dismiss', NOW)
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=90)) is None
    assert repo.claim_prompt(ADMIN, {}, NOW + timedelta(days=180))


@pytest.mark.parametrize('action', ['disable', 'supported'])
def test_preferences_persist_per_admin_across_scopes_and_can_be_reenabled(db, action):
    seed(db)
    repo = RecapRepository(db)
    repo.update_preferences(ADMIN, {}, action, NOW)
    assert RecapRepository(db).claim_prompt(ADMIN, {}, NOW) is None
    with patch.object(db, 'get_user_media_profiles', return_value=[{'provider': 'plex', 'external_user_id': 'alice'}]):
        assert repo.claim_prompt(ADMIN, {'REQUEST_VISIBILITY': 'own_all'}, NOW) is None
    assert repo.claim_prompt({'id': 3, 'role': 'admin'}, {}, NOW)
    repo.update_preferences(ADMIN, {}, 'enable', NOW)
    assert repo.claim_prompt(ADMIN, {}, NOW)


def test_personal_and_installation_prompt_history_are_separate(db):
    seed(db)
    repo = RecapRepository(db)
    assert repo.claim_prompt(ADMIN, {}, NOW)['scope'] == 'installation'
    with patch.object(db, 'get_user_media_profiles', return_value=[{'provider': 'plex', 'external_user_id': 'alice'}]):
        assert repo.claim_prompt(ADMIN, {'REQUEST_VISIBILITY': 'own_all'}, NOW)['scope'] == 'personal'


def test_synthetic_bypass_admin_needs_no_auth_user_row(db):
    seed(db)
    repo = RecapRepository(db)
    synthetic = {'id': '0', 'role': 'admin'}
    assert repo.claim_prompt(synthetic, {}, NOW)
    assert repo.update_preferences(synthetic, {}, 'supported', NOW)['reminder_mode'] == 'supported'


def test_concurrent_tabs_only_claim_once(db):
    seed(db)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: RecapRepository(db).claim_prompt(ADMIN, {}, NOW), range(4)))
    assert sum(result is not None for result in results) == 1


@pytest.mark.parametrize('db_type,prefix,suffix', [
    ('sqlite', 'INSERT OR IGNORE', ''), ('mysql', 'INSERT IGNORE', ''),
    ('mariadb', 'INSERT IGNORE', ''), ('postgres', 'INSERT', ' ON CONFLICT DO NOTHING'),
])
def test_insert_dialect(db_type, prefix, suffix):
    assert insert_ignore(db_type, 'recap_preferences', 'user_id', 'VALUES (?)') == f'{prefix} INTO recap_preferences (user_id) VALUES (?){suffix}'


@pytest.mark.parametrize('db_type', ['mysql', 'mariadb', 'postgres'])
def test_external_recap_summary_is_numeric_and_uses_native_parameters(db_type):
    db = MagicMock(db_type=db_type)
    db.get_user_media_profiles.return_value = [{'provider': 'plex', 'external_user_id': 'alice'}]
    cursor = db.get_connection.return_value.__enter__.return_value.cursor.return_value
    cursor.fetchone.side_effect = [(4, Decimal(3), Decimal(1), NOW), None]
    result = RecapRepository(db).summary(USER, {}, now=NOW)
    assert result['movies'] == 3 and isinstance(result['movies'], int)
    assert result['tv'] == 1 and isinstance(result['tv'], int)
    assert all('?' not in call.args[0] for call in cursor.execute.call_args_list)
    assert cursor.execute.call_args_list[0].args[1] == ('alice',)


@pytest.mark.parametrize('db_type', ['mysql', 'mariadb', 'postgres'])
def test_external_recap_schema_has_portable_keys_and_backfill(db_type):
    db = MagicMock(db_type=db_type)
    cursor = db.get_connection.return_value.__enter__.return_value.cursor.return_value
    cursor.fetchall.return_value = []
    initialize_recap_schema(db)
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert any('PRIMARY KEY (media_type, tmdb_id)' in sql for sql in statements)
    assert any('PRIMARY KEY (user_id, scope)' in sql for sql in statements)
    assert all('AUTOINCREMENT' not in sql and 'FOREIGN KEY' not in sql for sql in statements)
    backfill = statements[-1]
    assert "WHERE requested_by='SuggestArr'" in backfill
    assert ('ON CONFLICT DO NOTHING' if db_type == 'postgres' else 'INSERT IGNORE') in backfill


def route_client(db, user=ADMIN):
    from api_service.blueprints.recap.routes import recap_bp
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def identity():
        g.current_user = user

    app.register_blueprint(recap_bp, url_prefix='/api/recap')
    return app.test_client()


@pytest.mark.parametrize('user,status', [(None, 401), (USER, 403)])
def test_support_mutations_require_admin(db, user, status):
    client = route_client(db, user)
    assert client.post('/api/recap/prompt').status_code == status
    assert client.patch('/api/recap/preferences', json={'action': 'disable'}).status_code == status
    if user is None:
        assert client.get('/api/recap').status_code == 401


@pytest.mark.parametrize('payload', [None, [], {}, {'action': 'invalid'}, {'action': []}, {'action': 'disable', 'user_id': 2}])
def test_preferences_reject_invalid_payloads(db, payload):
    assert route_client(db).patch('/api/recap/preferences', json=payload).status_code == 400


def test_route_does_not_accept_scope_or_other_user_override(db):
    from api_service.blueprints.recap import routes
    seed(db)
    with patch.object(routes, 'DatabaseManager', return_value=db), patch.object(routes, 'load_env_vars', return_value={}), \
            patch.object(db, 'get_user_media_profiles', return_value=[]):
        response = route_client(db, USER).get('/api/recap?scope=installation&user_id=1&include_posters=true')
    assert response.status_code == 200
    assert response.json['data']['total'] == 0
    assert response.json['data']['posters'] == []


def test_route_errors_do_not_leak_internal_details(db):
    from api_service.blueprints.recap import routes
    with patch.object(routes, 'DatabaseManager', side_effect=RuntimeError('private database credentials')):
        response = route_client(db).get('/api/recap')
    assert response.status_code == 500
    assert 'credentials' not in response.get_data(as_text=True)


def test_signed_jwt_flow_through_auth_middleware_routes_and_sqlite(db):
    """Use production authentication and real SQL for the complete API exchange."""
    import jwt
    from api_service.auth import middleware, auth_service
    from api_service.blueprints.recap import routes

    seed(db, age=400)
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.before_request(middleware.enforce_authentication)
    app.register_blueprint(routes.recap_bp, url_prefix='/api/recap')
    client = app.test_client()
    key = 'isolated-recap-test-signing-key-never-used-in-production'
    token = jwt.encode({'sub': '1', 'role': 'admin', 'username': 'test-admin',
                        'exp': datetime.now(timezone.utc) + timedelta(minutes=5)}, key, algorithm='HS256')
    with patch.object(auth_service, 'load_secret_key', return_value=key), \
            patch.object(middleware, 'load_env_vars', return_value={'AUTH_MODE': 'enabled'}), \
            patch.object(middleware, '_is_setup_mode', return_value=False), \
            patch.object(routes, 'DatabaseManager', return_value=db), \
            patch.object(routes, 'load_env_vars', return_value={}):
        assert client.get('/api/recap').status_code == 401
        assert client.get('/api/recap', headers={'Authorization': 'Bearer invalid'}).status_code == 401
        client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        result = client.get('/api/recap')
        assert result.status_code == 200
        assert result.json['data']['total'] == 100
        prompt = client.post('/api/recap/prompt')
        assert prompt.status_code == 200
        assert prompt.json['data']['prompt']['milestone'] == 100
        assert client.post('/api/recap/prompt').json['data']['prompt'] is None
        saved = client.patch('/api/recap/preferences', json={'action': 'supported'})
        assert saved.status_code == 200
        assert saved.json['data']['reminder_mode'] == 'supported'
        assert client.get('/api/recap').json['data']['preferences']['reminder_mode'] == 'supported'
        assert client.post('/api/recap/prompt').json['data']['prompt'] is None
