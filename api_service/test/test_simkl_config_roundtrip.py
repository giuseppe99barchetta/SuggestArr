"""Config export/import coverage for Simkl.

The Trakt export path returns early for users with no Trakt link, so the
regression worth guarding is that a Simkl-only user survives a round trip.
"""
from unittest.mock import patch

import pytest

import api_service.db.database_manager as dm_mod
from api_service.db.database_manager import DatabaseManager
from api_service.services import config_service
from api_service.services.integration_sanitizer import sanitize_integration_config


@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "roundtrip.db")
    with patch.object(dm_mod, "DB_PATH", db_file), \
         patch("api_service.db.database_manager.load_env_vars", return_value={"DB_TYPE": "sqlite"}):
        DatabaseManager._instance = None
        yield DatabaseManager()
        DatabaseManager._instance = None


def link_simkl(db, external_id="jf-1", username="Wire", account_id="8307044"):
    identity = db.upsert_media_user_identity("jellyfin", external_id, username)
    link_id = db.upsert_simkl_account_link(identity["id"], account_id, username)
    db.upsert_simkl_oauth_tokens(link_id, "access-token")
    db.upsert_simkl_source(identity["id"], "watched_history", "watched_history")
    return identity, link_id


# ---- Sanitizer ---------------------------------------------------------------

def test_a_client_secret_is_stripped_from_simkl_config():
    """The PIN flow never uses one, so a secret here is a mistake at best."""
    result = sanitize_integration_config("simkl", {
        "client_id": "cid", "client_secret": "should-not-persist", "access_token": "nope",
    })
    assert result == {"client_id": "cid"}


def test_trakt_keeps_both_credential_keys():
    assert sanitize_integration_config("trakt", {
        "client_id": "cid", "client_secret": "secret", "access_token": "nope",
    }) == {"client_id": "cid", "client_secret": "secret"}


def test_unlisted_services_pass_through_untouched():
    assert sanitize_integration_config("jellyfin", {"api_url": "http://x", "api_key": "k"}) == {
        "api_url": "http://x", "api_key": "k",
    }


# ---- Export ------------------------------------------------------------------

def test_a_simkl_only_user_is_exported_with_their_link(db):
    """The Trakt branch returns early for these users; Simkl must not be lost."""
    link_simkl(db)
    exported = config_service._export_media_users(db)

    assert len(exported) == 1
    simkl = exported[0]["simkl"]
    assert simkl["simkl_username"] == "Wire"
    assert simkl["simkl_user_id"] == "8307044"
    assert "trakt" not in exported[0]


def test_export_redacts_the_access_token_by_default(db):
    link_simkl(db)
    exported = config_service._export_media_users(db)
    assert exported[0]["simkl"]["oauth_tokens"]["access_token"] == config_service.REDACTED


def test_export_emits_the_real_token_when_secrets_are_requested(db):
    link_simkl(db)
    exported = config_service._export_media_users(db, include_secrets=True)
    tokens = exported[0]["simkl"]["oauth_tokens"]

    assert tokens["access_token"] == "access-token"
    # Simkl issues no refresh token, so exporting a Trakt-shaped pair would
    # describe a credential that does not exist.
    assert "refresh_token" not in tokens


def test_export_carries_the_source_flags(db):
    identity, _ = link_simkl(db)
    db.upsert_simkl_source(
        identity["id"], "watched_history", "watched_history", use_as_seed=False,
    )
    sources = config_service._export_media_users(db)[0]["simkl"]["sources"]

    assert len(sources) == 1
    assert sources[0]["use_as_seed"] is False


def test_a_user_with_no_links_exports_neither_block(db):
    db.upsert_media_user_identity("jellyfin", "jf-2", "bob")
    exported = config_service._export_media_users(db)

    assert "simkl" not in exported[0]
    assert "trakt" not in exported[0]


def test_the_watch_cache_is_not_exported(db):
    """It is derived data the next sync rebuilds; shipping hundreds of rows
    per user inside a config snapshot would bloat it for no gain."""
    _, link_id = link_simkl(db)
    db.upsert_simkl_watched_cache(link_id, [{
        "simkl_id": "1", "simkl_type": "shows", "media_type": "tv", "status": "completed",
        "tmdb_id": "1", "title": "X", "year": 2000, "last_watched_at": 1,
    }])
    exported = config_service._export_media_users(db, include_secrets=True)

    assert "cache" not in exported[0]["simkl"]
    assert "watched_cache" not in exported[0]["simkl"]


# ---- Import ------------------------------------------------------------------

def test_a_simkl_only_snapshot_restores_the_link_token_and_source(db):
    config_service._import_media_users(db, [{
        "provider": "jellyfin", "external_user_id": "jf-9", "external_username": "carol",
        "simkl": {
            "simkl_user_id": "111", "simkl_username": "carol",
            "token_source": "manual_oauth", "status": "connected",
            "oauth_tokens": {"access_token": "restored-token", "expires_at": None},
            "sources": [{
                "source_type": "watched_history", "source_key": "watched_history",
                "enabled": True, "use_as_seed": False, "use_as_exclusion": True,
            }],
        },
    }])

    identity = db.get_media_user_identity("jellyfin", "jf-9")
    link = db.get_simkl_account_link(identity["id"])
    assert link["simkl_username"] == "carol"
    assert db.get_simkl_oauth_tokens(link["id"])["access_token"] == "restored-token"
    assert db.get_simkl_sources(identity["id"])[0]["use_as_seed"] is False


def test_import_gates_the_token_on_access_token_alone(db):
    """Requiring a refresh token, as the Trakt path does, would silently
    discard every restored Simkl token."""
    config_service._import_media_users(db, [{
        "provider": "jellyfin", "external_user_id": "jf-10",
        "simkl": {
            "simkl_user_id": "1", "simkl_username": "d",
            "oauth_tokens": {"access_token": "only-access"},
        },
    }])

    identity = db.get_media_user_identity("jellyfin", "jf-10")
    link = db.get_simkl_account_link(identity["id"])
    assert db.get_simkl_oauth_tokens(link["id"])["access_token"] == "only-access"


def test_a_redacted_token_is_not_restored(db):
    config_service._import_media_users(db, [{
        "provider": "jellyfin", "external_user_id": "jf-11",
        "simkl": {
            "simkl_user_id": "1", "simkl_username": "e",
            "oauth_tokens": {"access_token": config_service.REDACTED},
        },
    }])

    identity = db.get_media_user_identity("jellyfin", "jf-11")
    link = db.get_simkl_account_link(identity["id"])
    assert db.get_simkl_oauth_tokens(link["id"]) is None


def test_a_full_round_trip_preserves_both_providers(db):
    identity, _ = link_simkl(db, external_id="jf-both")
    trakt_link = db.upsert_trakt_account_link(identity["id"], "t-1", "trakt_name")
    db.upsert_trakt_oauth_tokens(trakt_link, "t-access", "t-refresh", 999)

    exported = config_service._export_media_users(db, include_secrets=True)
    db.unlink_simkl_account(identity["id"])
    db.unlink_trakt_account(identity["id"])
    config_service._import_media_users(db, exported)

    restored = db.get_media_user_identity("jellyfin", "jf-both")
    assert db.get_simkl_account_link(restored["id"])["simkl_username"] == "Wire"
    assert db.get_trakt_account_link(restored["id"])["trakt_username"] == "trakt_name"


def test_simkl_client_id_is_treated_as_a_db_integration_key():
    """Otherwise it would be exported under both integrations and settings."""
    assert "SIMKL_CLIENT_ID" in config_service._DB_INTEGRATION_KEYS
    assert "SIMKL_CLIENT_ID" not in config_service._VALID_SETTING_KEYS
