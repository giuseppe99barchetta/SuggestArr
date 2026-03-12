# For Pytest, do not remove this file. It is required to run tests.
import logging
import pytest

@pytest.fixture(autouse=True)
def reset_logging():
    logging.disable(logging.NOTSET)