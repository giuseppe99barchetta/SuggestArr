# For Pytest, do not remove this file. It is required to run tests.
import logging
import os

import pytest

# Importing api_service.app must not start the scheduler or open the real database:
# background jobs would otherwise run against whichever test database is active.
os.environ.setdefault('SUGGESTARR_DISABLE_BACKGROUND', '1')

@pytest.fixture(autouse=True)
def reset_logging():
    logging.disable(logging.NOTSET)