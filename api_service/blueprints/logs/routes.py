import os
from flask import Blueprint, jsonify
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager().get_logger("LogsRoute")
logs_bp = Blueprint('logs', __name__)

@logs_bp.route('/logs', methods=['GET'])
def get_logs():
    """
    Endpoint to retrieve logs.
    """
    logs = read_logs()
    return jsonify(logs), 200

def read_logs(log_file='app.log'):
    """
    Function to read log content from the specified log file.
    """
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../config/config_files'))
        log_file = os.path.join(base_dir, log_file)
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.readlines()
        return logs
    except Exception as e:
        logger.error(f'Error reading logs: {str(e)}')
        return []
