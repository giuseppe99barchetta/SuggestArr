"""Tests for the backend version module.

``APP_VERSION`` is derived from ``client/package.json`` at import time so the
release workflow only needs to bump one file. It is sent to Simkl as
``app-version`` on every request.
"""
import json
import unittest
from pathlib import Path

from api_service.version import APP_NAME, APP_VERSION, USER_AGENT

PACKAGE_JSON = Path(__file__).resolve().parents[2] / "client" / "package.json"


class TestVersion(unittest.TestCase):

    def test_app_version_matches_the_client_package(self):
        declared = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["version"]
        self.assertEqual(APP_VERSION, declared.lstrip("v"))

    def test_the_user_agent_is_built_from_the_two_constants(self):
        self.assertEqual(USER_AGENT, f"{APP_NAME}/{APP_VERSION}")

    def test_the_version_carries_no_leading_v(self):
        """Simkl's app-version is a bare version string."""
        self.assertFalse(APP_VERSION.startswith("v"))


if __name__ == "__main__":
    unittest.main()
