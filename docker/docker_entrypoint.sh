#!/bin/sh
set -e

cd "${SUGGESTARR_APP_DIR:-/app}"

# Default command: listen on SUGGESTARR_PORT. Arguments given to the container replace it, and are passed
# to uvicorn untouched (never through eval).
if [ "$#" -eq 0 ]; then
  set -- --host 0.0.0.0 --port "${SUGGESTARR_PORT:-5000}" --log-level info
fi

exec uvicorn api_service.app:asgi_app "$@"
