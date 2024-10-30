"""
Main Flask application for managing environment variables and running processes.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from asgiref.wsgi import WsgiToAsgi


from api_service.utils.utils import AppUtils
from api_service.config.logger_manager import LoggerManager

from api_service.blueprints.jellyfin.routes import jellyfin_bp
from api_service.blueprints.seer.routes import seer_bp
from api_service.blueprints.plex.routes import plex_bp
from api_service.blueprints.automation.routes import automation_bp
from api_service.blueprints.logs.routes import logs_bp
from api_service.blueprints.config.routes import config_bp

executor = ThreadPoolExecutor(max_workers=3)
logger = LoggerManager().get_logger(__name__)

# App Factory Pattern for modularity and testability
def create_app():
    """
    Create and configure the Flask application.
    """

    if AppUtils.is_last_worker():
        AppUtils.print_welcome_message() # Print only for last worker

    application = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), '../client/dist'),
        static_url_path='/'
    )
    CORS(application)

    application.register_blueprint(jellyfin_bp, url_prefix='/api/jellyfin')
    application.register_blueprint(seer_bp, url_prefix='/api/seer')
    application.register_blueprint(plex_bp, url_prefix='/api/plex')
    application.register_blueprint(automation_bp, url_prefix='/api/automation')
    application.register_blueprint(logs_bp, url_prefix='/api')
    application.register_blueprint(config_bp, url_prefix='/api/config')

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
        """
        app.static_folder = os.path.join(os.path.dirname(__file__), '../client/dist')
        full_path = os.path.join(app.static_folder, path or 'index.html')
        print(f"Trying to serve: {full_path}")  # Log del percorso effettivo
        if path == "" or not os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, 'index.html')
        else:
            # Serve the requested file (static assets like JS, CSS, images, etc.)
            return send_from_directory(app.static_folder, path)

app = create_app()
asgi_app = WsgiToAsgi(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
