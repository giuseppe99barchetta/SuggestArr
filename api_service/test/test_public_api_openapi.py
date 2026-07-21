from pathlib import Path

import yaml
from flask import Flask

from api_service.api.v1.blueprint import public_api_v1_bp


def test_openapi_documents_every_public_route_and_has_unique_operation_ids():
    spec = yaml.safe_load(
        (Path(__file__).parents[1] / 'openapi' / 'public-api-v1.yaml').read_text(encoding='utf-8')
    )
    app = Flask(__name__)
    app.register_blueprint(public_api_v1_bp, url_prefix='/api/v1')
    documented = {(path, method.upper()) for path, item in spec['paths'].items() for method in item if method in {'get', 'post', 'put', 'patch', 'delete'}}
    routes = {(rule.rule.replace('<int:', '{').replace('>', '}'), method)
              for rule in app.url_map.iter_rules() if rule.rule.startswith('/api/v1/')
              for method in rule.methods - {'HEAD', 'OPTIONS'}}
    assert routes == documented
    operation_ids = [operation['operationId'] for item in spec['paths'].values() for operation in item.values()]
    assert len(operation_ids) == len(set(operation_ids))


def test_openapi_public_operations_explicitly_disable_security():
    spec = yaml.safe_load(
        (Path(__file__).parents[1] / 'openapi' / 'public-api-v1.yaml').read_text(encoding='utf-8')
    )
    for path in ('/api/v1/status', '/api/v1/openapi.json', '/api/v1/openapi.yaml'):
        assert spec['paths'][path]['get']['security'] == []
