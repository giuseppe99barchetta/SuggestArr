"""Tests for personal "ready to watch" notifications sent to a user's own chat."""
import json
from unittest.mock import patch

import pytest
from flask import Flask, g

from api_service.blueprints.users import routes
from api_service.db import database_manager as dm_mod
from api_service.db.database_manager import DatabaseManager
from api_service.jobs.availability_sync import notify_owners
from api_service.services.request_sources import DISCOVER_SOURCE


@pytest.fixture
def db(tmp_path):
    with (
        patch.object(dm_mod, "DB_PATH", str(tmp_path / "notify.db")),
        patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}),
    ):
        DatabaseManager._instance = None
        manager = DatabaseManager()
        with manager.get_connection() as conn:
            conn.execute("INSERT INTO auth_users(id,username,password_hash,role) VALUES "
                         "(1,'admin','h','admin'),(2,'ann','h','user'),(3,'bob','h','user')")
            conn.commit()
        yield manager
    DatabaseManager._instance = None


def _deliveries(db):
    with db.get_connection() as conn:
        rows = conn.execute("SELECT webhook_id, url, payload FROM webhook_deliveries ORDER BY id").fetchall()
    return [(row[0], row[1], json.loads(row[2])) for row in rows]


def test_owners_come_from_the_suggestion_and_from_verified_media_links(db):
    db.save_metadata({"id": "438631", "title": "Dune"}, "movie")
    # Queued first, then delivered: the order the queue worker follows.
    db.enqueue_request("438631", "movie", None, {}, status="submitted", owner_id=3)
    db.save_request("movie", "438631", DISCOVER_SOURCE, user_id="jf-ann")
    db.create_user_media_profile(2, "jellyfin", "jf-ann", "ann", verified=True)
    assert db.get_title_owner_ids("movie", "438631", "jellyfin") == {2, 3}
    assert db.get_title_owner_ids("movie", "999", "jellyfin") == set()


def test_only_owners_with_a_destination_are_told_with_title_and_play_link(db):
    db.save_metadata({"id": "438631", "title": "Dune"}, "movie")
    # Queued first, then delivered: the order the queue worker follows.
    db.enqueue_request("438631", "movie", None, {}, status="submitted", owner_id=3)
    db.save_request("movie", "438631", DISCOVER_SOURCE, user_id="jf-ann")
    db.create_user_media_profile(2, "jellyfin", "jf-ann", "ann", verified=True)
    db.set_personal_notification(2, {"format": "discord", "url": "https://discord.com/api/webhooks/1/x"})

    sent = notify_owners(db, {"SELECTED_SERVICE": "jellyfin"}, "movie", "438631", "http://jf.local/play")

    assert sent == 1
    [(hook, url, body)] = _deliveries(db)
    assert hook == "user:2" and url == "https://discord.com/api/webhooks/1/x"
    assert body["content"] == "Your request is ready to watch: Dune\nhttp://jf.local/play"


def test_personal_deliveries_stay_out_of_the_admin_list_and_go_with_the_user(db):
    db.set_personal_notification(2, {"format": "ntfy", "url": "https://ntfy.sh/ann"})
    assert db.enqueue_personal_notification(2, "personal.test", "hi")
    assert db.list_webhook_deliveries() == []
    db.delete_auth_user(2)
    assert db.get_personal_notification(2) is None
    assert not db.enqueue_personal_notification(2, "personal.test", "hi")


def _client(db, user):
    app = Flask(__name__)

    @app.before_request
    def _user():
        g.current_user = user

    app.register_blueprint(routes.users_bp, url_prefix="/api/users")
    return app.test_client(), patch.object(routes, "DatabaseManager", return_value=db)


def test_a_user_sets_tests_reads_and_removes_their_destination(db):
    client, db_patch = _client(db, {"id": "2", "role": "user"})
    with db_patch, patch.object(routes, "validate_url"):
        saved = client.put("/api/users/me/notifications", json={"format": "ntfy", "url": " https://ntfy.sh/ann "})
        tested = client.post("/api/users/me/notifications/test")
        read = client.get("/api/users/me/notifications").get_json()
        removed = client.delete("/api/users/me/notifications")
        after = client.get("/api/users/me/notifications").get_json()
    assert saved.status_code == 200 and tested.status_code == 202
    assert read == {"format": "ntfy", "url": "https://ntfy.sh/ann"}
    assert removed.status_code == 204 and after == {"format": None, "url": None}
    assert _deliveries(db)[0][2]["message"] == "SuggestArr: notifications for your requests are working."


@pytest.mark.parametrize("user, status", [({"id": "2", "role": "user"}, 400), ({"id": "1", "role": "admin"}, 200)])
def test_private_network_destinations_are_for_administrators_only(db, user, status):
    client, db_patch = _client(db, user)
    with db_patch:
        response = client.put("/api/users/me/notifications", json={"format": "ntfy", "url": "http://192.168.1.5/alerts"})
    assert response.status_code == status


@pytest.mark.parametrize("payload, message", [
    ({"format": "json", "url": "https://x.example/hook"}, "format must be"),
    ({"format": "telegram", "url": "https://api.telegram.org/botT/sendMessage"}, "chat_id"),
    ({"format": "discord"}, "url is required"),
])
def test_invalid_destinations_are_explained(db, payload, message):
    client, db_patch = _client(db, {"id": "2", "role": "user"})
    with db_patch, patch.object(routes, "validate_url"):
        response = client.put("/api/users/me/notifications", json=payload)
    assert response.status_code == 400 and message in response.get_json()["error"]


def test_the_administrators_allowlist_also_binds_personal_destinations(db):
    db.set_webhook_allowed_hosts(["ntfy.sh"])
    client, db_patch = _client(db, {"id": "2", "role": "user"})
    with db_patch, patch.object(routes, "validate_url"):
        response = client.put("/api/users/me/notifications", json={"format": "discord", "url": "https://discord.com/api/webhooks/1/x"})
    assert response.status_code == 400 and "allowlist" in response.get_json()["error"]
