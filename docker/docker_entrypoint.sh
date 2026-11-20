#!/bin/sh
set -e

cd "${SUGGESTARR_APP_DIR:-/app}"

# Defaults first, then whatever the container was started with: for uvicorn the last occurrence of an
# option wins, so `--port 8080` or `--log-level debug` override or add to the defaults. Arguments are
# passed untouched (never through eval).
set -- --host 0.0.0.0 --port "${SUGGESTARR_PORT:-5000}" --log-level info "$@"

exec uvicorn api_service.app:asgi_app "$@"
