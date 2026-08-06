"""Tests for the account-id mapping applied when a user links Plex.

The boot-time repair in test_plex_account_resolver covers profiles created
before the mapping existed. This covers the other entry point: the OAuth poll,
which maps the id at the moment the profile is written.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

logging.disable(logging.CRITICAL)

from api_service.blueprints.users.routes import _reconcile_plex_account_id

SERVER_USERS = [
    {"id": 1, "name": "Wirewraith"},
    {"id": 3502706, "name": "somepotato"},
]


@pytest.fixture
def app_context():
    app = Flask(__name__)
    with app.test_request_context():
        g.current_user = {"id": "7", "username": "wire", "role": "admin"}
        yield


def make_db(plex_profiles=()):
    db = MagicMock()
    db.get_media_profiles_by_provider.return_value = list(plex_profiles)
    db.rename_media_user_identity.return_value = None
    return db


@patch("api_service.blueprints.users.routes.list_plex_server_users", return_value=SERVER_USERS)
def test_the_owners_plex_tv_id_is_mapped_to_the_server_id(_users, app_context):
    db = make_db()
    assert _reconcile_plex_account_id(db, "14621895", "Wirewraith") == "1"
    db.rename_media_user_identity.assert_called_once_with("plex", "14621895", "1")


@patch("api_service.blueprints.users.routes.list_plex_server_users", return_value=SERVER_USERS)
def test_an_id_the_server_already_uses_is_left_alone(_users, app_context):
    db = make_db()
    assert _reconcile_plex_account_id(db, "3502706", "somepotato") == "3502706"
    db.rename_media_user_identity.assert_not_called()


@patch("api_service.blueprints.users.routes.list_plex_server_users", return_value=[])
def test_an_unreachable_server_falls_back_to_the_plex_tv_id(_users, app_context):
    db = make_db()
    assert _reconcile_plex_account_id(db, "14621895", "Wirewraith") == "14621895"


@patch("api_service.blueprints.users.routes.list_plex_server_users", return_value=SERVER_USERS)
def test_an_id_another_account_already_holds_is_refused(_users, app_context):
    """The mapping is a display-name guess, and this is where it costs most.

    Handing this caller an id another SuggestArr account is linked to would
    merge two people's requests and watch history. The unmapped id resolves to
    nothing, which is the safer of the two wrong answers.
    """
    db = make_db([{"user_id": 3, "external_user_id": "1", "external_username": "Wirewraith"}])

    assert _reconcile_plex_account_id(db, "14621895", "Wirewraith") == "14621895"
    db.rename_media_user_identity.assert_not_called()


@patch("api_service.blueprints.users.routes.list_plex_server_users", return_value=SERVER_USERS)
def test_relinking_your_own_profile_is_not_treated_as_a_collision(_users, app_context):
    """The current user re-running OAuth must still get the mapped id."""
    db = make_db([{"user_id": 7, "external_user_id": "1", "external_username": "Wirewraith"}])

    assert _reconcile_plex_account_id(db, "14621895", "Wirewraith") == "1"
