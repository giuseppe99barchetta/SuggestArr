"""
Flask web application for configuring environment variables related to TMDb, Jellyfin, 
and Jellyseer APIs. 

Features:
- Save user configurations through a web interface.
- Execute media processing in the background.

Endpoints:
- `/`: Manage configuration settings.
- `/run_now`: Execute the media processing.

Dependencies:
- Flask, Flask-CORS, dotenv, logger.
"""
from flask import Flask, redirect, render_template, request, jsonify, url_for
from flask_cors import CORS
from dotenv import load_dotenv

from automate_process import ContentAutomation
from config.logger_manager import LoggerManager
from config.config import load_env_vars, save_env_vars

logger = LoggerManager.get_logger(__name__)

app = Flask(__name__)
CORS(app)

def reload_env():
    """
    Ricarica le variabili d'ambiente dal file .env
    """
    load_dotenv(override=True)
    logger.debug("Environment variables reloaded from .env")


@app.route('/', methods=['GET', 'POST'])
def configure():
    """
    Get and save environment variables from the web interface.
    """
    if request.method == 'POST':
        logger.debug("Received POST request to save configuration.")
        save_env_vars(request)
        logger.info("Configuration saved successfully.")
        return redirect(url_for('configure'))

    # Carica le variabili correnti dal file .env
    config = load_env_vars()

    logger.debug("Configuration page loaded with current environment values.")
    return render_template('config.html', config=config)

@app.route('/run_now', methods=['POST'])
def run_now():
    """
    Endpoint to execute the process in the background.
    """
    logger.info("Received request to start process now.")

    try:
        # Esegui il processo di automazione
        automation = ContentAutomation()
        automation.run()

        logger.debug("Process executed successfully in the background.")
        return jsonify({'status': 'success', 'message': 'Process started.'}), 202

    except ValueError as ve:
        logger.error("Value error occurred: %s", str(ve))
        return jsonify({'status': 'error', 'message': 'Value error: ' + str(ve)}), 400
    except FileNotFoundError as fnfe:
        logger.error("File not found: %s", str(fnfe))
        return jsonify({'status': 'error', 'message': 'File not found: ' + str(fnfe)}), 404
    except Exception as e: # pylint: disable=broad-except
        logger.error("An unexpected error occurred: %s", str(e))
        return jsonify({'status': 'error', 'message': 'Unexpected error: ' + str(e)}), 500


if __name__ == '__main__':
    print("\n\n===========================================================")
    print("Welcome to the Jellyfin TMDb Sync Automation Application!")
    print("Manage your settings through the web interface at: http://localhost:5000")
    print("Fill in the input fields with your data and let the cron job handle the rest!")
    print("To run the automation process immediately, click the 'Force Run' button.")
    print("The 'Force Run' button will appear only after you save your settings.")
    print("===========================================================\n\n")
    app.run(host='0.0.0.0', port=5000)
