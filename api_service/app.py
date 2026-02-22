"""
Main Flask application for managing environment variables and running processes.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from asgiref.wsgi import WsgiToAsgi
import logging
import atexit

from api_service.utils.utils import AppUtils
from api_service.config.logger_manager import LoggerManager
from api_service.config.config import load_env_vars

from api_service.blueprints.jellyfin.routes import jellyfin_bp
from api_service.blueprints.seer.routes import seer_bp
from api_service.blueprints.plex.routes import plex_bp
from api_service.blueprints.automation.routes import automation_bp
from api_service.blueprints.logs.routes import logs_bp
from api_service.blueprints.config.routes import config_bp
from api_service.blueprints.tmdb.routes import tmdb_bp
from api_service.blueprints.omdb.routes import omdb_bp
from api_service.blueprints.jobs.routes import jobs_bp

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
            # Strip the subpath from PATH_INFO
            environ['PATH_INFO'] = environ['PATH_INFO'][len(subpath) + 1:]
            # Ensure SCRIPT_NAME correctly reflects the subpath
            environ['SCRIPT_NAME'] = f'/{subpath}'
        return self.app(environ, start_response)

executor = ThreadPoolExecutor(max_workers=3)
logger = LoggerManager.get_logger("APP") 
logger.debug(f"Current log level: {logging.getLevelName(logger.getEffectiveLevel())}")

# App Factory Pattern for modularity and testability
def create_app():
    """
    Create and configure the Flask application.
    """

    if AppUtils.is_last_worker():
        AppUtils.print_welcome_message() # Print only for last worker

    application = Flask(__name__, static_folder='../static')
    CORS(application)

    application.register_blueprint(jellyfin_bp, url_prefix='/api/jellyfin')
    application.register_blueprint(seer_bp, url_prefix='/api/seer')
    application.register_blueprint(plex_bp, url_prefix='/api/plex')
    application.register_blueprint(automation_bp, url_prefix='/api/automation')
    application.register_blueprint(logs_bp, url_prefix='/api')
    application.register_blueprint(config_bp, url_prefix='/api/config')
    application.register_blueprint(tmdb_bp, url_prefix='/api/tmdb')
    application.register_blueprint(omdb_bp, url_prefix='/api/omdb')
    application.register_blueprint(jobs_bp, url_prefix='/api/jobs')

    # Register routes
    register_routes(application)

    # Load environment variables at startup
    AppUtils.load_environment()

    return application

def register_routes(app): # pylint: disable=redefined-outer-name
    """
    Register the application routes.
    """

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """
        Serve the built frontend's index.html or any other static file.
        API routes should be handled by blueprints, not this catch-all.
        """
        # API routes that reach here were not matched by blueprints - return 404
        if path.startswith('api/'):
            from flask import abort
            abort(404)

        app.static_folder = '../static'
        
        env_vars = load_env_vars()
        subpath = env_vars.get('SUBPATH')
        subpath = str(subpath).strip('/') if subpath else ''
        
        # If the browser mistakenly requested the asset including the subpath 
        # (e.g., due to absolute vs relative resolution confusion), we strip it
        # so we can find the actual file in the static directory.
        if subpath and path.startswith(f"{subpath}/"):
            path = path[len(subpath) + 1:]
        elif subpath and path == subpath:
            path = ""
            
        target_path = path if path != "" else "index.html"

        # Resolve and validate the requested path against the static folder to
        # prevent directory traversal using user-controlled `path`.
        static_root = os.path.realpath(app.static_folder)
        full_path = os.path.realpath(os.path.join(static_root, target_path))

        # If the resolved path is outside the static root, do not serve it.
        if os.path.commonpath([static_root, full_path]) != static_root:
            from flask import abort
            abort(404)

        if target_path == "index.html" or not os.path.exists(full_path):
            from flask import Response
            index_path = os.path.join(app.static_folder, 'index.html')
            if not os.path.exists(index_path):
                from flask import abort
                abort(404)
            
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                
            if subpath:
                subpath_prefix = '/' + subpath
            else:
                subpath_prefix = ''
                
            # Inject subpath so frontend knows its base URL
            meta_tag = f'<meta name="suggestarr-subpath" content="{subpath_prefix}">'
            content = content.replace('<head>', f'<head>{meta_tag}')
            
            return Response(content, mimetype='text/html')
        else:
            # Serve the requested file (static assets like JS, CSS, images, etc.).
            # `target_path` has been validated to stay within `static_root`.
            return send_from_directory(app.static_folder, target_path)

app = create_app()
app.wsgi_app = SubpathMiddleware(app.wsgi_app)
asgi_app = WsgiToAsgi(app)
env_vars = load_env_vars()
if env_vars.get('CRON_TIMES'):
    from api_service.config.cron_jobs import start_cron_job
    start_cron_job(env_vars)

# Initialize database and jobs scheduler
try:
    from api_service.db.database_manager import DatabaseManager
    from api_service.jobs.job_manager import JobManager
    from api_service.jobs.discover_automation import execute_discover_job
    from api_service.jobs.recommendation_automation import execute_recommendation_job
    from api_service.jobs.system_job_sync import sync_system_job_from_config

    # Initialize database tables (including discover_jobs)
    db_manager = DatabaseManager()
    db_manager.initialize_db()

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
    logger.info("Jobs scheduler initialized (discover + recommendation)")
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