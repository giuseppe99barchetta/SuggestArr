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
from flask import g


def suggestarr_rate_limit_key():
    if getattr(g, 'api_key_id', None):
        return f"api-key:{g.api_key_id}"
    if getattr(g, 'current_user', None):
        return f"user:{g.current_user['id']}"
    from api_service.auth.middleware import _resolve_client_address
    return _resolve_client_address()[0]

# Anonymous clients use forwarded addresses only from explicitly trusted peers.
limiter = Limiter(
    key_func=suggestarr_rate_limit_key,
    # Global fallback applied to every route that has no explicit @limiter.limit.
    # Prevents unbounded hammering of any endpoint by a single IP.
    default_limits=["200 per minute"],
    storage_uri="memory://",
)
