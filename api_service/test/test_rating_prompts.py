"""Tests for one-tap rating prompts: eligibility, delivery policy, answer security and settings."""
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import AsyncMock, patch

import pytest
from flask import Flask, g

from api_service.blueprints.users import routes
from api_service.db import database_manager as dm_mod
from api_service.db.components.schema_manager import SchemaManager
from api_service.db.database_manager import DatabaseManager
from api_service.jobs import rating_prompts as job
from api_service.services.notification_formats import render_rating_prompt


class FakeTelegram:
    """A local Bot API: records calls, serves queued updates, can be told to fail sendMessage."""

    def __init__(self):
        self.calls = []
        self.updates = []
        self.send_reply = (200, {'ok': True, 'result': {}})
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
                method = self.path.rsplit('/', 1)[-1].split('?')[0]
                outer.calls.append((method, body))
                if method == 'sendMessage':
                    status, reply = outer.send_reply
                elif method == 'getUpdates':
                    status, reply = 200, {'ok': True, 'result': outer.updates}
                else:
                    status, reply = 200, {'ok': True, 'result': True}
                raw = json.dumps(reply).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_port}/bot123:abc'

    def of(self, method):
        return [body for name, body in self.calls if name == method]


@pytest.fixture
def tg():
    fake = FakeTelegram()
    job._offsets.clear()
    job._warned.clear()
    yield fake
    fake.server.shutdown()


@pytest.fixture
def db(tmp_path):
    with (
        patch.object(dm_mod, 'DB_PATH', str(tmp_path / 'rating.db')),
        patch('api_service.db.database_manager.load_env_vars', return_value={'DB_TYPE': 'sqlite'}),
        patch('api_service.services.watch_history_sync.ConfigService.get_runtime_config',
              return_value={'SELECTED_SERVICE': 'jellyfin'}),
    ):
        DatabaseManager._instance = None
        manager = DatabaseManager()
        with manager.get_connection() as conn:
            conn.execute("INSERT INTO auth_users(id,username,password_hash,role) VALUES "
                         "(1,'admin','h','admin'),(2,'ann','h','user'),(3,'bob','h','user')")
            conn.commit()
        yield manager
    DatabaseManager._instance = None


def _ago(hours):
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)


def _store_config(db, user_id, payload):
    """Write a rating-prompt config straight into the row (tests need a start date in the past)."""
    with db.get_connection() as conn:
        conn.execute('UPDATE auth_users SET rating_prompt_config=? WHERE id=?', (json.dumps(payload), user_id))
        conn.commit()


def _setup(db, tg, user_id=2, chat_id='555', verified=True, delay=12, enabled_hours_ago=100):
    """Opt a user in: verified Jellyfin link, own Telegram chat, settings enabled in the past."""
    db.create_user_media_profile(user_id, 'jellyfin', f'jf-{user_id}', f'u{user_id}', verified=verified)
    db.set_personal_notification(user_id, {'format': 'telegram', 'url': f'{tg.base}/sendMessage?chat_id={chat_id}',
                                           'allow_private': True})
    _store_config(db, user_id, {'enabled': True, 'delay_hours': delay, 'enabled_at': _ago(enabled_hours_ago).isoformat()})
    return db.upsert_media_user_identity('jellyfin', f'jf-{user_id}')


def _play(db, identity, tmdb_id, hours_ago, media_type='movie', title=None):
    db.record_server_plays(identity['id'], [{'tmdb_id': str(tmdb_id), 'media_type': media_type,
                                             'title': title or f'Title {tmdb_id}', 'year': 2020,
                                             'watched_at': _ago(hours_ago)}])


def _rating(db, identity, tmdb_id, media_type='movie'):
    return db.get_watched_media_item(identity['id'], str(tmdb_id), media_type)['rating']


def _run_prompts(synced=([], False, 0)):
    with patch.object(job, 'sync_identity_history', return_value=synced) as sync:
        job.run_rating_prompts()
    return sync


def _tap(prompt_text_body, n, sender=555, chat=555, update_id=1):
    """A Telegram update for tapping button n of a recorded sendMessage body."""
    data = prompt_text_body['reply_markup']['inline_keyboard'][(n - 1) // 5][(n - 1) % 5]['callback_data']
    return {'update_id': update_id, 'callback_query': {
        'id': f'cb{update_id}', 'data': data, 'from': {'id': sender}, 'message': {'chat': {'id': chat}}}}


# ── what is asked, and when ────────────────────────────────────────────────

def test_only_played_unrated_unexcluded_titles_past_the_delay_are_asked_once(db, tg):
    me = _setup(db, tg)
    _play(db, me, 1, 13)                          # asked
    _play(db, me, 2, 11)                          # still within the delay
    _play(db, me, 3, 13)                          # already rated
    db.update_watched_media(me['id'], db.get_watched_media_item(me['id'], '3', 'movie')['id'], {'rating': 9})
    _play(db, me, 4, 13)                          # excluded
    db.update_watched_media(me['id'], db.get_watched_media_item(me['id'], '4', 'movie')['id'], {'excluded': True})
    _play(db, me, 5, 150)                         # played before the user opted in
    _play(db, me, 6, 13, media_type='tv')         # a show is one title however many episodes
    db.upsert_watched_media(me['id'], 7, 'movie', 'Imported', rating=None)  # no play date: never asked
    _run_prompts()
    _run_prompts()                                # a second run asks nothing new
    texts = sorted(body['text'] for body in tg.of('sendMessage'))
    assert texts == ['What did you think of Title 1 (2020)?', 'What did you think of Title 6 (2020)?']


def test_delay_is_measured_from_the_latest_play_of_a_show(db, tg):
    me = _setup(db, tg)
    _play(db, me, 6, 20, media_type='tv')
    _play(db, me, 6, 2, media_type='tv')          # a later episode moves the play date forward
    _run_prompts()
    assert tg.of('sendMessage') == []


def test_prompts_per_run_are_capped(db, tg):
    me = _setup(db, tg)
    for n in range(1, 8):
        _play(db, me, n, 13)
    _run_prompts()
    assert len(tg.of('sendMessage')) == job.MAX_PROMPTS_PER_RUN
    _run_prompts()
    assert len(tg.of('sendMessage')) == 7


@pytest.mark.parametrize('synced', [None, ([], True, 0)])
def test_unavailable_or_partial_history_sends_nothing(db, tg, synced):
    me = _setup(db, tg)
    _play(db, me, 1, 13)
    _run_prompts(synced)
    assert tg.of('sendMessage') == []


def test_a_failing_sync_sends_nothing(db, tg):
    me = _setup(db, tg)
    _play(db, me, 1, 13)
    with patch.object(job, 'sync_identity_history', side_effect=RuntimeError('down')):
        job.run_rating_prompts()
    assert tg.of('sendMessage') == []


def test_deactivated_unverified_or_non_telegram_users_are_not_synced_or_asked(db, tg):
    me = _setup(db, tg)
    _play(db, me, 1, 13)
    with db.get_connection() as conn:
        conn.execute('UPDATE auth_users SET is_active=0 WHERE id=2')
        conn.commit()
    assert not _run_prompts().called
    with db.get_connection() as conn:
        conn.execute('UPDATE auth_users SET is_active=1 WHERE id=2')
        conn.commit()
    db.set_personal_notification(2, {'format': 'discord', 'url': 'https://discord.com/api/webhooks/1/x'})
    assert not _run_prompts().called
    db.set_personal_notification(2, {'format': 'telegram', 'url': f'{tg.base}/sendMessage?chat_id=-100'})
    assert not _run_prompts().called
    assert tg.of('sendMessage') == []


def test_unverified_media_link_is_not_prompted(db, tg):
    me = _setup(db, tg, verified=False)
    _play(db, me, 1, 13)
    assert not _run_prompts().called


# ── delivery policy ────────────────────────────────────────────────────────

def test_a_definite_telegram_rejection_leaves_no_claim_and_is_retried(db, tg):
    me = _setup(db, tg)
    _play(db, me, 1, 13)
    tg.send_reply = (400, {'ok': False, 'error_code': 400, 'description': 'chat not found'})
    _run_prompts()
    assert db.users_with_open_prompts() == []
    tg.send_reply = (200, {'ok': True, 'result': {}})
    _run_prompts()
    assert len(tg.of('sendMessage')) == 2 and db.users_with_open_prompts() == [2]


@pytest.mark.parametrize('reply', [(502, {'error': 'bad gateway'}), (200, {'weird': True}), (500, {'ok': False, 'error_code': 500})])
def test_an_ambiguous_send_is_never_repeated_and_its_button_still_works(db, tg, reply):
    me = _setup(db, tg)
    _play(db, me, 1, 13)
    tg.send_reply = reply
    _run_prompts()
    _run_prompts()
    assert len(tg.of('sendMessage')) == 1
    tg.updates = [_tap(tg.of('sendMessage')[0], 8)]
    job.run_rating_answers()
    assert _rating(db, me, 1) == 8


def test_marking_sent_never_reopens_an_answered_prompt(db, tg):
    me = _setup(db, tg)
    _play(db, me, 1, 13)
    prompt = db.claim_rating_prompt(2, me['id'], {'tmdb_id': '1', 'media_type': 'movie', 'title': 'T'})
    assert db.answer_rating_prompt_row(prompt['id'], prompt['nonce'], 7, me['id']) == 'saved'
    db.mark_rating_prompt_sent(prompt['id'])
    assert db.get_rating_prompt(prompt['id'])['status'] == 'answered'
    assert db.claim_rating_prompt(2, me['id'], {'tmdb_id': '1', 'media_type': 'movie', 'title': 'T'}) is None


def test_render_has_ten_buttons_and_short_callback_data():
    _, body = render_rating_prompt('https://api.telegram.org/botT/sendMessage?chat_id=555', 'Dune', 2021, 123456789, 'a' * 16)
    payload = json.loads(body)
    buttons = [b for row in payload['reply_markup']['inline_keyboard'] for b in row]
    assert [b['text'] for b in buttons] == [str(n) for n in range(1, 11)]
    assert all(len(b['callback_data'].encode()) < 64 for b in buttons)
    assert payload['chat_id'] == '555' and payload['text'] == 'What did you think of Dune (2021)?'


# ── answers ────────────────────────────────────────────────────────────────

def _open_prompt(db, tg):
    me = _setup(db, tg)
    _play(db, me, 1, 13)
    _run_prompts()
    return me, tg.of('sendMessage')[-1]


def _answer(db, tg, update):
    return job.answer_rating_prompt(db, tg.base, update['callback_query'])


def test_the_owner_tapping_in_their_private_chat_stores_the_rating_once(db, tg):
    me, sent = _open_prompt(db, tg)
    assert _answer(db, tg, _tap(sent, 8)) == 'Saved: 8/10 for Title 1'
    assert _rating(db, me, 1) == 8
    assert _answer(db, tg, _tap(sent, 3)) == 'Not available'  # second tap changes nothing
    assert _rating(db, me, 1) == 8


@pytest.mark.parametrize('kwargs', [
    {'sender': 999},                  # someone else, same chat
    {'chat': -100123, 'sender': 555}, # the owner's id but in a group chat
    {'chat': 999},                    # message from another chat
])
def test_taps_from_anyone_but_the_owner_in_their_own_chat_change_nothing(db, tg, kwargs):
    me, sent = _open_prompt(db, tg)
    assert _answer(db, tg, _tap(sent, 8, **kwargs)) == 'Not available'
    assert _rating(db, me, 1) is None


def test_missing_message_wrong_nonce_garbage_and_other_bots_are_refused(db, tg):
    me, sent = _open_prompt(db, tg)
    good = _tap(sent, 8)
    no_message = json.loads(json.dumps(good))
    del no_message['callback_query']['message']
    wrong_nonce = json.loads(json.dumps(good).replace(good['callback_query']['data'].split(':')[2], '0' * 16))
    for update in (no_message, wrong_nonce, {'callback_query': {'data': 'rp:1:zz:8', 'from': {'id': 555}}},
                   {'callback_query': {'data': 'rp:1:' + 'a' * 16 + ':11', 'from': {'id': 555}, 'message': {'chat': {'id': 555}}}}):
        assert job.answer_rating_prompt(db, tg.base, update['callback_query']) == 'Not available'
    assert job.answer_rating_prompt(db, tg.base.replace('123:abc', '999:zzz'), good['callback_query']) == 'Not available'
    out_of_range = json.loads(json.dumps(good).replace(':8"', ':11"'))
    assert job.answer_rating_prompt(db, tg.base, out_of_range['callback_query']) == 'Not available'
    assert _rating(db, me, 1) is None


@pytest.mark.parametrize('change', ['deactivate', 'disable', 'new_destination', 'no_destination', 'unlink', 'replace_link'])
def test_an_old_button_is_dead_once_the_owner_state_changes(db, tg, change):
    me, sent = _open_prompt(db, tg)
    if change == 'deactivate':
        with db.get_connection() as conn:
            conn.execute('UPDATE auth_users SET is_active=0 WHERE id=2')
            conn.commit()
    elif change == 'disable':
        db.set_rating_prompt_config(2, False, 12)
    elif change == 'new_destination':
        db.set_personal_notification(2, {'format': 'telegram', 'url': f'{tg.base}/sendMessage?chat_id=777', 'allow_private': True})
    elif change == 'no_destination':
        db.set_personal_notification(2, None)
    elif change == 'unlink':
        with db.get_connection() as conn:
            conn.execute('DELETE FROM user_media_profiles WHERE user_id=2')
            conn.commit()
    elif change == 'replace_link':
        with db.get_connection() as conn:
            conn.execute("UPDATE user_media_profiles SET external_user_id='jf-other' WHERE user_id=2")
            conn.commit()
    assert _answer(db, tg, _tap(sent, 8)) == 'Not available'
    assert _rating(db, me, 1) is None
    assert db.get_rating_prompt(1)['status'] in ('pending', 'sent')  # the claim was rolled back


def test_a_rating_made_elsewhere_is_not_overwritten_by_an_old_tap(db, tg):
    me, sent = _open_prompt(db, tg)
    db.update_watched_media(me['id'], db.get_watched_media_item(me['id'], '1', 'movie')['id'], {'rating': 4})
    assert _answer(db, tg, _tap(sent, 9)) == 'Already rated'
    assert _rating(db, me, 1) == 4
    assert db.get_rating_prompt(1)['status'] == 'answered'


def test_a_failed_rating_write_rolls_the_claim_back(db, tg):
    me, sent = _open_prompt(db, tg)
    db.delete_watched_media(me['id'], db.get_watched_media_item(me['id'], '1', 'movie')['id'])
    assert _answer(db, tg, _tap(sent, 9)) == 'Not available'
    assert db.get_rating_prompt(1)['status'] in ('pending', 'sent')


# ── polling ────────────────────────────────────────────────────────────────

def test_end_to_end_play_prompt_tap_rating_with_a_replayed_update(db, tg):
    me = _setup(db, tg)
    played = [{'tmdb_id': '438631', 'media_type': 'movie', 'title': 'Dune', 'year': 2021, 'watched_at': _ago(14)},
              {'tmdb_id': '2', 'media_type': 'movie', 'title': 'Other', 'year': 2020, 'watched_at': _ago(13)}]
    with patch('api_service.services.watch_history_sync.PlayedTitles') as titles:
        titles.return_value.titles = AsyncMock(return_value=(played, False))
        job.run_rating_prompts()
    sent = tg.of('sendMessage')[0]  # oldest play first; the second prompt keeps polling alive
    assert len(tg.of('sendMessage')) == 2
    assert sent['text'] == 'What did you think of Dune (2021)?' and sent['chat_id'] == '555'
    tg.updates = [_tap(sent, 8)]
    job.run_rating_answers()
    assert _rating(db, me, 438631) == 8
    job.run_rating_answers()  # Telegram re-serves the same update (e.g. after a restart)
    assert _rating(db, me, 438631) == 8
    answers = [body['text'] for body in tg.of('answerCallbackQuery')]
    assert answers[0] == 'Saved: 8/10 for Dune' and answers[1:] == ['Not available'] * len(answers[1:])
    polls = tg.of('getUpdates')
    assert polls[0]['allowed_updates'] == ['callback_query'] and polls[-1].get('offset', 0) >= 2


def test_nothing_is_polled_without_open_prompts(db, tg):
    _setup(db, tg)
    job.run_rating_answers()
    assert tg.of('getUpdates') == []


def test_users_sharing_a_bot_are_polled_through_one_stream(db, tg):
    for user_id, chat in ((2, '555'), (3, '556')):
        me = _setup(db, tg, user_id=user_id, chat_id=chat)
        db.claim_rating_prompt(user_id, me['id'], {'tmdb_id': '1', 'media_type': 'movie', 'title': 'T'})
    job.run_rating_answers()
    assert len(tg.of('getUpdates')) == 1


def test_the_strictest_outbound_policy_wins_for_a_shared_bot(db, tg):
    for user_id, chat in ((2, '555'), (3, '556')):
        me = _setup(db, tg, user_id=user_id, chat_id=chat)
        db.claim_rating_prompt(user_id, me['id'], {'tmdb_id': '1', 'media_type': 'movie', 'title': 'T'})
    config = db.get_personal_notification(3)
    db.set_personal_notification(3, {**config, 'allow_private': False})
    job.run_rating_answers()
    assert tg.of('getUpdates') == []  # loopback is refused for the whole bot


# ── settings, schema ───────────────────────────────────────────────────────

def _client(db, user_id='2'):
    app = Flask(__name__)

    @app.before_request
    def _user():
        g.current_user = {'id': user_id, 'role': 'user'}

    app.register_blueprint(routes.users_bp, url_prefix='/api/users')
    return app.test_client(), patch.object(routes, 'DatabaseManager', return_value=db)


def test_settings_are_validated_saved_and_cleared_with_the_destination(db, tg):
    _setup(db, tg)
    db.set_rating_prompt_config(2, False, 12)
    client, db_patch = _client(db)
    with db_patch:
        assert client.put('/api/users/me/rating-prompts', json={'enabled': 'yes'}).status_code == 400
        assert client.put('/api/users/me/rating-prompts', json={'enabled': True, 'delay_hours': 49}).status_code == 400
        assert client.put('/api/users/me/rating-prompts', json={'enabled': True, 'delay_hours': True}).status_code == 400
        saved = client.put('/api/users/me/rating-prompts', json={'enabled': True, 'delay_hours': 0})
        no_discord = {'public_key': '', 'user_id': '', 'has_token': False}
        assert saved.status_code == 200 and saved.get_json() == {
            'enabled': True, 'delay_hours': 0, 'channel': 'telegram', 'discord': no_discord}
        assert client.get('/api/users/me/rating-prompts').get_json() == {
            'enabled': True, 'delay_hours': 0, 'channel': 'telegram', 'discord': no_discord,
            'available': True, 'reason': None}
        assert client.delete('/api/users/me/notifications').status_code == 204
        after = client.get('/api/users/me/rating-prompts').get_json()
    assert after['enabled'] is False and after['available'] is False and 'Telegram' in after['reason']


def test_enabling_needs_a_private_telegram_chat_and_a_verified_media_link(db, tg):
    client, db_patch = _client(db)
    with db_patch:
        body = {'enabled': True, 'delay_hours': 12}
        assert 'Telegram' in client.put('/api/users/me/rating-prompts', json=body).get_json()['error']
        db.set_personal_notification(2, {'format': 'telegram', 'url': f'{tg.base}/sendMessage?chat_id=-5'})
        assert client.put('/api/users/me/rating-prompts', json=body).status_code == 400
        db.set_personal_notification(2, {'format': 'telegram', 'url': f'{tg.base}/sendMessage?chat_id=5'})
        assert 'media server' in client.put('/api/users/me/rating-prompts', json=body).get_json()['error']
        db.create_user_media_profile(2, 'jellyfin', 'jf-2', 'ann', verified=True)
        assert client.put('/api/users/me/rating-prompts', json=body).status_code == 200
        # Turning it off never needs the destination.
        assert client.put('/api/users/me/rating-prompts', json={'enabled': False, 'delay_hours': 12}).status_code == 200


def test_enabled_at_resets_only_when_switching_on(db, tg):
    _setup(db, tg)
    db.set_rating_prompt_config(2, False, 12)
    first = db.set_rating_prompt_config(2, True, 12)['enabled_at']
    again = db.set_rating_prompt_config(2, True, 24)['enabled_at']
    assert again == first
    db.set_rating_prompt_config(2, False, 24)
    assert db.set_rating_prompt_config(2, True, 24)['enabled_at'] >= first


def test_the_column_is_added_to_an_existing_database(tmp_path):
    with (
        patch.object(dm_mod, 'DB_PATH', str(tmp_path / 'old.db')),
        patch('api_service.db.database_manager.load_env_vars', return_value={'DB_TYPE': 'sqlite'}),
    ):
        DatabaseManager._instance = None
        manager = DatabaseManager()
        with manager.get_connection() as conn:
            conn.execute('ALTER TABLE auth_users DROP COLUMN rating_prompt_config')
            conn.commit()
        DatabaseManager._instance = None
        manager = DatabaseManager()
        with manager.get_connection() as conn:
            columns = {row[1] for row in conn.execute('PRAGMA table_info(auth_users)').fetchall()}
        assert 'rating_prompt_config' in columns
    DatabaseManager._instance = None


# ── inspection findings ────────────────────────────────────────────────────

def test_mysql_gets_an_explicitly_sized_table_that_fits_the_index_limit(db):
    ddl = SchemaManager(db)._prepare_create_table_query_for_db('rating_prompts', 'CREATE TABLE rating_prompts (x TEXT)', 'mysql')
    assert 'tmdb_id VARCHAR(64)' in ddl and 'media_type VARCHAR(16)' in ddl and 'UNIQUE KEY uniq_rating_prompt' in ddl
    assert 4 * (4 + 4 + 64 + 16) < 3072  # utf8mb4 key bytes


def test_a_title_rated_while_earlier_prompts_were_sending_is_skipped(db, tg):
    me = _setup(db, tg)
    _play(db, me, 1, 14)
    _play(db, me, 2, 13)
    original = job._send_prompt

    def rate_the_second_while_the_first_sends(database, dest, body):
        original(database, dest, body)
        item = database.get_watched_media_item(me['id'], '2', 'movie')
        database.update_watched_media(me['id'], item['id'], {'rating': 6})

    with patch.object(job, '_send_prompt', side_effect=rate_the_second_while_the_first_sends):
        _run_prompts()
    assert [body['text'] for body in tg.of('sendMessage')] == ['What did you think of Title 1 (2020)?']


def test_switching_off_or_unlinking_while_sending_stops_the_remaining_prompts(db, tg):
    me = _setup(db, tg)
    for n in (1, 2, 3):
        _play(db, me, n, 13)
    original = job._send_prompt

    def switch_off_after_the_first(database, dest, body):
        original(database, dest, body)
        database.set_rating_prompt_config(2, False, 12)

    with patch.object(job, '_send_prompt', side_effect=switch_off_after_the_first):
        _run_prompts()
    assert len(tg.of('sendMessage')) == 1


def test_a_failed_tap_is_left_unconfirmed_so_telegram_serves_it_again(db, tg):
    me, sent = _open_prompt(db, tg)
    tg.updates = [_tap(sent, 8)]
    with patch.object(db, 'answer_rating_prompt_row', side_effect=RuntimeError('database is locked')), \
            patch.object(job, 'DatabaseManager', return_value=db):
        job.run_rating_answers()
    assert job._offsets.get(tg.base) is None and _rating(db, me, 1) is None
    with patch.object(job, 'DatabaseManager', return_value=db):
        job.run_rating_answers()
    assert _rating(db, me, 1) == 8


def test_the_verified_link_is_rechecked_inside_the_answer_transaction(db, tg):
    me, sent = _open_prompt(db, tg)
    prompt = db.get_rating_prompt(1)
    with db.get_connection() as conn:  # unlinked after the handler looked the identity up
        conn.execute('DELETE FROM user_media_profiles WHERE user_id=2')
        conn.commit()
    assert db.answer_rating_prompt_row(prompt['id'], prompt['nonce'], 8, me['id']) == 'unavailable'
    assert _rating(db, me, 1) is None and db.get_rating_prompt(1)['status'] in ('pending', 'sent')
