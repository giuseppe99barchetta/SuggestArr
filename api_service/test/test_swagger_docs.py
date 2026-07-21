from api_service.app import app


def test_docs_uses_self_hosted_swagger_assets_and_local_openapi_document():
    response = app.test_client().get('/docs')

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'SwaggerUIBundle' in body
    assert '"/api/v1/openapi.json"' in body
    assert 'href="/swagger-ui/swagger-ui.css"' in body
    assert 'src="/swagger-ui/swagger-ui-bundle.js"' in body
    assert 'src="/swagger-ui/swagger-ui-standalone-preset.js"' in body
    assert 'validatorUrl: null' in body
    assert 'http://' not in body
    assert 'https://' not in body
