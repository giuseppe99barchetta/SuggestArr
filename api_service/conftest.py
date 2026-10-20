# For Pytest, do not remove this file. It is required to run tests.
import logging
import os

import pytest

# Importing api_service.app must not start the scheduler or open the real database:
# background jobs would otherwise run against whichever test database is active.
os.environ.setdefault('SUGGESTARR_DISABLE_BACKGROUND', '1')


@pytest.fixture(scope='session', autouse=True)
def isolated_runtime(tmp_path_factory):
    """Never use the operator's config, database or integrations during tests."""
    from api_service.config import config
    from api_service.db import database_manager

    temporary = tmp_path_factory.mktemp('suggestarr-runtime')
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(config, 'CONFIG_PATH', str(temporary / 'config.yaml'))
        patcher.setattr(database_manager, 'DB_PATH', str(temporary / 'requests.db'))
        patcher.setattr(database_manager.DatabaseManager, '_instance', None)
        config.invalidate_config_cache()
        yield
        config.invalidate_config_cache()

@pytest.fixture(autouse=True)
def reset_logging():
    logging.disable(logging.NOTSET)
