"""Application version constant for the backend.

The user-facing version lives in ``client/package.json``, but that file is a
build input rather than a runtime artifact: the production image builds the
client and copies only the compiled output, so it cannot be read at runtime.
Backend callers that must report a version (currently the Simkl API, which
requires an ``app-version`` query parameter on every request) read it here.

Keep this in sync with ``client/package.json`` on release.
"""

APP_NAME = "suggestarr"
APP_VERSION = "2.11.0"
USER_AGENT = f"{APP_NAME}/{APP_VERSION}"
