from api_service.app import app


def test_docs_uses_self_hosted_swagger_assets_and_local_openapi_document():
    response = app.test_client().get('/docs')

    assert response.status_code == 200
    assert response.content_type == 'text/html; charset=utf-8'
    body = response.get_data(as_text=True)
    assert '"/api/v1/openapi.json"' in body
    assert 'href="/swagger-ui/swagger-ui.css"' in body
    assert 'src="/swagger-ui/swagger-ui-bundle.js"' in body
    assert 'src="/swagger-ui/swagger-ui-standalone-preset.js"' in body
    assert 'href="/swagger-ui/custom/swagger-custom.css"' in body
    assert 'src="/swagger-ui/custom/swagger-init.js"' in body
    assert 'src="/swagger-ui/logo"' in body
    assert 'id="swagger-ui"' in body
    assert '<noscript>' in body
    assert 'OpenAPI specification' in body
    assert '"layout": "BaseLayout"' in body
    assert '"deepLinking": true' in body
    assert '"displayRequestDuration": true' in body
    assert '"persistAuthorization": false' in body
    assert '"tryItOutEnabled": true' in body
    assert 'http://' not in body
    assert 'https://' not in body


def test_docs_custom_assets_and_openapi_document_are_available():
    client = app.test_client()

    init = client.get('/swagger-ui/custom/swagger-init.js')
    assert init.status_code == 200
    assert 'validatorUrl: null' in init.get_data(as_text=True)

    assert client.get('/swagger-ui/custom/swagger-custom.css').status_code == 200
    assert client.get('/swagger-ui/logo').status_code == 200
    assert client.get('/api/v1/openapi.json').status_code == 200
