import asyncio
import threading
import traceback
from flask import Blueprint, jsonify, request
from api_service.automate_process import ContentAutomation
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager().get_logger("AutomationRoute")
automation_bp = Blueprint('automation', __name__)

_force_run_lock = threading.Lock()
_force_run_running = False


def _run_automation_in_background():
    """Run the automation in a dedicated thread with its own event loop."""
    global _force_run_running
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        content_automation = loop.run_until_complete(ContentAutomation.create())
        loop.run_until_complete(content_automation.run())
        logger.info("Force run completed successfully.")
    except Exception as e:
        logger.error(f'Background force run error: {str(e)}', exc_info=True)
    finally:
        loop.close()
        with _force_run_lock:
            _force_run_running = False


@automation_bp.route('/force_run', methods=['POST'])
def run_now():
    """
    Endpoint to execute the automation process in a background thread.
    Returns immediately while the task runs asynchronously.
    """
    global _force_run_running
    with _force_run_lock:
        if _force_run_running:
            return jsonify({'status': 'busy', 'message': 'A force run is already in progress.'}), 409
        _force_run_running = True

    thread = threading.Thread(target=_run_automation_in_background, daemon=True)
    thread.start()
    return jsonify({'status': 'success', 'message': 'Task started in the background!'}), 202

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
        logger.error(f"Error retrieving requests: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500

@automation_bp.route('/requests/ai-search', methods=['GET'])
def get_ai_requests():
    """Get requests originated from AI Search with pagination and sorting."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        sort_by = request.args.get('sort_by', 'date-desc', type=str)

        valid_sorts = ['date-desc', 'date-asc', 'title-asc', 'title-desc']
        if sort_by not in valid_sorts:
            sort_by = 'date-desc'

        db_manager = DatabaseManager()
        result = db_manager.get_ai_search_requests(page=page, per_page=per_page, sort_by=sort_by)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error retrieving AI search requests: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@automation_bp.route('/requests/stats', methods=['GET'])
def get_requests_stats():
    """Get statistics for automation requests."""
    try:
        db_manager = DatabaseManager()
        stats = db_manager.get_requests_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error retrieving request stats: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500