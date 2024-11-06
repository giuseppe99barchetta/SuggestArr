from flask import Blueprint, jsonify, request
from api_service.automate_process import ContentAutomation
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager().get_logger(__name__)
automation_bp = Blueprint('automation', __name__)

@automation_bp.route('/force_run', methods=['POST'])
async def run_now():
    """
    Endpoint to execute the process in the background.
    """
    try:
        content_automation = await ContentAutomation.create()
        await content_automation.run()
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

@automation_bp.route('/requests', methods=['GET'])
def get_all_requests():
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=5, type=int)
    db_manager = DatabaseManager()
    return jsonify(db_manager.get_all_requests_grouped_by_source(page=page, per_page=per_page))