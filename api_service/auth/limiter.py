"""
Flask-Limiter singleton.

Create the Limiter instance here so it can be imported by both app.py
(for init_app) and the auth blueprint (for per-route @limiter.limit decorators)
without circular imports.

Storage: in-memory (default).  No Redis required for a single-container
self-hosted deployment.  Multiple gunicorn/uvicorn workers each maintain
their own counter — the effective rate is limit × worker_count.  That is
acceptable here because login brute-force protection is the primary concern
and the instance count is small.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import g


def suggestarr_rate_limit_key():
    if getattr(g, 'api_key_id', None):
        return f"api-key:{g.api_key_id}"
    if getattr(g, 'current_user', None):
        return f"user:{g.current_user['id']}"
    return get_remote_address()

# key_func=get_remote_address uses X-Forwarded-For when available so that
# rate-limiting works correctly behind a reverse proxy.
# app.py applies ProxyFix to trust the first X-Forwarded-For hop.
limiter = Limiter(
    key_func=suggestarr_rate_limit_key,
    # Global fallback applied to every route that has no explicit @limiter.limit.
    # Prevents unbounded hammering of any endpoint by a single IP.
    default_limits=["200 per minute"],
    storage_uri="memory://",
)
