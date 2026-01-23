from flask import Blueprint, jsonify, request
from api_service.automate_process import ContentAutomation
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager().get_logger("AutomationRoute")
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
def get_requests():
    """Get all automation requests grouped by source with pagination and sorting."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 8, type=int)
        sort_by = request.args.get('sort_by', 'date-desc', type=str)
        
        # Validte sort_by
        valid_sorts = ['date-desc', 'date-asc', 'title-asc', 'title-desc', 'rating-desc', 'rating-asc']
        if sort_by not in valid_sorts:
            sort_by = 'date-desc'
        
        db_manager = DatabaseManager()
        result = db_manager.get_all_requests_grouped_by_source(
            page=page, 
            per_page=per_page,
            sort_by=sort_by
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error retrieving requests: {e}")
        return jsonify({"error": str(e)}), 500
    
@automation_bp.route('/requests/stats', methods=['GET'])
def get_requests_stats():
    """Get statistics for automation requests."""
    try:
        db_manager = DatabaseManager()
        stats = db_manager.get_requests_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error retrieving request stats: {e}")
        return jsonify({"error": str(e)}), 500