"""
Main Flask application for managing environment variables and running processes.
"""
from flask import Flask, redirect, render_template, request, jsonify, url_for
from flask_cors import CORS
from utils.utils import AppUtils
from automate_process import ContentAutomation
from config.config import load_env_vars, save_env_vars

# App Factory Pattern for modularity and testability
def create_app():
    """
    Create and configure the Flask application.
    """

    if AppUtils.is_last_worker():
        AppUtils.print_welcome_message() # Print only for last worker

    application = Flask(__name__)
    CORS(application)

    # Register routes
    register_routes(application)

    # Load environment variables at startup
    AppUtils.load_environment()

    return application

def register_routes(app): # pylint: disable=redefined-outer-name
    """
    Register the application routes.
    """

    @app.route('/', methods=['GET', 'POST'])
    def configure():
        """
        Get and save environment variables from the web interface.
        """
        if request.method == 'POST':
            save_env_vars(request)
            return redirect(url_for('configure'))

        # Load current environment variables
        config = load_env_vars()
        return render_template('config.html', config=config)

    @app.route('/run_now', methods=['POST'])
    def run_now():
        """
        Endpoint to execute the process in the background.
        """
        try:
            # Execute automation process
            automation = ContentAutomation()
            automation.run()

            return jsonify({'status': 'success', 'message': 'Process started.'}), 202

        except ValueError as ve:
            return jsonify({'status': 'error', 'message': 'Value error: ' + str(ve)}), 400
        except FileNotFoundError as fnfe:
            return jsonify({'status': 'error', 'message': 'File not found: ' + str(fnfe)}), 404
        except Exception as e: # pylint: disable=broad-except
            return jsonify({'status': 'error', 'message': 'Unexpected error: ' + str(e)}), 500

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
