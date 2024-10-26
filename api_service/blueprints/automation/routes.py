from flask import Blueprint, jsonify
from api_service.tasks.tasks import run_content_automation_task
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager().get_logger(__name__)
automation_bp = Blueprint('automation', __name__)

@automation_bp.route('/force_run', methods=['POST'])
async def run_now():
    """
    Endpoint to execute the process in the background.
    """
    try:
        await run_content_automation_task()
        return jsonify({'status': 'success', 'message': 'Task is running in the background!'}), 202
    except ValueError as ve:
        logger.error(f'Value error: {str(ve)}')
        return jsonify({'status': 'error', 'message': 'Value error: ' + str(ve)}), 400
    except FileNotFoundError as fnfe:
        logger.error(f'File not found: {str(fnfe)}')
        return jsonify({'status': 'error', 'message': 'File not found: ' + str(fnfe)}), 404
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Unexpected error: ' + str(e)}), 500
