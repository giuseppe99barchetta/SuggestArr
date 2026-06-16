from collections import deque
import os
from flask import Blueprint, jsonify, request
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager().get_logger("LogsRoute")
logs_bp = Blueprint('logs', __name__)
DEFAULT_LOG_LIMIT = 500
MAX_LOG_LIMIT = 2000
MAX_LOG_OFFSET = 100000


@logs_bp.route('/logs', methods=['GET'])
def get_logs():
    """
    Endpoint to retrieve logs.
    """
    limit = _get_positive_int_arg('limit', DEFAULT_LOG_LIMIT)
    offset = _get_positive_int_arg('offset', 0)
    limit = min(limit, MAX_LOG_LIMIT)
    offset = min(offset, MAX_LOG_OFFSET)

    logs = read_logs(limit=limit, offset=offset)
    return jsonify(logs), 200

def _get_positive_int_arg(name, default):
    raw_value = request.args.get(name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(value, 0)


def read_logs(log_file='app.log', limit=DEFAULT_LOG_LIMIT, offset=0):
    """
    Function to read log content from the specified log file.
    """
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../config/config_files'))
        log_file = os.path.join(base_dir, log_file)
        limit = max(int(limit), 0)
        offset = max(int(offset), 0)

        if limit == 0:
            return []

        lines_to_keep = limit + offset
        with open(log_file, 'r', encoding='utf-8') as f:
            recent_logs = deque(f, maxlen=lines_to_keep)

        if offset == 0:
            return list(recent_logs)[-limit:]

        logs = list(recent_logs)
        end_index = len(logs) - offset
        if end_index <= 0:
            return []
        start_index = max(0, end_index - limit)
        return logs[start_index:end_index]
    except Exception as e:
        logger.error(f'Error reading logs: {str(e)}')
        return []
