"""
Main Flask application for managing environment variables and running processes.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from asgiref.wsgi import WsgiToAsgi
import logging
import atexit

from api_service.utils.utils import AppUtils
from api_service.config.logger_manager import LoggerManager
from api_service.config.config import load_env_vars

from api_service.auth.middleware import enforce_authentication
from api_service.auth.limiter import limiter

from api_service.blueprints.auth.routes import auth_bp
from api_service.blueprints.jellyfin.routes import jellyfin_bp
from api_service.blueprints.seer.routes import seer_bp
from api_service.blueprints.plex.routes import plex_bp
from api_service.blueprints.automation.routes import automation_bp
from api_service.blueprints.integrations.routes import integrations_bp
from api_service.blueprints.logs.routes import logs_bp
from api_service.blueprints.config.routes import config_bp
from api_service.blueprints.tmdb.routes import tmdb_bp
from api_service.blueprints.omdb.routes import omdb_bp
from api_service.blueprints.jobs.routes import jobs_bp
from api_service.blueprints.ai_search.routes import ai_search_bp
from api_service.blueprints.health.routes import health_bp
from api_service.blueprints.admin.routes import admin_bp
from api_service.blueprints.users.routes import users_bp
from api_service.blueprints.cleanup.routes import cleanup_bp
from api_service.blueprints.trakt.routes import trakt_bp

class SubpathMiddleware:
    """
    WSGI Middleware to strip the SUBPATH from the request URL
    so Flask routing works correctly behind various reverse proxies.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        env_vars = load_env_vars()
        subpath = env_vars.get('SUBPATH')
        subpath = str(subpath).strip('/') if subpath else ''
        
        if subpath and environ['PATH_INFO'].startswith(f'/{subpath}'):
            # Strip the subpath from PATH_INFO.
            # If the URL is exactly /<subpath> (no trailing slash), the result
            # would be an empty string which is not a valid WSGI PATH_INFO.
            # Fall back to '/' so Flask can match the root route.
            stripped = environ['PATH_INFO'][len(subpath) + 1:]
            environ['PATH_INFO'] = stripped if stripped else '/'
            # Ensure SCRIPT_NAME correctly reflects the subpath
            environ['SCRIPT_NAME'] = f'/{subpath}'
        return self.app(environ, start_response)
from api_service.frontend_routes import SubpathMiddleware, register_routes

executor = ThreadPoolExecutor(max_workers=3)
logger = LoggerManager.get_logger("APP") 
logger.debug(f"Current log level: {logging.getLevelName(logger.getEffectiveLevel())}")

DEFAULT_CORS_ORIGINS = [
    'http://localhost:8080',
    'http://127.0.0.1:8080',
]

# App Factory Pattern for modularity and testability
def create_app():
    """
    Create and configure the Flask application.
    """

    if AppUtils.is_last_worker():
        AppUtils.print_welcome_message() # Print only for last worker

    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    application = Flask(__name__, static_folder=static_dir)

    # ------------------------------------------------------------------
    # Reverse-proxy trust
    # Trust one hop of X-Forwarded-For / X-Forwarded-Proto so that:
    #   - Rate limiting uses the real client IP (not the proxy IP).
    #   - Secure cookie detection works correctly behind HTTPS terminators.
    # ------------------------------------------------------------------
    application.wsgi_app = ProxyFix(application.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # ------------------------------------------------------------------
    # CORS
    # Default: allow the local frontend dev servers used by the Vue app.
    # Credentialed requests cannot use wildcard origins, so operators who
    # expose SuggestArr elsewhere SHOULD set SUGGESTARR_ALLOWED_ORIGINS to
    # a comma-separated allowlist of exact origins.
    # Example: SUGGESTARR_ALLOWED_ORIGINS=https://suggestarr.home.example.com
    # ------------------------------------------------------------------
    allowed_origins_env = os.environ.get('SUGGESTARR_ALLOWED_ORIGINS', '').strip()
    if allowed_origins_env:
        allowed_origins = [o.strip() for o in allowed_origins_env.split(',') if o.strip()]
        CORS(application,
             origins=allowed_origins,
             supports_credentials=True,
             allow_headers=["Authorization", "Content-Type"],
             methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        logger.info("CORS restricted to: %s", allowed_origins)
    else:
        CORS(application,
             origins=DEFAULT_CORS_ORIGINS,
             supports_credentials=True,
             allow_headers=["Authorization", "Content-Type"],
             methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        logger.info("CORS using default frontend origins: %s", DEFAULT_CORS_ORIGINS)

    # ------------------------------------------------------------------
    # Rate limiter
    # ------------------------------------------------------------------
    limiter.init_app(application)

    # ------------------------------------------------------------------
    # Authentication middleware
    # Runs before every request and enforces JWT on all /api/* routes
    # except those explicitly listed in auth.middleware.PUBLIC_ROUTES.
    # ------------------------------------------------------------------
    auth_mode = None
    if os.environ.get("SUGGESTARR_AUTH_DISABLED", "").lower() == "true":
        auth_mode = "disabled"
    else:
        auth_mode = str(load_env_vars().get("AUTH_MODE", "enabled")).strip().lower()

    if auth_mode == "disabled":
        logger.warning("=" * 60)
        logger.warning("!! SECURITY WARNING: Authentication is DISABLED !!")
        logger.warning("!! All API endpoints are publicly accessible.   !!")
        logger.warning("!! Set SUGGESTARR_AUTH_DISABLED=false to re-enable.")
        logger.warning("=" * 60)
    elif auth_mode == "local_bypass":
        logger.warning("=" * 60)
        logger.warning("!! SECURITY WARNING: Local Network Auth Bypass is ENABLED !!")
        logger.warning("!! Trusted local CIDRs bypass login; remote access still needs JWT. !!")
        logger.warning("!! Validate proxy/X-Forwarded-For trust configuration before use. !!")
        logger.warning("=" * 60)

    application.before_request(enforce_authentication)

    # ------------------------------------------------------------------
    # JSON error handlers — never leak stack traces or internal state
    # ------------------------------------------------------------------
    @application.errorhandler(401)
    def handle_401(exc):
        return jsonify({"error": "Authentication required"}), 401

    @application.errorhandler(403)
    def handle_403(exc):
        return jsonify({"error": "Insufficient permissions"}), 403

    @application.errorhandler(404)
    def handle_404(exc):
        return jsonify({"error": "Not found"}), 404

    @application.errorhandler(429)
    def handle_429(exc):
        return jsonify({"error": "Too many requests — please try again later"}), 429

    @application.errorhandler(500)
    def handle_500(exc):
        logger.error("Unhandled internal error: %s", exc, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    # ------------------------------------------------------------------
    # Blueprint registration
    # ------------------------------------------------------------------
    application.register_blueprint(auth_bp, url_prefix='/api/auth')
    application.register_blueprint(jellyfin_bp, url_prefix='/api/jellyfin')
    application.register_blueprint(seer_bp, url_prefix='/api/seer')
    application.register_blueprint(plex_bp, url_prefix='/api/plex')
    application.register_blueprint(automation_bp, url_prefix='/api/automation')
    application.register_blueprint(integrations_bp, url_prefix='/api/integrations')
    application.register_blueprint(logs_bp, url_prefix='/api')
    application.register_blueprint(config_bp, url_prefix='/api/config')
    application.register_blueprint(tmdb_bp, url_prefix='/api/tmdb')
    application.register_blueprint(omdb_bp, url_prefix='/api/omdb')
    application.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    application.register_blueprint(ai_search_bp, url_prefix='/api/ai-search')
    application.register_blueprint(health_bp, url_prefix='/api/health')
    application.register_blueprint(admin_bp, url_prefix='/api/admin')
    application.register_blueprint(users_bp, url_prefix='/api/users')
    application.register_blueprint(cleanup_bp, url_prefix='/api/cleanup')
    application.register_blueprint(trakt_bp, url_prefix='/api/trakt')

    # Register routes
    register_routes(application)

    # Load environment variables at startup
    AppUtils.load_environment()

    return application

app = create_app()
app.wsgi_app = SubpathMiddleware(app.wsgi_app)
asgi_app = WsgiToAsgi(app)
# Initialize database and jobs scheduler
try:
    from api_service.db.database_manager import DatabaseManager
    from api_service.jobs.job_manager import JobManager
    from api_service.jobs.discover_automation import execute_discover_job
    from api_service.jobs.recommendation_automation import execute_recommendation_job
    from api_service.jobs.system_job_sync import sync_system_job_from_config
    from api_service.jobs.queue_worker import run_queue_worker

    # Initialize database tables (including discover_jobs).
    # DatabaseManager.__init__ already calls initialize_db(), so no need to
    # call it a second time here.
    db_manager = DatabaseManager()

    # One-time migration: copy integration credentials from config.yaml into
    # the integrations table if not already present.
    db_manager.migrate_integrations_from_config()

    # Sync system job from YAML config (backwards compatibility)
    sync_result = sync_system_job_from_config()
    if sync_result['status'] == 'success':
        logger.info(f"System job synced from config (ID: {sync_result['job_id']})")
    elif sync_result['status'] == 'skipped':
        logger.debug("No system job to sync (CRON_TIMES not configured)")

    # Initialize and start job scheduler
    job_manager = JobManager.get_instance()
    # Register executors for both job types
    job_manager.set_job_executor(execute_discover_job, job_type='discover')
    job_manager.set_job_executor(execute_recommendation_job, job_type='recommendation')
    job_manager.start()
    job_manager.sync_jobs_from_db()

    # Register Seer delivery queue worker (every 2 min, no overlap)
    job_manager.scheduler.add_job(
        run_queue_worker,
        'interval',
        minutes=2,
        id='seer_queue_worker',
        max_instances=1,
        replace_existing=True,
    )

    # Daily cleanup job (no-op when disabled in cleanup_settings)
    from api_service.jobs.cleanup_automation import execute_cleanup_job, _run_lock as _cleanup_run_lock
    import asyncio as _asyncio
    def _run_cleanup_job():
        if not _cleanup_run_lock.acquire(blocking=False):
            logger.info("Cleanup cron skipped: a run is already in progress.")
            return
        try:
            _asyncio.run(execute_cleanup_job())
        except Exception as exc:
            logger.error(f"Cleanup job error: {exc}")
        finally:
            try:
                _cleanup_run_lock.release()
            except RuntimeError:
                pass
    job_manager.scheduler.add_job(
        _run_cleanup_job,
        'cron',
        hour=4, minute=15,
        id='cleanup_automation',
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Jobs scheduler initialized (discover + recommendation + queue_worker + cleanup)")
except Exception as e:
    import traceback
    logger.error(f"Failed to initialize discover jobs scheduler: {e}")
    logger.error(traceback.format_exc())

def close_log_handlers():
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)
atexit.register(close_log_handlers)

if __name__ == '__main__':
    port = int(os.environ.get('SUGGESTARR_PORT', 5000))
    app.run(host='0.0.0.0', port=port)
