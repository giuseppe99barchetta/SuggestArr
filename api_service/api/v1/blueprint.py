from copy import deepcopy
from pathlib import Path
import time

import yaml
from flask import Blueprint, Response, jsonify, g, request

from api_service.auth.limiter import limiter
from api_service.auth.middleware import require_role
from api_service.config.config import load_env_vars
from api_service.db.database_manager import DatabaseManager
from api_service.db.job_repository import JobRepository
from api_service.jobs.job_manager import JobManager
from api_service.jobs.discover_automation import DiscoverAutomation
from api_service.jobs.recommendation_automation import RecommendationAutomation
from api_service.jobs.trakt_recommendations_automation import TraktRecommendationsAutomation
from api_service.utils.asyncio_loop import run_coroutine_sync
from api_service.config.logger_manager import LoggerManager

public_api_v1_bp = Blueprint('public_api_v1', __name__)
logger = LoggerManager.get_logger('PublicApiV1')
_OPENAPI_PATH = Path(__file__).parents[2] / 'openapi' / 'public-api-v1.yaml'


@public_api_v1_bp.before_request
def _audit_start():
    g.public_api_started_at = time.monotonic()


@public_api_v1_bp.after_request
def _audit_response(response):
    user = getattr(g, 'current_user', {})
    logger.info('public_api method=%s path=%s status=%s user_id=%s auth=%s api_key_id=%s duration_ms=%d',
                request.method, request.path, response.status_code, user.get('id'),
                getattr(g, 'auth_method', None), getattr(g, 'api_key_id', None),
                int((time.monotonic() - getattr(g, 'public_api_started_at', time.monotonic())) * 1000))
    return response


def _openapi_document():
    with _OPENAPI_PATH.open(encoding='utf-8') as stream:
        document = yaml.safe_load(stream)
    document = deepcopy(document)
    document['servers'] = [{'url': request.script_root or '/'}]
    return document


@public_api_v1_bp.route('/openapi.json', methods=['GET'])
def openapi_json():
    return jsonify(_openapi_document())


@public_api_v1_bp.route('/openapi.yaml', methods=['GET'])
def openapi_yaml():
    return Response(yaml.safe_dump(_openapi_document(), sort_keys=False), mimetype='application/yaml')


@public_api_v1_bp.route('/status', methods=['GET'])
def status():
    return jsonify({'data': {'service': 'SuggestArr', 'api_version': 'v1', 'status': 'ok'}}), 200


@public_api_v1_bp.route('/me', methods=['GET'])
@limiter.limit('120 per minute')
def me():
    user = g.current_user
    return jsonify({'data': {
        'id': int(user['id']) if str(user['id']).isdigit() else user['id'],
        'username': user['username'], 'role': user['role'],
        'permissions': {'can_manage_ai': bool(user.get('can_manage_ai'))},
        'authentication': {'method': g.auth_method, 'api_key_id': g.api_key_id, 'api_key_name': g.api_key_name},
    }}), 200


def _job_payload(job):
    """Stable, credential-free subset of the internal job record."""
    fields = ('id', 'name', 'job_type', 'enabled', 'media_type', 'filters', 'schedule_type',
              'schedule_value', 'max_results', 'user_ids', 'owner_id', 'created_at', 'updated_at')
    return {field: job.get(field) for field in fields}


def _visible_job(job):
    return g.current_user['role'] == 'admin' or job.get('owner_id') == int(g.current_user['id'])


def _page_args():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))
    except (TypeError, ValueError):
        return None
    if page < 1 or not 1 <= per_page <= 100:
        return None
    return page, per_page


@public_api_v1_bp.route('/jobs', methods=['GET'])
@limiter.limit('120 per minute')
def jobs():
    pagination = _page_args()
    if not pagination:
        return jsonify({'error': {'code': 'validation_error', 'message': 'Invalid pagination.'}}), 400
    enabled = request.args.get('enabled')
    job_type = request.args.get('job_type')
    if enabled not in (None, 'true', 'false') or job_type not in (None, 'discover', 'recommendation', 'trakt_recommendations'):
        return jsonify({'error': {'code': 'validation_error', 'message': 'Invalid filters.'}}), 400
    items = [job for job in JobRepository().get_all_jobs() if _visible_job(job)]
    if enabled is not None:
        items = [job for job in items if bool(job.get('enabled')) == (enabled == 'true')]
    if job_type:
        items = [job for job in items if job.get('job_type') == job_type]
    page, per_page = pagination
    total = len(items)
    return jsonify({'data': [_job_payload(job) for job in items[(page - 1) * per_page:page * per_page]],
                    'meta': {'page': page, 'per_page': per_page, 'total': total, 'pages': max(1, (total + per_page - 1) // per_page)}}), 200


@public_api_v1_bp.route('/jobs/<int:job_id>', methods=['GET'])
@limiter.limit('120 per minute')
def job(job_id):
    item = JobRepository().get_job(job_id)
    if not item or not _visible_job(item):
        return jsonify({'error': {'code': 'not_found', 'message': 'Job not found.'}}), 404
    return jsonify({'data': _job_payload(item)}), 200


@public_api_v1_bp.route('/jobs/<int:job_id>/preview', methods=['POST'])
@limiter.limit('10 per minute')
def preview_job(job_id):
    item = JobRepository().get_job(job_id)
    if not item or not _visible_job(item):
        return jsonify({'error': {'code': 'not_found', 'message': 'Job not found.'}}), 404

    async def preview():
        if item.get('job_type') == 'recommendation':
            automation = await RecommendationAutomation.create(job_id, dry_run=True)
        elif item.get('job_type') == 'trakt_recommendations':
            automation = await TraktRecommendationsAutomation.create(job_id, dry_run=True)
        else:
            automation = await DiscoverAutomation.create(job_id)
        return await automation.run(dry_run=True)

    result = run_coroutine_sync(preview())
    if not result.success:
        return jsonify({'error': {'code': 'service_unavailable', 'message': 'Job preview failed.'}}), 503
    return jsonify({'data': {'job_id': job_id, 'items_count': result.results_count, 'items': result.dry_run_items or []}}), 200


def _run_payload(run):
    fields = ('id', 'job_id', 'job_name', 'status', 'trigger_source', 'results_count', 'requested_count', 'error_message', 'started_at', 'finished_at')
    return {field: run.get(field) for field in fields}


@public_api_v1_bp.route('/jobs/<int:job_id>/runs', methods=['POST'])
@limiter.limit('5 per minute')
def start_run(job_id):
    job_data = JobRepository().get_job(job_id)
    if not job_data or not _visible_job(job_data):
        return jsonify({'error': {'code': 'not_found', 'message': 'Job not found.'}}), 404
    execution_id = JobManager.get_instance().enqueue_job_run(job_id, int(g.current_user['id']), g.api_key_id)
    run = JobRepository().get_execution(execution_id)
    response = jsonify({'data': _run_payload(run)})
    response.status_code = 202
    response.headers['Location'] = f'/api/v1/runs/{execution_id}'
    return response


@public_api_v1_bp.route('/runs', methods=['GET'])
@limiter.limit('120 per minute')
def runs():
    pagination = _page_args()
    if not pagination:
        return jsonify({'error': {'code': 'validation_error', 'message': 'Invalid pagination.'}}), 400
    job_id, status = request.args.get('job_id', type=int), request.args.get('status')
    if status and status not in ('queued', 'running', 'completed', 'failed', 'skipped'):
        return jsonify({'error': {'code': 'validation_error', 'message': 'Invalid status.'}}), 400
    records = JobRepository().get_recent_history(1000)
    records = [record for record in records if (not job_id or record['job_id'] == job_id) and (not status or record['status'] == status)]
    if g.current_user['role'] != 'admin':
        own = {job['id'] for job in JobRepository().get_all_jobs() if _visible_job(job)}
        records = [record for record in records if record['job_id'] in own]
    page, per_page = pagination
    total = len(records)
    return jsonify({'data': [_run_payload(row) for row in records[(page - 1) * per_page:page * per_page]], 'meta': {'page': page, 'per_page': per_page, 'total': total, 'pages': max(1, (total + per_page - 1) // per_page)}}), 200


@public_api_v1_bp.route('/runs/<int:run_id>', methods=['GET'])
@limiter.limit('120 per minute')
def run(run_id):
    record = JobRepository().get_execution(run_id)
    if not record:
        return jsonify({'error': {'code': 'not_found', 'message': 'Run not found.'}}), 404
    job_data = JobRepository().get_job(record['job_id'])
    if not job_data or not _visible_job(job_data):
        return jsonify({'error': {'code': 'not_found', 'message': 'Run not found.'}}), 404
    return jsonify({'data': _run_payload(record)}), 200


def _visible_request_user_ids(db):
    selected = request.args.get('user_id', '').strip()
    if g.current_user['role'] == 'admin':
        return [selected] if selected else None
    if load_env_vars().get('REQUEST_VISIBILITY', 'all') != 'own':
        return [selected] if selected else None
    linked = [str(profile['external_user_id']) for profile in db.get_user_media_profiles(int(g.current_user['id']))]
    return [selected] if selected and selected in linked else linked


def _request_statistics(db, users=None):
    """Return request counters for all users or a visible-user subset."""
    ph = '%s' if db.db_type in ('mysql', 'mariadb', 'postgres') else '?'
    where, params = ["requested_by = 'SuggestArr'"], []
    if users is not None:
        where.append(f"user_id IN ({','.join([ph] * len(users))})" if users else '1=0')
        params.extend(users)
    base_where = ' AND '.join(where)

    date_conditions = {
        'sqlite': {
            'today': "DATE(requested_at) = DATE('now')",
            'this_week': "DATE(requested_at) >= DATE('now', '-' || ((CAST(strftime('%w', 'now') AS INTEGER) + 6) % 7) || ' days')",
            'this_month': "strftime('%Y-%m', requested_at) = strftime('%Y-%m', 'now')",
        },
        'postgres': {
            'today': 'DATE(requested_at) = CURRENT_DATE',
            'this_week': "DATE(requested_at) >= DATE_TRUNC('week', CURRENT_DATE)",
            'this_month': "DATE_TRUNC('month', requested_at) = DATE_TRUNC('month', CURRENT_DATE)",
        },
        'mysql': {
            'today': 'DATE(requested_at) = CURDATE()',
            'this_week': 'DATE(requested_at) >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)',
            'this_month': 'YEAR(requested_at) = YEAR(CURDATE()) AND MONTH(requested_at) = MONTH(CURDATE())',
        },
        'mariadb': {
            'today': 'DATE(requested_at) = CURDATE()',
            'this_week': 'DATE(requested_at) >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)',
            'this_month': 'YEAR(requested_at) = YEAR(CURDATE()) AND MONTH(requested_at) = MONTH(CURDATE())',
        },
    }.get(db.db_type, {})

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM requests WHERE {base_where}", tuple(params))
        stats = {'total': cursor.fetchone()[0]}
        for period in ('today', 'this_week', 'this_month'):
            condition = date_conditions.get(period)
            if not condition:
                stats[period] = stats['total']
                continue
            cursor.execute(
                f"SELECT COUNT(*) FROM requests WHERE {base_where} AND {condition}",
                tuple(params),
            )
            stats[period] = cursor.fetchone()[0]
    return stats


def _status_counts(db, table, statuses):
    """Count a fixed table's status values, preserving zero-valued known states."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT status, COUNT(*) FROM {table} GROUP BY status')
        counts = {str(row[0]): int(row[1]) for row in cursor.fetchall()}
    return {status: counts.get(status, 0) for status in statuses}, sum(counts.values())


@public_api_v1_bp.route('/suggestions', methods=['GET'])
@limiter.limit('120 per minute')
def suggestions():
    pagination = _page_args()
    status = request.args.get('status', 'awaiting_approval')
    media_type = request.args.get('media_type', 'all')
    if not pagination or status not in ('awaiting_approval', 'queued', 'submitting', 'submitted', 'rejected', 'failed', 'blacklisted') or media_type not in ('all', 'movie', 'tv'):
        return jsonify({'error': {'code': 'validation_error', 'message': 'Invalid query parameters.'}}), 400
    search = request.args.get('search', '')
    if len(search) > 100:
        return jsonify({'error': {'code': 'validation_error', 'message': 'Search must be at most 100 characters.'}}), 400
    db = DatabaseManager()
    owner_id = None if g.current_user['role'] == 'admin' else int(g.current_user['id'])
    page, per_page = pagination
    items, total = db.list_suggestions(owner_id, status, search, page, per_page, media_type, _visible_request_user_ids(db))
    return jsonify({'data': items, 'meta': {'page': page, 'per_page': per_page, 'total': total, 'pages': max(1, (total + per_page - 1) // per_page)}}), 200


@public_api_v1_bp.route('/suggestions/actions', methods=['POST'])
@limiter.limit('20 per minute')
def suggestion_actions():
    body = request.get_json(silent=True) or {}
    action, ids = body.get('action'), body.get('ids')
    if action not in ('approve', 'reject', 'blacklist', 'retry', 'request_again') or not isinstance(ids, list) or not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids) or any(type(item) is not int for item in ids):
        return jsonify({'error': {'code': 'validation_error', 'message': 'ids must contain 1 to 100 unique integers.'}}), 400
    remove_blacklist = body.get('remove_blacklist', False)
    if type(remove_blacklist) is not bool or (remove_blacklist and action != 'request_again'):
        return jsonify({'error': {'code': 'validation_error', 'message': 'remove_blacklist is valid only with request_again.'}}), 400
    db = DatabaseManager()
    owner_id = None if g.current_user['role'] == 'admin' else int(g.current_user['id'])
    if action == 'approve':
        changed = db.decide_suggestions(ids, owner_id, int(g.current_user['id']), True)
    elif action == 'reject':
        changed = db.decide_suggestions(ids, owner_id, int(g.current_user['id']), False)
    elif action == 'blacklist':
        changed = db.decide_suggestions(ids, owner_id, int(g.current_user['id']), False, True)
    elif action == 'retry':
        changed = db.retry_suggestions(ids, owner_id)
    else:
        changed = db.request_rejected(ids, owner_id, remove_blacklist)
    return jsonify({'data': {'action': action, 'updated': changed}}), 200


@public_api_v1_bp.route('/requests', methods=['GET'])
@limiter.limit('120 per minute')
def requests_list():
    pagination = _page_args()
    sort = request.args.get('sort', 'date_desc')
    if not pagination or sort not in ('date_desc', 'date_asc', 'title_asc', 'title_desc', 'rating_desc', 'rating_asc'):
        return jsonify({'error': {'code': 'validation_error', 'message': 'Invalid query parameters.'}}), 400
    db = DatabaseManager()
    users = _visible_request_user_ids(db)
    ph = '%s' if db.db_type in ('mysql', 'mariadb', 'postgres') else '?'
    order = {'date_desc': 'r.requested_at DESC', 'date_asc': 'r.requested_at ASC', 'title_asc': 'm.title ASC', 'title_desc': 'm.title DESC', 'rating_desc': 'm.rating DESC', 'rating_asc': 'm.rating ASC'}[sort]
    where, params = ["r.requested_by = 'SuggestArr'"], []
    source = request.args.get('source')
    if source:
        where.append(f'r.source_origin = {ph}')
        params.append(source)
    if users is not None:
        where.append(f"r.user_id IN ({','.join([ph] * len(users))})" if users else '1=0')
        params.extend(users)
    clause = ' AND '.join(where)
    page, per_page = pagination
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM requests r WHERE {clause}', tuple(params))
        total = cursor.fetchone()[0]
        query = f'''SELECT r.tmdb_request_id,r.media_type,m.title,r.source_origin,r.tmdb_source_id,r.requested_at,r.requested_by,r.user_id,m.poster_path,m.rating
                    FROM requests r LEFT JOIN metadata m ON m.media_id=r.tmdb_request_id AND m.media_type=r.media_type
                    WHERE {clause} ORDER BY {order} LIMIT {ph} OFFSET {ph}'''
        cursor.execute(query, tuple(params + [per_page, (page - 1) * per_page]))
        rows = cursor.fetchall()
    data = [{'id': str(row[0]), 'tmdb_id': str(row[0]), 'media_type': row[1], 'title': row[2], 'source_origin': row[3], 'source_media_id': row[4], 'requested_at': row[5], 'requested_by': row[6], 'media_user': {'id': row[7]} if row[7] else None, 'metadata': {'poster_path': row[8], 'rating': row[9]}} for row in rows]
    return jsonify({'data': data, 'meta': {'page': page, 'per_page': per_page, 'total': total, 'pages': max(1, (total + per_page - 1) // per_page)}}), 200


@public_api_v1_bp.route('/requests/stats', methods=['GET'])
@limiter.limit('120 per minute')
def request_stats():
    db = DatabaseManager()
    return jsonify({'data': _request_statistics(db, _visible_request_user_ids(db))}), 200


@public_api_v1_bp.route('/installation/stats', methods=['GET'])
@require_role('admin')
@limiter.limit('60 per minute')
def installation_stats():
    """Return installation-wide, non-sensitive operational counters for admins."""
    db = DatabaseManager()
    jobs = JobRepository().get_all_jobs()
    job_types = ('discover', 'recommendation', 'trakt_recommendations')
    jobs_by_type = {job_type: sum(job.get('job_type') == job_type for job in jobs) for job_type in job_types}

    suggestion_statuses = ('awaiting_approval', 'queued', 'submitting', 'submitted', 'rejected', 'failed', 'blacklisted')
    run_statuses = ('queued', 'running', 'completed', 'failed', 'skipped')
    suggestion_by_status, suggestion_total = _status_counts(db, 'pending_requests', suggestion_statuses)
    run_by_status, run_total = _status_counts(db, 'job_execution_history', run_statuses)
    queue = {
        status: suggestion_by_status[status]
        for status in ('queued', 'submitting', 'submitted', 'failed')
    }
    queue['total_pending'] = queue['queued'] + queue['submitting']
    queue['total'] = suggestion_total

    return jsonify({'data': {
        'requests': _request_statistics(db),
        'jobs': {
            'total': len(jobs),
            'enabled': sum(bool(job.get('enabled')) for job in jobs),
            'disabled': sum(not bool(job.get('enabled')) for job in jobs),
            'system': sum(bool(job.get('is_system')) for job in jobs),
            'by_type': jobs_by_type,
        },
        'runs': {'total': run_total, 'by_status': run_by_status},
        'suggestions': {'total': suggestion_total, 'by_status': suggestion_by_status},
        'queue': queue,
    }}), 200
