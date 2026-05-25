"""
Frontend static file and SPA fallback routing helpers.
"""
from html import escape
import os

from flask import Response, abort, send_file
from werkzeug.security import safe_join

from api_service.config.config import load_env_vars


def normalize_subpath(value):
    """Return SUBPATH as '' or '/segment' without trailing slash."""
    if value is None:
        return ""

    normalized = str(value).strip()
    if not normalized:
        return ""

    normalized = "/" + normalized.strip("/")
    return "" if normalized == "/" else normalized


def get_configured_subpath():
    """Return normalized SUBPATH from environment first, then config."""
    env_subpath = os.environ.get("SUBPATH")
    if env_subpath not in (None, ""):
        return normalize_subpath(env_subpath)

    return normalize_subpath(load_env_vars().get("SUBPATH"))


def strip_subpath_prefix(path, subpath):
    """Drop leading SUBPATH from frontend request paths when present."""
    normalized_path = (path or "").lstrip("/")
    if not subpath:
        return normalized_path

    subpath_prefix = subpath.lstrip("/")
    if normalized_path == subpath_prefix:
        return ""
    if normalized_path.startswith(f"{subpath_prefix}/"):
        return normalized_path[len(subpath_prefix) + 1:]
    return normalized_path


def request_targets_asset(path):
    """Heuristic: asset requests usually include filename extension."""
    normalized_path = (path or "").strip("/")
    if not normalized_path:
        return False

    filename = normalized_path.rsplit("/", maxsplit=1)[-1]
    return "." in filename and not filename.startswith(".")


def _resolve_static_path(static_root, target_path):
    safe_path = safe_join(static_root, target_path)
    if safe_path is None:
        abort(404)

    full_path = os.path.realpath(safe_path)
    if os.path.commonpath([static_root, full_path]) != static_root:
        abort(404)

    return full_path


def _render_index(static_root, subpath):
    index_path = os.path.join(static_root, "index.html")
    if not os.path.exists(index_path):
        abort(404)

    with open(index_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    escaped_subpath = escape(subpath, quote=True)
    injected_tags = f'<meta name="suggestarr-subpath" content="{escaped_subpath}">'
    if subpath:
        injected_tags += f'<base href="{escaped_subpath}/">'

    return Response(content.replace("<head>", f"<head>{injected_tags}"), mimetype="text/html")


class SubpathMiddleware:
    """
    WSGI middleware to strip SUBPATH from request URL so Flask routing still works.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        subpath = get_configured_subpath()

        if subpath and environ["PATH_INFO"] == subpath:
            query_string = environ.get("QUERY_STRING", "")
            location = f"{subpath}/"
            if query_string:
                location = f"{location}?{query_string}"

            start_response(
                "308 Permanent Redirect",
                [
                    ("Location", location),
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", "0"),
                ],
            )
            return [b""]

        if subpath and environ["PATH_INFO"].startswith(f"{subpath}/"):
            stripped = environ["PATH_INFO"][len(subpath):]
            environ["PATH_INFO"] = stripped if stripped else "/"
            environ["SCRIPT_NAME"] = subpath

        return self.app(environ, start_response)


def register_routes(app):  # pylint: disable=redefined-outer-name
    """Register frontend routes."""

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path.startswith("api/"):
            abort(404)

        subpath = get_configured_subpath()
        relative_path = strip_subpath_prefix(path, subpath)
        target_path = relative_path or "index.html"
        static_root = os.path.realpath(app.static_folder)

        if target_path == "index.html":
            return _render_index(static_root, subpath)

        full_path = _resolve_static_path(static_root, target_path)

        if os.path.isfile(full_path):
            return send_file(full_path)

        if relative_path and request_targets_asset(relative_path):
            abort(404)

        return _render_index(static_root, subpath)
