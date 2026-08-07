"""Application version for the backend, derived from ``client/package.json``.

The user-facing version is maintained in ``client/package.json`` (bumped by the
release workflow). Backend callers that must report a version (currently the
Simkl API, which requires an ``app-version`` query parameter) read it here.

In production images ``client/package.json`` is copied into the image for this
purpose; locally it is read from the repo checkout.
"""
import json
from pathlib import Path

APP_NAME = "suggestarr"

_PACKAGE_JSON = Path(__file__).resolve().parents[1] / "client" / "package.json"


def _load_app_version() -> str:
    """Return the bare semver from ``client/package.json`` (no leading ``v``).

    Returns:
        str: Version string without a leading ``v`` prefix.

    Raises:
        FileNotFoundError: If ``client/package.json`` is not present.
        KeyError: If the package manifest has no ``version`` field.
        json.JSONDecodeError: If the package manifest is not valid JSON.
    """
    declared = json.loads(_PACKAGE_JSON.read_text(encoding="utf-8"))["version"]
    return str(declared).lstrip("v")


APP_VERSION = _load_app_version()
USER_AGENT = f"{APP_NAME}/{APP_VERSION}"
