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
from api_service.utils.request_profiles import (
    validate_request_profiles,
    validate_request_profiles_with_seer,
)
from api_service.utils import request_scope
from api_service.services.tmdb.localization import display_language, localize_groups

logger = LoggerManager().get_logger("AutomationRoute")
automation_bp = Blueprint('automation', __name__)

_force_run_lock = threading.Lock()
_force_run_running = False
_FEEDBACK_VALUES = {'interested', 'not_interested', 'already_seen', 'seen_liked', 'too_similar',
                    'save_for_later'}
_FEEDBACK_REASONS = {'genre', 'provider', 'content', 'title', 'other'}


def _feedback_payload():
    data = request.get_json(silent=True) or {}
    feedback = data.get('feedback')
    reason_type = data.get('reason_type')
    reason_text = data.get('reason_text')
    if feedback not in _FEEDBACK_VALUES:
        return None, (jsonify({'status': 'error', 'message': 'Invalid feedback value'}), 400)
    if reason_type is not None and reason_type not in _FEEDBACK_REASONS:
        return None, (jsonify({'status': 'error', 'message': 'Invalid feedback reason'}), 400)
    if reason_text is not None:
        if not isinstance(reason_text, str) or len(reason_text.strip()) > 500:
            return None, (jsonify({'status': 'error', 'message': 'reason_text must be at most 500 characters'}), 400)
        reason_text = reason_text.strip() or None
    # The title is what the recommendation prompt can actually use, so it is stored with
    # the rating. It stays optional: an older client simply keeps the previous behaviour.
    title = data.get('title')
    if title is not None and not isinstance(title, str):
        return None, (jsonify({'status': 'error', 'message': 'title must be a string'}), 400)
    year = data.get('year')
    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError):
            return None, (jsonify({'status': 'error', 'message': 'year must be an integer'}), 400)
    return (feedback, reason_type, reason_text, data.get('media_user_id'), title, year), None


def _workflow_ids():
    ids = (request.get_json(silent=True) or {}).get('ids')
    if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(item, int) for item in ids):
        return None
    return ids


def _suggestion_scope(db):
    return request_scope.suggestion_scope(
        db, g.current_user, load_env_vars(), request.args.get('user_id', ''))


def _localize(db, *groups):
    """
    Show the listed titles in the reader's language (see services/tmdb/localization.py).

    Args:
        db: Database manager.
        groups: (items, fields) pairs, localized with one shared lookup budget.
    """
    env = load_env_vars()
    try:
        own = db.get_user_language(int(g.current_user['id']))
    except Exception:
        own = None
    language = display_language(own, env)
    integration = db.get_integration('tmdb') or {}
    api_key = integration.get('api_key') or env.get('TMDB_API_KEY')
    localize_groups(list(groups), language, db, api_key)


def _visible_request_user_ids(db):
    return request_scope.visible_request_user_ids(
        db, g.current_user, load_env_vars(), request.args.get('user_id', ''))


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
    scope = _suggestion_scope(db)
    items, total = db.list_suggestions(
        scope.owner_id, status, request.args.get('search', '').strip()[:100], page, per_page, media_type,
        scope.media_user_ids, int(g.current_user['id']), scope.include_unassigned)
    _localize(db, (items, [('tmdb_id', 'media_type', 'title', 'overview')]))
    return jsonify({'status': 'success', 'items': items, 'total': total, 'page': page,
                    'pages': max(1, (total + per_page - 1) // per_page)}), 200


def _requested_profiles():
    """
    Read an optional per-media-type request profile from an approval call.

    Lets the person approving decide how these items are fetched instead of
    always taking the job's profile or Jellyseerr's default.  The shape is the
    same one jobs use, so a caller that can fill the job dialog can fill this.

    Returns:
        dict: ``{'movie': {...}, 'tv': {...}}``, possibly empty.

    Raises:
        ValueError: On a malformed profile, or on ids Jellyseerr does not know.
                    The caller answers 400 rather than fetching with a profile
                    that means something else on the server it ends up on.
    """
    requested = (request.get_json(silent=True) or {}).get('profile')
    profile = validate_request_profiles(requested)
    validate_request_profiles_with_seer(profile)
    return profile


def _decide_workflow(approve, blacklist=False):
    ids = _workflow_ids()
    if ids is None:
        return jsonify({'status': 'error', 'message': 'ids must contain 1 to 100 integers'}), 400

    profile = {}
    if approve:
        try:
            profile = _requested_profiles()
        except ValueError:
            logger.warning("Invalid request profile supplied in workflow decision", exc_info=True)
            return jsonify({'status': 'error', 'message': 'Invalid profile request'}), 400

    # The profile and the status change are committed together: the worker
    # never picks up a queued row without its profile, and a failed approval
    # leaves no profile behind.
    db = DatabaseManager()
    scope = _suggestion_scope(db)
    changed = db.decide_suggestions(
        ids, scope.owner_id, int(g.current_user['id']), approve, blacklist, profiles=profile,
        include_unassigned=scope.include_unassigned)
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
    db = DatabaseManager()
    scope = _suggestion_scope(db)
    changed = db.retry_suggestions(ids, scope.owner_id, scope.include_unassigned)
    return jsonify({'status': 'success', 'updated': changed}), 200


@automation_bp.route('/requests/workflow/request-again', methods=['POST'])
@limiter.limit('20 per minute')
def request_workflow_again():
    ids = _workflow_ids()
    if ids is None:
        return jsonify({'status': 'error', 'message': 'ids must contain 1 to 100 integers'}), 400
    remove_blacklist = bool((request.get_json(silent=True) or {}).get('remove_blacklist'))
    db = DatabaseManager()
    scope = _suggestion_scope(db)
    changed = db.request_rejected(ids, scope.owner_id, remove_blacklist, scope.include_unassigned)
    return jsonify({'status': 'success', 'updated': changed}), 200


@automation_bp.route('/requests/workflow/<int:suggestion_id>/feedback', methods=['PUT'])
@limiter.limit('30 per minute')
def set_request_feedback(suggestion_id):
    """Save personal feedback without changing the shared request or blacklist."""
    parsed, error = _feedback_payload()
    if error:
        return error
    feedback, reason_type, reason_text, _, title, year = parsed
    db = DatabaseManager()
    scope = _suggestion_scope(db)
    result = db.set_suggestion_feedback(
        suggestion_id, scope.owner_id, int(g.current_user['id']), feedback, reason_type, reason_text,
        scope.media_user_ids, scope.include_unassigned, title, year,
    )
    if result is None:
        return jsonify({'status': 'error', 'message': 'Suggestion not found'}), 404
    return jsonify({'status': 'success', 'feedback': result}), 200


@automation_bp.route('/requests/workflow/<int:suggestion_id>/feedback', methods=['DELETE'])
@limiter.limit('30 per minute')
def clear_request_feedback(suggestion_id):
    db = DatabaseManager()
    scope = _suggestion_scope(db)
    removed = db.clear_suggestion_feedback(
        suggestion_id, scope.owner_id, int(g.current_user['id']), scope.media_user_ids,
        scope.include_unassigned,
    )
    return jsonify({'status': 'success', 'removed': removed}), 200


@automation_bp.route('/requests/media/<media_type>/<tmdb_id>/feedback', methods=['PUT'])
@limiter.limit('30 per minute')
def set_sent_request_feedback(media_type, tmdb_id):
    """Save personal feedback for a canonical request already sent to Seer."""
    if media_type not in ('movie', 'tv'):
        return jsonify({'status': 'error', 'message': 'Invalid media type'}), 400
    parsed, error = _feedback_payload()
    if error:
        return error
    feedback, reason_type, reason_text, media_user_id, title, year = parsed
    db = DatabaseManager()
    visible_user_ids = _visible_request_user_ids(db)
    if not db.has_visible_suggestarr_request(tmdb_id, media_type, media_user_id, visible_user_ids):
        return jsonify({'status': 'error', 'message': 'Request not found'}), 404
    result = db.set_media_feedback(
        int(g.current_user['id']), media_user_id, tmdb_id, media_type,
        feedback, reason_type, reason_text, title, year,
    )
    return jsonify({'status': 'success', 'feedback': result}), 200


@automation_bp.route('/requests/media/<media_type>/<tmdb_id>/feedback', methods=['DELETE'])
@limiter.limit('30 per minute')
def clear_sent_request_feedback(media_type, tmdb_id):
    if media_type not in ('movie', 'tv'):
        return jsonify({'status': 'error', 'message': 'Invalid media type'}), 400
    data = request.get_json(silent=True) or {}
    media_user_id = data.get('media_user_id')
    db = DatabaseManager()
    visible_user_ids = _visible_request_user_ids(db)
    if not db.has_visible_suggestarr_request(tmdb_id, media_type, media_user_id, visible_user_ids):
        return jsonify({'status': 'error', 'message': 'Request not found'}), 404
    removed = db.clear_media_feedback(int(g.current_user['id']), media_user_id, tmdb_id, media_type)
    return jsonify({'status': 'success', 'removed': removed}), 200


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

def _list_page(default_per_page):
    """
    Read page and per_page for a list route, bounded like the workflow route.

    Each listed item may cost a translation lookup, so per_page is capped.

    Returns:
        tuple: (page >= 1, 1 <= per_page <= 100)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', default_per_page, type=int)
    return max(1, page), min(100, max(1, per_page))


@automation_bp.route('/requests', methods=['GET'])
def get_requests():
    """Get all automation requests grouped by source with pagination and sorting."""
    try:
        page, per_page = _list_page(default_per_page=8)
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
            feedback_user_id=int(g.current_user['id']),
        )
        sources = result.get('data') or []
        _localize(db_manager,
                  (sources, [('source_id', 'media_type', 'source_title', 'source_overview')]),
                  ([req for source in sources for req in source.get('requests') or []],
                   [('request_id', 'media_type', 'title', 'overview')]))

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error retrieving requests: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500

@automation_bp.route('/requests/ai-search', methods=['GET'])
def get_ai_requests():
    """Get requests originated from AI Search with pagination and sorting."""
    try:
        page, per_page = _list_page(default_per_page=12)
        sort_by = request.args.get('sort_by', 'date-desc', type=str)

        valid_sorts = ['date-desc', 'date-asc', 'title-asc', 'title-desc']
        if sort_by not in valid_sorts:
            sort_by = 'date-desc'

        db_manager = DatabaseManager()
        result = db_manager.get_ai_search_requests(page=page, per_page=per_page, sort_by=sort_by)
        _localize(db_manager, (result.get('data') or [], [('request_id', 'media_type', 'title', 'overview')]))
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
