from pathlib import Path
from unittest.mock import patch

import yaml
from flask import Flask, g

from api_service.api.v1.blueprint import public_api_v1_bp


def _client():
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def authenticate_test_request():
        g.current_user = {'id': 1, 'username': 'tester', 'role': 'admin'}
        g.auth_method = 'test'
        g.api_key_id = None
        g.api_key_name = None

    app.register_blueprint(public_api_v1_bp, url_prefix='/api/v1')
    return app.test_client()


def test_suggestion_all_status_reaches_repository():
    class SuggestionsDatabase:
        db_type = 'sqlite'

        def __init__(self):
            self.status = None

        def list_suggestions(self, _owner_id, status, *_args):
            self.status = status
            return [], 0

    database = SuggestionsDatabase()
    with patch('api_service.api.v1.blueprint.DatabaseManager', return_value=database):
        response = _client().get('/api/v1/suggestions?status=all')

    assert response.status_code == 200
    assert database.status == 'all'


def test_job_payload_includes_all_safe_job_configuration_fields():
    job = {
        'id': 1, 'name': 'Daily recommendations', 'job_type': 'recommendation', 'enabled': True,
        'media_type': 'both', 'filters': {'vote_average_gte': 7}, 'schedule_type': 'preset',
        'schedule_value': 'daily', 'max_results': 20, 'user_ids': ['media-user'], 'is_system': True,
        'owner_id': 1, 'pause_if_pending_requests': True, 'prevent_suggestions_if_unwatched': False,
        'unwatched_suggestion_days': 7, 'delivery_mode': 'inherit',
        'seer_identity_mode': 'technical_user', 'request_profiles': {'movie': {'serverId': 1}},
        'approval_pause_mode': 'inherit', 'created_at': None, 'updated_at': None,
    }

    class JobsRepository:
        def get_all_jobs(self):
            return [job]

    with patch('api_service.api.v1.blueprint.JobRepository', return_value=JobsRepository()):
        response = _client().get('/api/v1/jobs')

    assert response.status_code == 200
    assert response.get_json()['data'][0] == job


def test_openapi_documents_public_filters_and_full_resource_schemas():
    spec = yaml.safe_load(
        (Path(__file__).parents[1] / 'openapi' / 'public-api-v1.yaml').read_text(encoding='utf-8')
    )

    suggestion_status = next(
        parameter for parameter in spec['paths']['/api/v1/suggestions']['get']['parameters']
        if parameter['name'] == 'status'
    )
    assert 'all' in suggestion_status['schema']['enum']
    assert {'filters', 'request_profiles', 'approval_pause_mode'} <= set(spec['components']['schemas']['Job']['properties'])
    assert {'request_profile', 'media_user_id', 'user_name'} <= set(spec['components']['schemas']['Suggestion']['properties'])
    assert {'source_origin', 'source_media_id', 'media_user', 'metadata'} <= set(spec['components']['schemas']['Request']['properties'])
