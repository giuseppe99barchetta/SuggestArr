import ast
from pathlib import Path
from unittest.mock import patch

import pytest

import api_service.db.database_manager as database_manager_module
from api_service.db.database_manager import DatabaseManager


MIXINS = (
    "integration_mixin.py",
    "request_mixin.py",
    "metadata_mixin.py",
    "request_queue_mixin.py",
    "ai_search_mixin.py",
    "cleanup_mixin.py",
    "auth_mixin.py",
    "media_user_mixin.py",
)


def test_facade_exposes_representative_domain_methods():
    for method in (
        "get_integration", "save_request", "get_metadata", "enqueue_request",
        "set_ai_feedback", "get_cleanup_settings", "create_auth_user",
        "get_media_user_identity",
    ):
        assert callable(getattr(DatabaseManager, method))


def test_mixins_do_not_import_database_manager():
    db_dir = Path(database_manager_module.__file__).parent / "components"
    for filename in MIXINS:
        tree = ast.parse((db_dir / filename).read_text(encoding="utf-8"))
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        assert all("database_manager" not in ast.unparse(node) for node in imports)


def test_failed_initialization_can_be_retried():
    DatabaseManager._instance = None
    with patch.object(DatabaseManager, "initialize_db", side_effect=[RuntimeError("boom"), None]), \
         patch.object(database_manager_module, "load_env_vars", return_value={"DB_TYPE": "sqlite"}):
        with pytest.raises(RuntimeError, match="boom"):
            DatabaseManager()
        manager = DatabaseManager()

    assert manager._initialized is True
    assert manager is DatabaseManager._instance
    DatabaseManager._instance = None


def test_refresh_config_uses_historical_patch_target():
    manager = object.__new__(DatabaseManager)
    manager.logger = database_manager_module.LoggerManager.get_logger("DatabaseManagerTest")
    manager.initialize_db = lambda: None

    with patch.object(database_manager_module, "load_env_vars", return_value={"DB_TYPE": "postgres"}) as load:
        manager.refresh_config()

    load.assert_called_once_with(force_reload=True)
    assert manager.db_type == "postgres"
