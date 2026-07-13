import asyncio
import threading
from flask import Blueprint, jsonify, request, g
from api_service.auth.limiter import limiter
from api_service.auth.middleware import require_role
from api_service.automate_process import ContentAutomation
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.utils.asyncio_loop import close_event_loop

logger = LoggerManager().get_logger("AutomationRoute")
automation_bp = Blueprint('automation', __name__)

_force_run_lock = threading.Lock()
_force_run_running = False


def _workflow_ids():
    ids = (request.get_json(silent=True) or {}).get('ids')
    if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(item, int) for item in ids):
        return None
    return ids


def _workflow_owner():
    return None if g.current_user.get('role') == 'admin' else int(g.current_user['id'])


def _visible_request_user_ids(db):
    selected = request.args.get('user_id', '').strip()
    if g.current_user.get('role') == 'admin':
        return [selected] if selected else None
    if load_env_vars().get('REQUEST_VISIBILITY', 'all') != 'own':
        return [selected] if selected else None
    linked = [str(profile['external_user_id']) for profile in db.get_user_media_profiles(int(g.current_user['id']))]
    return [selected] if selected and selected in linked else linked


@automation_bp.route('/requests/workflow', methods=['GET'])
def request_workflow():
    status = request.args.get('status', 'awaiting_approval')
    if status not in ('all', 'awaiting_approval', 'queued', 'submitting', 'submitted', 'rejected', 'failed', 'blacklisted'):
        return jsonify({'status': 'error', 'message': 'Invalid status'}), 400
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 24))))
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid pagination'}), 400
    media_type = request.args.get('media_type', 'all')
    if media_type not in ('all', 'movie', 'tv'):
        return jsonify({'status': 'error', 'message': 'Invalid media type'}), 400
    db = DatabaseManager()
    items, total = db.list_suggestions(
        _workflow_owner(), status, request.args.get('search', '').strip()[:100], page, per_page, media_type,
        _visible_request_user_ids(db))
    return jsonify({'status': 'success', 'items': items, 'total': total, 'page': page,
                    'pages': max(1, (total + per_page - 1) // per_page)}), 200


def _decide_workflow(approve, blacklist=False):
    ids = _workflow_ids()
    if ids is None:
        return jsonify({'status': 'error', 'message': 'ids must contain 1 to 100 integers'}), 400
    changed = DatabaseManager().decide_suggestions(
        ids, _workflow_owner(), int(g.current_user['id']), approve, blacklist)
    return jsonify({'status': 'success', 'updated': changed}), 200


@automation_bp.route('/requests/workflow/approve', methods=['POST'])
@limiter.limit('20 per minute')
def approve_workflow():
    return _decide_workflow(True)


@automation_bp.route('/requests/workflow/reject', methods=['POST'])
@limiter.limit('20 per minute')
def reject_workflow():
    return _decide_workflow(False)


@automation_bp.route('/requests/workflow/blacklist', methods=['POST'])
@limiter.limit('20 per minute')
def blacklist_workflow():
    return _decide_workflow(False, True)


@automation_bp.route('/requests/workflow/retry', methods=['POST'])
@limiter.limit('20 per minute')
def retry_workflow():
    ids = _workflow_ids()
    if ids is None:
        return jsonify({'status': 'error', 'message': 'ids must contain 1 to 100 integers'}), 400
    changed = DatabaseManager().retry_suggestions(ids, _workflow_owner())
    return jsonify({'status': 'success', 'updated': changed}), 200


@automation_bp.route('/requests/workflow/request-again', methods=['POST'])
@limiter.limit('20 per minute')
def request_workflow_again():
    ids = _workflow_ids()
    if ids is None:
        return jsonify({'status': 'error', 'message': 'ids must contain 1 to 100 integers'}), 400
    remove_blacklist = bool((request.get_json(silent=True) or {}).get('remove_blacklist'))
    changed = DatabaseManager().request_rejected(ids, _workflow_owner(), remove_blacklist)
    return jsonify({'status': 'success', 'updated': changed}), 200


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
        close_event_loop(loop, logger)
        with _force_run_lock:
            _force_run_running = False


@automation_bp.route('/force_run', methods=['POST'])
@require_role('admin')
@limiter.limit("5 per minute")
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
            sort_by=sort_by,
            user_ids=_visible_request_user_ids(db_manager),
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
