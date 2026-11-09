"""Tests for Discord rating prompts: signed interactions, DM delivery, ownership checks and delivery generations."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest
from flask import Flask, g
from nacl.signing import SigningKey

from api_service.blueprints.discord_interactions import routes as discord_routes
from api_service.blueprints.users import routes as users_routes
from api_service.jobs import rating_prompts as job
from api_service.services import discord_interactions as discord

# Shared fixtures and helpers of the Telegram tests.
from test_rating_prompts import (  # noqa: F401
    FakeTelegram, _ago, _open_prompt, _play, _rating, _run_prompts, _setup, _store_config, _tap, db, tg,
)

USER_ID = '123456789012345678'
TOKEN = 'T' * 30


class FakeDiscord:
    """A local Discord API: opens DMs, records messages (with their Authorization header), can be told to fail."""

    def __init__(self):
        self.calls = []
        self.dm_reply = (200, {'id': 'dm-1'})
        self.message_reply = (200, {'id': 'msg-1'})
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
                outer.calls.append((self.path, body, self.headers.get('Authorization')))
                status, reply = outer.dm_reply if self.path.endswith('/users/@me/channels') else outer.message_reply
                raw = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.api = f'http://127.0.0.1:{self.server.server_port}/api/v10'

    def messages(self):
        return [(path, body, auth) for path, body, auth in self.calls if '/messages' in path]

    def dms(self):
        return [(path, body, auth) for path, body, auth in self.calls if path.endswith('/users/@me/channels')]


@pytest.fixture
def dc():
    fake = FakeDiscord()
    with patch.object(job, 'DISCORD_API', fake.api), patch.object(job, 'DISCORD_ALLOW_PRIVATE', True):
        yield fake
    fake.server.shutdown()


def _discord_setup(db, user_id=2, key=None, user=USER_ID, enabled=True, hours_ago=100):
    """Opt a user in on Discord: verified link, saved credentials, settings enabled in the past."""
    key = key or SigningKey.generate()
    db.create_user_media_profile(user_id, 'jellyfin', f'jf-{user_id}', f'u{user_id}', verified=True)
    _store_config(db, user_id, {'enabled': enabled, 'delay_hours': 12, 'enabled_at': _ago(hours_ago).isoformat(),
                                'channel': 'discord', 'discord': {'bot_token': TOKEN, 'user_id': user,
                                                                  'public_key': key.verify_key.encode().hex()}})
    return db.upsert_media_user_identity('jellyfin', f'jf-{user_id}'), key


def _client(db):
    app = Flask(__name__)
    app.register_blueprint(discord_routes.discord_interactions_bp, url_prefix='/api/discord')
    return app.test_client(), patch.object(discord_routes, 'DatabaseManager', return_value=db)


def _signed(key, payload, timestamp=None, body=None):
    body = body if body is not None else json.dumps(payload).encode()
    timestamp = str(int(time.time())) if timestamp is None else timestamp
    return body, {'X-Signature-Ed25519': key.sign(timestamp.encode() + body).signature.hex(),
                  'X-Signature-Timestamp': timestamp, 'Content-Type': 'application/json'}


def _post(client, key, payload, **kwargs):
    body, headers = _signed(key, payload, **kwargs)
    return client.post('/api/discord/interactions', data=body, headers=headers)


def _button(message, n):
    return message['components'][(n - 1) // 5]['components'][(n - 1) % 5]['custom_id']


def _tap_payload(message, n, user=USER_ID, **extra):
    return {'type': 3, 'user': {'id': user}, 'data': {'custom_id': _button(message, n)}, **extra}


def _opened(db, dc, hours=13):
    """A Discord user with one delivered prompt; returns (identity, key, client patch, message body)."""
    me, key = _discord_setup(db)
    _play(db, me, 1, hours)
    _run_prompts()
    return me, key, dc.messages()[-1][1]


# ── signatures and the route ───────────────────────────────────────────────

def test_signature_checks_never_raise_and_only_accept_the_matching_key():
    key, other = SigningKey.generate(), SigningKey.generate()
    body, headers = _signed(key, {'type': 1})
    pk = key.verify_key.encode().hex()
    stamp, sig = headers['X-Signature-Timestamp'], headers['X-Signature-Ed25519']
    assert discord.verify_signature(pk, stamp, body, sig)
    assert not discord.verify_signature(other.verify_key.encode().hex(), stamp, body, sig)
    assert not discord.verify_signature(pk, stamp, body + b' ', sig)
    for bad in ('', 'zz', 'ab' * 3, sig[:-2]):
        assert not discord.verify_signature(pk, stamp, body, bad)
    assert not discord.verify_signature('nothex', stamp, body, sig)
    assert discord.timestamp_is_fresh(str(int(time.time()))) and not discord.timestamp_is_fresh('abc')
    assert not discord.timestamp_is_fresh(str(int(time.time()) - 400))
    assert not discord.timestamp_is_fresh(str(int(time.time()) + 400))


def test_a_signed_ping_is_answered_even_while_prompts_are_switched_off(db):
    _, key = _discord_setup(db, enabled=False)  # credentials saved, prompts still off: the setup order
    client, patched = _client(db)
    with patched:
        response = _post(client, key, {'type': 1})
    assert response.status_code == 200 and response.get_json() == {'type': 1}


@pytest.mark.parametrize('case', ['tampered', 'other_key', 'stale', 'future', 'missing', 'garbage_sig', 'oversize'])
def test_bad_requests_get_401_and_nothing_else(db, case):
    _, key = _discord_setup(db)
    client, patched = _client(db)
    payload = {'type': 1}
    with patched:
        if case == 'tampered':
            body, headers = _signed(key, payload)
            response = client.post('/api/discord/interactions', data=body + b' ', headers=headers)
        elif case == 'other_key':
            response = _post(client, SigningKey.generate(), payload)
        elif case == 'stale':
            response = _post(client, key, payload, timestamp=str(int(time.time()) - 600))
        elif case == 'future':
            response = _post(client, key, payload, timestamp=str(int(time.time()) + 600))
        elif case == 'missing':
            response = client.post('/api/discord/interactions', json=payload)
        elif case == 'garbage_sig':
            body, headers = _signed(key, payload)
            response = client.post('/api/discord/interactions', data=body,
                                   headers={**headers, 'X-Signature-Ed25519': 'not-hex'})
        else:
            response = _post(client, key, None, body=b'{"type":1,"pad":"' + b'a' * 20000 + b'"}')
    assert response.status_code == 401 and response.get_json() == {}


def test_only_active_users_with_complete_credentials_provide_keys(db):
    _, key = _discord_setup(db)
    assert db.discord_public_keys() == [key.verify_key.encode().hex()]
    with db.get_connection() as conn:
        conn.execute('UPDATE auth_users SET is_active=0 WHERE id=2')
        conn.commit()
    assert db.discord_public_keys() == []
    with db.get_connection() as conn:
        conn.execute('UPDATE auth_users SET is_active=1 WHERE id=2')
        conn.commit()
    db.set_rating_prompt_config(2, False, 12, 'telegram')
    assert db.discord_public_keys() == []


def test_unsupported_interaction_types_are_rejected(db):
    _, key = _discord_setup(db)
    client, patched = _client(db)
    with patched:
        assert _post(client, key, {'type': 2}).status_code == 400


# ── delivery ───────────────────────────────────────────────────────────────

def test_end_to_end_play_dm_tap_edit_and_a_replayed_signed_request(db, dc):
    me, key, message = _opened(db, dc)
    [(dm_path, dm_body, dm_auth)] = dc.dms()
    assert dm_body == {'recipient_id': USER_ID} and dm_auth == f'Bot {TOKEN}'
    [(path, _, auth)] = dc.messages()
    assert path.endswith('/channels/dm-1/messages') and auth == f'Bot {TOKEN}'
    assert message['content'] == 'What did you think of Title 1 (2020)?' and message['allowed_mentions'] == {'parse': []}
    rows = message['components']
    assert [len(row['components']) for row in rows] == [5, 5]
    assert [b['label'] for row in rows for b in row['components']] == [str(n) for n in range(1, 11)]
    assert all(len(b['custom_id']) < 100 for row in rows for b in row['components'])
    assert db.get_rating_prompt(1)['status'] == 'sent'

    client, patched = _client(db)
    payload = _tap_payload(message, 8)
    body, headers = _signed(key, payload)
    with patched:
        first = client.post('/api/discord/interactions', data=body, headers=headers)
        replay = client.post('/api/discord/interactions', data=body, headers=headers)
    assert first.get_json() == {'type': 7, 'data': {'content': 'Saved: 8/10 for Title 1', 'components': []}}
    assert _rating(db, me, 1) == 8
    assert replay.get_json() == {'type': 4, 'data': {'content': 'Not available', 'flags': 64}}
    assert _rating(db, me, 1) == 8


def test_the_dm_is_opened_once_per_run_and_prompts_are_capped(db, dc):
    me, _ = _discord_setup(db)
    for n in range(1, 8):
        _play(db, me, n, 13)
    _run_prompts()
    assert len(dc.dms()) == 1 and len(dc.messages()) == job.MAX_PROMPTS_PER_RUN


@pytest.mark.parametrize('reply', [(403, {'code': 50007, 'message': 'Cannot send messages to this user'}),
                                   (429, {'message': 'You are being rate limited.', 'code': 0, 'retry_after': 1})])
def test_a_discord_rejection_leaves_no_claim_and_is_retried(db, dc, reply):
    me, _ = _discord_setup(db)
    _play(db, me, 1, 13)
    dc.message_reply = reply
    _run_prompts()
    assert db.users_with_open_prompts() == []
    dc.message_reply = (200, {'id': 'msg-2'})
    _run_prompts()
    assert len(dc.messages()) == 2 and db.users_with_open_prompts() == [2]


@pytest.mark.parametrize('reply', [(502, b'<html>bad gateway</html>'), (500, {'message': 'boom'}), (200, b'not json'),
                                   (200, {'no': 'id'})])
def test_an_ambiguous_discord_send_is_never_repeated_and_its_button_still_works(db, dc, reply):
    me, key = _discord_setup(db)
    _play(db, me, 1, 13)
    dc.message_reply = reply
    _run_prompts()
    _run_prompts()
    assert len(dc.messages()) == 1
    assert db.get_rating_prompt(1)['status'] == 'pending'
    message = dc.messages()[0][1]
    assert job.answer_discord_interaction(db, key.verify_key.encode().hex(), _tap_payload(message, 6))['type'] == 7
    assert _rating(db, me, 1) == 6


@pytest.mark.parametrize('reply', [(401, {'code': 0, 'message': '401: Unauthorized'}), (500, {'message': 'x'}),
                                   (200, b'garbage')])
def test_failing_to_open_the_dm_leaves_no_claim_for_any_failure(db, dc, reply):
    me, _ = _discord_setup(db)
    _play(db, me, 1, 13)
    dc.dm_reply = reply
    _run_prompts()
    assert dc.messages() == [] and db.users_with_open_prompts() == []
    dc.dm_reply = (200, {'id': 'dm-1'})
    _run_prompts()
    assert len(dc.messages()) == 1


# ── who may tap ────────────────────────────────────────────────────────────

REFUSED = discord.refused()


def _tap_with(db, key, message, n=8, **kwargs):
    return job.answer_discord_interaction(db, key.verify_key.encode().hex(), _tap_payload(message, n, **kwargs))


def test_the_owner_in_their_dm_is_the_only_one_who_can_rate(db, dc):
    me, key, message = _opened(db, dc)
    assert _tap_with(db, key, message, user='999999999999999999') == REFUSED          # someone else
    assert _tap_with(db, key, message, member={'user': {'id': USER_ID}}) == REFUSED   # in a server
    no_user = {'type': 3, 'data': {'custom_id': _button(message, 8)}}
    assert job.answer_discord_interaction(db, key.verify_key.encode().hex(), no_user) == REFUSED
    assert _rating(db, me, 1) is None
    assert _tap_with(db, key, message)['type'] == 7 and _rating(db, me, 1) == 8
    assert _tap_with(db, key, message, 3) == REFUSED  # already answered


def test_another_applications_valid_key_cannot_answer_this_users_prompt(db, dc):
    me, key, message = _opened(db, dc)
    _, other = _discord_setup(db, user_id=3)
    assert _tap_with(db, other, message) == REFUSED
    assert _rating(db, me, 1) is None


def test_malformed_buttons_and_values_are_refused(db, dc):
    me, key, message = _opened(db, dc)
    pk = key.verify_key.encode().hex()
    good = _button(message, 8)
    for custom_id in ('', 'rp:1:zz:8', 'rp:1:' + 'a' * 16 + ':8', good.rsplit(':', 1)[0] + ':11', good.rsplit(':', 1)[0] + ':0',
                      good.replace('rp:1:', 'rp:99:')):
        assert job.answer_discord_interaction(db, pk, {'type': 3, 'user': {'id': USER_ID},
                                                       'data': {'custom_id': custom_id}}) == REFUSED
    assert _rating(db, me, 1) is None


@pytest.mark.parametrize('change', ['deactivate', 'disable', 'to_telegram', 'new_key', 'new_user', 'unlink'])
def test_an_old_discord_button_is_dead_once_the_owner_state_changes(db, dc, change):
    me, key, message = _opened(db, dc)
    pk = key.verify_key.encode().hex()
    if change == 'deactivate':
        with db.get_connection() as conn:
            conn.execute('UPDATE auth_users SET is_active=0 WHERE id=2')
            conn.commit()
    elif change == 'disable':
        db.set_rating_prompt_config(2, False, 12, 'discord', {})
    elif change == 'to_telegram':
        db.set_personal_notification(2, {'format': 'telegram', 'url': 'https://api.telegram.org/botX/sendMessage?chat_id=5'})
        db.set_rating_prompt_config(2, True, 12, 'telegram')
    elif change == 'new_key':
        db.set_rating_prompt_config(2, True, 12, 'discord', {'public_key': SigningKey.generate().verify_key.encode().hex()})
    elif change == 'new_user':
        db.set_rating_prompt_config(2, True, 12, 'discord', {'user_id': '222222222222222222'})
    else:
        with db.get_connection() as conn:
            conn.execute('DELETE FROM user_media_profiles WHERE user_id=2')
            conn.commit()
    assert job.answer_discord_interaction(db, pk, _tap_payload(message, 8)) == REFUSED
    assert _rating(db, me, 1) is None and db.get_rating_prompt(1)['status'] in ('pending', 'sent')


def test_a_rating_made_elsewhere_is_kept(db, dc):
    me, key, message = _opened(db, dc)
    db.update_watched_media(me['id'], db.get_watched_media_item(me['id'], '1', 'movie')['id'], {'rating': 4})
    assert _tap_with(db, key, message, 9) == discord.updated('Already rated')
    assert _rating(db, me, 1) == 4


# ── delivery generations ───────────────────────────────────────────────────

def _generation(db, user_id=2):
    return db.get_rating_prompt_config(user_id)['generation']


def _tg_tap(db, tg, sent, n=8):
    return job.answer_rating_prompt(db, tg.base, _tap(sent, n))


def test_switching_channel_away_and_back_never_revives_an_old_telegram_button(db, tg):
    me, sent = _open_prompt(db, tg)
    creds = {'bot_token': TOKEN, 'public_key': SigningKey.generate().verify_key.encode().hex(), 'user_id': USER_ID}
    start = _generation(db)
    db.set_rating_prompt_config(2, True, 12, 'discord', creds)
    db.set_rating_prompt_config(2, True, 12, 'telegram')
    assert _generation(db) == start + 2
    assert _tg_tap(db, tg, sent) == 'Not available' and _rating(db, me, 1) is None
    # The title stays claimed: it is not asked again either.
    assert db.eligible_rating_prompt_titles(2, me['id'], _ago(200), _ago(0), 5) == []


def test_changing_the_discord_key_or_user_and_back_never_revives_an_old_button(db, dc):
    me, key, message = _opened(db, dc)
    pk = key.verify_key.encode().hex()
    other = SigningKey.generate().verify_key.encode().hex()
    db.set_rating_prompt_config(2, True, 12, 'discord', {'public_key': other})
    db.set_rating_prompt_config(2, True, 12, 'discord', {'public_key': pk})
    assert job.answer_discord_interaction(db, pk, _tap_payload(message, 8)) == REFUSED
    db.set_rating_prompt_config(2, True, 12, 'discord', {'user_id': '222222222222222222'})
    db.set_rating_prompt_config(2, True, 12, 'discord', {'user_id': USER_ID})
    assert job.answer_discord_interaction(db, pk, _tap_payload(message, 8)) == REFUSED
    assert _rating(db, me, 1) is None


def test_changing_the_telegram_chat_and_back_never_revives_an_old_button(db, tg):
    me, sent = _open_prompt(db, tg)
    url = db.get_personal_notification(2)['url']
    start = _generation(db)
    db.set_personal_notification(2, {'format': 'telegram', 'url': url.replace('chat_id=555', 'chat_id=777'), 'allow_private': True})
    db.set_personal_notification(2, {'format': 'telegram', 'url': url, 'allow_private': True})
    assert _generation(db) == start + 2 and _tg_tap(db, tg, sent) == 'Not available'


def test_deleting_and_restoring_the_same_telegram_destination_never_revives_a_button(db, tg):
    me, sent = _open_prompt(db, tg)
    url = db.get_personal_notification(2)['url']
    db.set_personal_notification(2, None)
    config = db.get_rating_prompt_config(2)
    assert config['enabled'] is False and config['generation'] == 1  # switched off, counter kept
    db.set_personal_notification(2, {'format': 'telegram', 'url': url, 'allow_private': True})
    db.set_rating_prompt_config(2, True, 12, 'telegram')
    assert _tg_tap(db, tg, sent) == 'Not available' and _rating(db, me, 1) is None


def test_saving_identical_values_changes_nothing(db, tg):
    _setup(db, tg)
    start = _generation(db)
    notify = db.get_personal_notification(2)
    db.set_personal_notification(2, dict(notify))
    db.set_rating_prompt_config(2, True, 24, 'telegram')
    assert _generation(db) == start


def test_an_unrelated_telegram_change_leaves_discord_prompts_answerable(db, dc):
    me, key, message = _opened(db, dc)
    start = _generation(db)
    db.set_personal_notification(2, {'format': 'telegram', 'url': 'https://api.telegram.org/botX/sendMessage?chat_id=5'})
    db.set_personal_notification(2, None)
    assert _generation(db) == start and db.get_rating_prompt_config(2)['enabled'] is True
    assert job.answer_discord_interaction(db, key.verify_key.encode().hex(), _tap_payload(message, 8))['type'] == 7


def test_removing_a_telegram_destination_keeps_saved_discord_credentials_in_both_orders(db, tg):
    _setup(db, tg)
    creds = {'bot_token': TOKEN, 'public_key': SigningKey.generate().verify_key.encode().hex(), 'user_id': USER_ID}
    db.set_rating_prompt_config(2, True, 12, 'telegram', creds)   # Discord details saved while on Telegram
    db.set_personal_notification(2, None)                         # delete first ...
    config = db.get_rating_prompt_config(2)
    assert config['enabled'] is False and config['discord'] == creds
    saved = db.set_rating_prompt_config(2, True, 12, 'discord', {})  # ... then switch, token omitted
    assert saved['channel'] == 'discord' and saved['enabled'] is True
    db.set_personal_notification(2, {'format': 'telegram', 'url': 'https://api.telegram.org/botX/sendMessage?chat_id=5'})
    db.set_rating_prompt_config(2, True, 12, 'telegram')           # switch first ...
    db.set_personal_notification(2, None)                         # ... then delete
    config = db.get_rating_prompt_config(2)
    assert config['discord'] == creds and config['enabled'] is False


def test_a_change_between_the_re_read_and_the_claim_yields_no_claim_and_no_message(db, dc):
    me, _ = _discord_setup(db)
    _play(db, me, 1, 13)
    original = db.claim_rating_prompt

    def destination_changes_first(*args, **kwargs):
        db.set_rating_prompt_config(2, True, 12, 'discord', {'user_id': '222222222222222222'})
        return original(*args, **kwargs)

    with patch.object(db, 'claim_rating_prompt', side_effect=destination_changes_first):
        _run_prompts()
    assert dc.messages() == [] and db.users_with_open_prompts() == []


def test_concurrent_destination_changes_never_lose_a_bump(tmp_path, db, tg):
    _setup(db, tg)
    start = _generation(db)
    urls = [f'{tg.base}/sendMessage?chat_id={n}' for n in (601, 602, 603, 604)]
    errors = []

    def change(url):
        try:
            db.set_personal_notification(2, {'format': 'telegram', 'url': url, 'allow_private': True})
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=change, args=(url,)) for url in urls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == [] and _generation(db) == start + 4


def test_a_failed_write_leaves_the_destination_and_the_generation_unchanged(db, tg):
    _setup(db, tg)
    before = (db.get_personal_notification(2), _generation(db))
    with patch('api_service.db.components.rating_prompt_mixin.json.dumps', side_effect=RuntimeError('disk full')):
        with pytest.raises(RuntimeError):
            db.set_personal_notification(2, {'format': 'telegram', 'url': f'{tg.base}/sendMessage?chat_id=999'})
    assert (db.get_personal_notification(2), _generation(db)) == before


# ── settings ───────────────────────────────────────────────────────────────

def _settings_client(db, user_id='2'):
    app = Flask(__name__)

    @app.before_request
    def _user():
        g.current_user = {'id': user_id, 'role': 'user'}

    app.register_blueprint(users_routes.users_bp, url_prefix='/api/users')
    return app.test_client(), patch.object(users_routes, 'DatabaseManager', return_value=db)


CREDS = {'bot_token': TOKEN, 'public_key': 'ab' * 32, 'user_id': USER_ID}


def test_first_time_discord_setup_works_without_any_telegram_destination(db):
    client, patched = _settings_client(db)
    with patched:
        saved = client.put('/api/users/me/rating-prompts', json={'enabled': False, 'delay_hours': 12,
                                                                  'channel': 'discord', 'discord': CREDS})
        assert saved.status_code == 200
        # Enabling still needs a verified media link.
        assert 'media server' in client.put('/api/users/me/rating-prompts', json={
            'enabled': True, 'delay_hours': 12, 'channel': 'discord'}).get_json()['error']
        db.create_user_media_profile(2, 'jellyfin', 'jf-2', 'ann', verified=True)
        with patch('api_service.blueprints.users.routes.selected_provider', return_value='jellyfin'):
            enabled = client.put('/api/users/me/rating-prompts', json={'enabled': True, 'delay_hours': 12, 'channel': 'discord'})
            read = client.get('/api/users/me/rating-prompts').get_json()
    assert enabled.status_code == 200 and enabled.get_json()['enabled'] is True
    assert read['channel'] == 'discord' and read['available'] is True


def test_the_bot_token_is_write_only_and_kept_when_omitted(db):
    client, patched = _settings_client(db)
    with patched:
        saved = client.put('/api/users/me/rating-prompts', json={'enabled': False, 'channel': 'discord', 'discord': CREDS})
        read = client.get('/api/users/me/rating-prompts')
        client.put('/api/users/me/rating-prompts', json={'enabled': False, 'channel': 'discord',
                                                         'discord': {'public_key': 'cd' * 32, 'user_id': USER_ID}})
        after = client.get('/api/users/me/rating-prompts')
    for response in (saved, read, after):
        assert TOKEN not in response.get_data(as_text=True)
    assert read.get_json()['discord'] == {'public_key': 'ab' * 32, 'user_id': USER_ID, 'has_token': True}
    assert after.get_json()['discord']['public_key'] == 'cd' * 32 and after.get_json()['discord']['has_token'] is True
    assert db.get_rating_prompt_config(2)['discord']['bot_token'] == TOKEN


@pytest.mark.parametrize('discord_fields, message', [
    ({**CREDS, 'public_key': 'xyz'}, 'public key'),
    ({**CREDS, 'public_key': 'ab' * 31}, 'public key'),
    ({**CREDS, 'user_id': '12ab'}, 'user id'),
    ({**CREDS, 'bot_token': 'short'}, 'token'),
    ({**CREDS, 'bot_token': 'a b ' * 10}, 'token'),
])
def test_invalid_discord_fields_are_explained(db, discord_fields, message):
    client, patched = _settings_client(db)
    with patched:
        response = client.put('/api/users/me/rating-prompts', json={'enabled': False, 'channel': 'discord', 'discord': discord_fields})
    assert response.status_code == 400 and message in response.get_json()['error']


def test_enabling_discord_without_complete_credentials_is_refused_and_telegram_keeps_working(db, tg):
    db.create_user_media_profile(2, 'jellyfin', 'jf-2', 'ann', verified=True)
    client, patched = _settings_client(db)
    with patched, patch('api_service.blueprints.users.routes.selected_provider', return_value='jellyfin'):
        refused = client.put('/api/users/me/rating-prompts', json={'enabled': True, 'channel': 'discord', 'discord': {'user_id': USER_ID}})
        assert refused.status_code == 400 and 'bot token' in refused.get_json()['error']
        db.set_personal_notification(2, {'format': 'telegram', 'url': f'{tg.base}/sendMessage?chat_id=555'})
        assert client.put('/api/users/me/rating-prompts', json={'enabled': True, 'delay_hours': 12}).status_code == 200
        assert client.put('/api/users/me/rating-prompts', json={'enabled': True, 'channel': 'carrier-pigeon'}).status_code == 400


def test_the_test_message_reaches_the_dm_or_explains_why_not(db, dc):
    _discord_setup(db)
    client, patched = _settings_client(db)
    with patched:
        ok = client.post('/api/users/me/rating-prompts/test')
        dc.message_reply = (403, {'code': 50007, 'message': 'Cannot send messages to this user'})
        blocked = client.post('/api/users/me/rating-prompts/test')
        dc.dm_reply = (401, {'code': 0, 'message': '401: Unauthorized'})
        rejected = client.post('/api/users/me/rating-prompts/test')
    assert ok.status_code == 200 and dc.messages()[0][1]['content'] == 'SuggestArr: rating prompts are connected.'
    assert blocked.status_code == 400 and 'share a server' in blocked.get_json()['error']
    assert rejected.status_code == 400 and 'token' in rejected.get_json()['error']
    assert TOKEN not in blocked.get_data(as_text=True)


def test_the_test_message_needs_the_discord_channel(db, tg):
    _setup(db, tg)
    client, patched = _settings_client(db)
    with patched:
        assert client.post('/api/users/me/rating-prompts/test').status_code == 400


def test_generation_columns_are_added_to_an_existing_database(tmp_path):
    from api_service.db import database_manager as dm_mod
    from api_service.db.database_manager import DatabaseManager
    with (
        patch.object(dm_mod, 'DB_PATH', str(tmp_path / 'old.db')),
        patch('api_service.db.database_manager.load_env_vars', return_value={'DB_TYPE': 'sqlite'}),
    ):
        DatabaseManager._instance = None
        manager = DatabaseManager()
        with manager.get_connection() as conn:
            conn.execute('ALTER TABLE auth_users DROP COLUMN rating_prompt_generation')
            conn.execute('ALTER TABLE rating_prompts DROP COLUMN generation')
            conn.commit()
        DatabaseManager._instance = None
        manager = DatabaseManager()
        with manager.get_connection() as conn:
            users = {row[1] for row in conn.execute('PRAGMA table_info(auth_users)').fetchall()}
            prompts = {row[1] for row in conn.execute('PRAGMA table_info(rating_prompts)').fetchall()}
    DatabaseManager._instance = None
    assert 'rating_prompt_generation' in users and 'generation' in prompts


def test_discord_credentials_must_be_complete_on_every_discord_save_even_with_prompts_off(db):
    client, patched = _settings_client(db)
    with patched:
        for partial in ({}, {'user_id': USER_ID}, {'public_key': 'ab' * 32, 'user_id': USER_ID},
                        {'bot_token': TOKEN, 'user_id': USER_ID}):
            response = client.put('/api/users/me/rating-prompts', json={'enabled': False, 'channel': 'discord', 'discord': partial})
            assert response.status_code == 400 and 'bot token' in response.get_json()['error']
        assert db.get_rating_prompt_config(2)['channel'] == 'telegram'
        assert client.put('/api/users/me/rating-prompts', json={'enabled': False, 'channel': 'discord', 'discord': CREDS}).status_code == 200
        # Later saves may omit the stored token, and Telegram never needs Discord fields.
        assert client.put('/api/users/me/rating-prompts', json={'enabled': False, 'channel': 'discord',
                                                                'discord': {'user_id': USER_ID}}).status_code == 200
        assert client.put('/api/users/me/rating-prompts', json={'enabled': False, 'channel': 'telegram'}).status_code == 200


def test_a_title_rated_while_the_dm_is_being_opened_is_not_claimed_or_sent(db, dc):
    me, _ = _discord_setup(db)
    _play(db, me, 1, 13)
    original = job._discord_dm_channel

    def rate_the_title_while_opening(database, dest):
        channel = original(database, dest)
        database.update_watched_media(me['id'], database.get_watched_media_item(me['id'], '1', 'movie')['id'], {'rating': 5})
        return channel

    with patch.object(job, '_discord_dm_channel', side_effect=rate_the_title_while_opening):
        _run_prompts()
    assert dc.messages() == [] and db.users_with_open_prompts() == [] and _rating(db, me, 1) == 5


def test_switching_off_while_the_dm_is_being_opened_stops_the_run(db, dc):
    me, _ = _discord_setup(db)
    _play(db, me, 1, 13)
    original = job._discord_dm_channel

    def switch_off_while_opening(database, dest):
        channel = original(database, dest)
        database.set_rating_prompt_config(2, False, 12, 'discord', {})
        return channel

    with patch.object(job, '_discord_dm_channel', side_effect=switch_off_while_opening):
        _run_prompts()
    assert dc.messages() == [] and db.users_with_open_prompts() == []


def test_a_destination_change_waits_for_a_tap_in_flight_and_then_kills_the_button(db, dc):
    """The answer transaction holds the owner row, so the change commits only after the rating is stored."""
    me, key, message = _opened(db, dc)
    pk = key.verify_key.encode().hex()
    inside, order, errors = threading.Event(), [], []
    from api_service.db.components import rating_prompt_mixin as mixin
    real = mixin.normalize_rating_prompt_config

    in_transaction = threading.local()
    real_row = db.answer_rating_prompt_row

    def mark_the_transaction(*args, **kwargs):
        in_transaction.open = True
        try:
            return real_row(*args, **kwargs)
        finally:
            in_transaction.open = False

    def pause_inside_the_answer(raw, generation=0):
        if getattr(in_transaction, 'open', False) and not inside.is_set():
            inside.set()
            time.sleep(0.6)  # the destination change is attempted while this transaction is open
        return real(raw, generation)

    def tap():
        try:
            order.append(('tap', job.answer_discord_interaction(db, pk, _tap_payload(message, 8))['type']))
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    def change():
        inside.wait(5)
        try:
            db.set_rating_prompt_config(2, True, 12, 'discord', {'user_id': '222222222222222222'})
            order.append(('change', None))
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    with patch.object(mixin, 'normalize_rating_prompt_config', side_effect=pause_inside_the_answer), \
            patch.object(db, 'answer_rating_prompt_row', side_effect=mark_the_transaction):
        tapper = threading.Thread(target=tap, name='tapper')
        changer = threading.Thread(target=change, name='changer')
        tapper.start(); changer.start()
        tapper.join(); changer.join()
    assert errors == [] and [name for name, _ in order] == ['tap', 'change']
    assert _rating(db, me, 1) == 8 and _generation(db) == 1
    assert job.answer_discord_interaction(db, pk, _tap_payload(message, 3)) == REFUSED


def test_a_huge_signed_timestamp_is_a_401_not_a_server_error(db):
    _, key = _discord_setup(db)
    client, patched = _client(db)
    with patched:
        body, headers = _signed(key, {'type': 1}, timestamp='9' * 400)
        response = client.post('/api/discord/interactions', data=body, headers=headers)
    assert response.status_code == 401 and not discord.timestamp_is_fresh('9' * 400)


def test_enabling_telegram_prompts_is_checked_again_under_the_lock_when_the_destination_vanishes(db, tg):
    _setup(db, tg)
    db.set_rating_prompt_config(2, False, 12, 'telegram')
    with pytest.raises(ValueError, match='Telegram destination'):
        db.set_personal_notification(2, None)
        db.set_rating_prompt_config(2, True, 12, 'telegram')
    assert db.get_rating_prompt_config(2)['enabled'] is False


def test_deleting_the_destination_between_the_routes_check_and_the_write_leaves_prompts_off(db, tg):
    _setup(db, tg)
    db.set_rating_prompt_config(2, False, 12, 'telegram')
    client, patched = _settings_client(db)
    real_blocker = users_routes._rating_prompt_blocker

    def delete_after_the_check(*args, **kwargs):
        result = real_blocker(*args, **kwargs)
        db.set_personal_notification(2, None)  # a concurrent DELETE /me/notifications commits here
        return result

    with patched, patch('api_service.blueprints.users.routes.selected_provider', return_value='jellyfin'), \
            patch.object(users_routes, '_rating_prompt_blocker', side_effect=delete_after_the_check):
        response = client.put('/api/users/me/rating-prompts', json={'enabled': True, 'delay_hours': 12})
    assert response.status_code == 400 and 'Telegram destination' in response.get_json()['error']
    assert db.get_rating_prompt_config(2)['enabled'] is False
