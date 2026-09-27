from io import BytesIO
from unittest.mock import MagicMock, patch

from flask import Flask, g

from api_service.blueprints.watched_history.routes import watched_history_bp


def make_app():
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def inject_user():
        g.current_user = {'id': '7', 'username': 'alice', 'role': 'user'}

    app.register_blueprint(watched_history_bp, url_prefix='/api/watched-history')
    return app


def _db():
    db = MagicMock()
    db.get_user_media_profiles.return_value = [{
        'provider': 'jellyfin', 'external_user_id': 'jf-1', 'external_username': 'alice',
    }]
    db.upsert_media_user_identity.return_value = {'id': 42}
    return db


def _patches(db):
    return (
        patch('api_service.blueprints.watched_history.routes.DatabaseManager', return_value=db),
        patch('api_service.blueprints.watched_history.routes.ConfigService.get_runtime_config', return_value={
            'SELECTED_SERVICE': 'jellyfin',
        }),
    )


def test_list_my_watched_media_is_scoped_to_current_media_profile():
    db = _db()
    db.list_watched_media.return_value = [{'id': 3, 'title': 'Arrival'}]
    p1, p2 = _patches(db)
    with p1, p2:
        response = make_app().test_client().get('/api/watched-history/me')
    assert response.status_code == 200
    assert response.get_json()['items'] == [{'id': 3, 'title': 'Arrival'}]
    db.list_watched_media.assert_called_once_with(42)


def test_csv_import_uses_fixed_columns_and_stores_csv_source():
    db = _db()
    p1, p2 = _patches(db)
    csv_data = b'tmdb_id,media_type,title,year,rating\n27205,movie,Inception,2010,9\n'
    with p1, p2:
        response = make_app().test_client().post(
            '/api/watched-history/me/import',
            data={'file': (BytesIO(csv_data), 'history.csv')},
            content_type='multipart/form-data',
        )
    assert response.status_code == 200
    assert response.get_json()['imported'] == 1
    db.upsert_watched_media.assert_called_once_with(
        42, '27205', 'movie', 'Inception', '2010', '9', source='csv_import',
    )


def test_csv_import_rejects_wrong_headers():
    db = _db()
    p1, p2 = _patches(db)
    with p1, p2:
        response = make_app().test_client().post(
            '/api/watched-history/me/import',
            data={'file': (BytesIO(b'id,title\n1,Arrival\n'), 'history.csv')},
            content_type='multipart/form-data',
        )
    assert response.status_code == 400
    assert 'headers' in response.get_json()['message']
