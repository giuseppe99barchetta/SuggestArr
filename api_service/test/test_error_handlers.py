"""
Tests for utils/error_handlers.py and utils/error_handling.py.

Covers:
  error_handlers.py:
    - handle_api_errors decorator: ValueError→400, FileNotFoundError→404, generic→500, success
    - validate_required_fields: happy path, missing fields, empty required list
    - success_response: with/without data, status code, response shape
    - error_response: default 400, custom status codes, response shape

  error_handling.py:
    - handle_api_errors decorator: all exception branches (ValueError, connection
      errors, APIClientError, DatabaseError, PermissionError, FileNotFoundError,
      TimeoutError, generic)
    - validate_request_data decorator: no JSON, missing fields, success
    - validate_query_params decorator: missing params, success
    - log_api_call decorator: pass-through, re-raise on exception
    - success_response: with/without data, outside-app-context fallback, custom message
    - paginated_response: metadata correctness, last-page flags

Strategy
--------
All tests that need a Flask request context use a minimal app with a test
client.  No DB, no auth, no external I/O.
"""
import unittest
import logging
from flask import Flask, jsonify

logging.disable(logging.CRITICAL)


# ===========================================================================
# error_handlers.py
# ===========================================================================

class TestErrorHandlersDecoratorSimple(unittest.TestCase):
    """Tests for the handle_api_errors decorator in utils/error_handlers.py."""

    def _make_app(self, view_func):
        from api_service.utils.error_handlers import handle_api_errors
        app = Flask(__name__)

        @app.route('/test')
        @handle_api_errors
        def test_view():
            return view_func()

        return app

    def test_success_passes_through(self):
        app = self._make_app(lambda: (jsonify({'ok': True}), 200))
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['ok'])

    def test_value_error_returns_400(self):
        def raise_ve():
            raise ValueError("bad input here")

        app = self._make_app(raise_ve)
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('message', data)
        self.assertEqual(data['type'], 'error')
        self.assertIn('bad input here', data['message'])

    def test_file_not_found_returns_404(self):
        def raise_fnf():
            raise FileNotFoundError("file gone")

        app = self._make_app(raise_fnf)
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertEqual(data['type'], 'error')
        self.assertIn('file gone', data['message'])

    def test_generic_exception_returns_500(self):
        def raise_exc():
            raise RuntimeError("unexpected crash")

        app = self._make_app(raise_exc)
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertIn('message', data)
        self.assertEqual(data['type'], 'error')

    def test_decorator_preserves_function_name(self):
        from api_service.utils.error_handlers import handle_api_errors

        @handle_api_errors
        def my_named_func():
            return "ok"

        self.assertEqual(my_named_func.__name__, 'my_named_func')


class TestValidateRequiredFieldsSimple(unittest.TestCase):

    def test_all_fields_present_no_error(self):
        from api_service.utils.error_handlers import validate_required_fields
        validate_required_fields(['a', 'b'], {'a': 1, 'b': 2})  # must not raise

    def test_missing_single_field_raises_value_error(self):
        from api_service.utils.error_handlers import validate_required_fields
        with self.assertRaises(ValueError) as ctx:
            validate_required_fields(['a', 'b'], {'a': 1})
        self.assertIn('Missing required fields', str(ctx.exception))
        self.assertIn('b', str(ctx.exception))

    def test_missing_multiple_fields_raises_value_error(self):
        from api_service.utils.error_handlers import validate_required_fields
        with self.assertRaises(ValueError) as ctx:
            validate_required_fields(['x', 'y', 'z'], {})
        msg = str(ctx.exception)
        self.assertIn('x', msg)
        self.assertIn('y', msg)
        self.assertIn('z', msg)

    def test_empty_required_fields_never_raises(self):
        from api_service.utils.error_handlers import validate_required_fields
        validate_required_fields([], {'anything': 'here'})  # must not raise
        validate_required_fields([], {})                    # must not raise

    def test_extra_fields_in_data_are_ignored(self):
        from api_service.utils.error_handlers import validate_required_fields
        validate_required_fields(['a'], {'a': 1, 'extra': 99})  # must not raise


class TestSuccessAndErrorResponseSimple(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)

    def test_success_response_status_200(self):
        from api_service.utils.error_handlers import success_response
        with self.app.app_context():
            resp, code = success_response("done")
            self.assertEqual(code, 200)

    def test_success_response_type_field(self):
        from api_service.utils.error_handlers import success_response
        with self.app.app_context():
            resp, _ = success_response("done")
            self.assertEqual(resp.get_json()['type'], 'success')

    def test_success_response_message_preserved(self):
        from api_service.utils.error_handlers import success_response
        with self.app.app_context():
            resp, _ = success_response("operation complete")
            self.assertEqual(resp.get_json()['message'], 'operation complete')

    def test_success_response_with_data_includes_data_key(self):
        from api_service.utils.error_handlers import success_response
        with self.app.app_context():
            resp, _ = success_response("ok", data={'key': 'value'})
            data = resp.get_json()
            self.assertIn('data', data)
            self.assertEqual(data['data']['key'], 'value')

    def test_success_response_without_data_omits_data_key(self):
        from api_service.utils.error_handlers import success_response
        with self.app.app_context():
            resp, _ = success_response("ok")
            self.assertNotIn('data', resp.get_json())

    def test_error_response_default_400(self):
        from api_service.utils.error_handlers import error_response
        with self.app.app_context():
            resp, code = error_response("something went wrong")
            self.assertEqual(code, 400)
            data = resp.get_json()
            self.assertEqual(data['type'], 'error')
            self.assertEqual(data['message'], 'something went wrong')

    def test_error_response_custom_status(self):
        from api_service.utils.error_handlers import error_response
        with self.app.app_context():
            _, code = error_response("forbidden", status_code=403)
            self.assertEqual(code, 403)

    def test_error_response_custom_500(self):
        from api_service.utils.error_handlers import error_response
        with self.app.app_context():
            _, code = error_response("server broke", status_code=500)
            self.assertEqual(code, 500)


# ===========================================================================
# error_handling.py
# ===========================================================================

class TestErrorHandlingDecorator(unittest.TestCase):
    """Tests for handle_api_errors in utils/error_handling.py."""

    def _make_app(self, view_func):
        from api_service.utils.error_handling import handle_api_errors
        app = Flask(__name__)

        @app.route('/test')
        @handle_api_errors
        def test_view():
            return view_func()

        return app

    def test_success_passes_through(self):
        app = self._make_app(lambda: (jsonify({'ok': True}), 200))
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 200)

    def test_value_error_returns_400(self):
        app = self._make_app(lambda: (_ for _ in ()).throw(ValueError("bad value")))

        # Simpler approach: define a function that raises
        from api_service.utils.error_handling import handle_api_errors
        app2 = Flask(__name__)

        @app2.route('/t')
        @handle_api_errors
        def t():
            raise ValueError("bad value")

        resp = app2.test_client().get('/t')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data['type'], 'validation_error')
        self.assertIn('endpoint', data)
        self.assertIn('bad value', data['message'])

    def test_plex_connection_error_returns_503(self):
        from api_service.utils.error_handling import handle_api_errors
        from api_service.exceptions.api_exceptions import PlexConnectionError
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise PlexConnectionError("timed out")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 503)
        data = resp.get_json()
        self.assertEqual(data['type'], 'connection_error')
        self.assertEqual(data['service'], 'Plex')

    def test_jellyfin_connection_error_returns_503(self):
        from api_service.utils.error_handling import handle_api_errors
        from api_service.exceptions.api_exceptions import JellyfinConnectionError
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise JellyfinConnectionError("refused")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 503)
        data = resp.get_json()
        self.assertEqual(data['service'], 'Jellyfin')

    def test_tmdb_connection_error_returns_503(self):
        from api_service.utils.error_handling import handle_api_errors
        from api_service.exceptions.api_exceptions import TMDBConnectionError
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise TMDBConnectionError("no route")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.get_json()['service'], 'TMDB')

    def test_seer_connection_error_returns_503(self):
        from api_service.utils.error_handling import handle_api_errors
        from api_service.exceptions.api_exceptions import SeerConnectionError
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise SeerConnectionError("unavailable")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.get_json()['service'], 'Seer')

    def test_api_client_error_returns_500(self):
        from api_service.utils.error_handling import handle_api_errors
        from api_service.exceptions.api_exceptions import APIClientError
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise APIClientError("api failure", service_name="MyService")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertEqual(data['type'], 'api_error')
        self.assertEqual(data['service'], 'MyService')

    def test_database_error_returns_500(self):
        from api_service.utils.error_handling import handle_api_errors
        from api_service.exceptions.database_exceptions import DatabaseError
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise DatabaseError("constraint violated", db_type='sqlite')

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertEqual(data['type'], 'database_error')
        self.assertEqual(data['database'], 'sqlite')

    def test_permission_error_returns_403(self):
        from api_service.utils.error_handling import handle_api_errors
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise PermissionError("not allowed")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json()['type'], 'permission_error')

    def test_file_not_found_returns_404(self):
        from api_service.utils.error_handling import handle_api_errors
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise FileNotFoundError("missing resource")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()['type'], 'not_found_error')

    def test_timeout_error_returns_504(self):
        from api_service.utils.error_handling import handle_api_errors
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise TimeoutError("took too long")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 504)
        self.assertEqual(resp.get_json()['type'], 'timeout_error')

    def test_generic_exception_returns_500(self):
        from api_service.utils.error_handling import handle_api_errors
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def t():
            raise RuntimeError("something unexpected")

        resp = app.test_client().get('/t')
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json()['type'], 'internal_error')

    def test_decorator_preserves_function_name(self):
        from api_service.utils.error_handling import handle_api_errors

        @handle_api_errors
        def my_handler():
            pass

        self.assertEqual(my_handler.__name__, 'my_handler')

    def test_endpoint_name_in_error_response(self):
        from api_service.utils.error_handling import handle_api_errors
        app = Flask(__name__)

        @app.route('/t')
        @handle_api_errors
        def my_endpoint():
            raise ValueError("oops")

        resp = app.test_client().get('/t')
        data = resp.get_json()
        self.assertEqual(data.get('endpoint'), 'my_endpoint')


class TestValidateRequestData(unittest.TestCase):

    def _make_app(self, required_fields):
        from api_service.utils.error_handling import validate_request_data, handle_api_errors
        app = Flask(__name__)

        @app.route('/test', methods=['POST'])
        @handle_api_errors
        @validate_request_data(required_fields)
        def test_view():
            return jsonify({'ok': True}), 200

        return app

    def test_all_required_fields_present(self):
        app = self._make_app(['field1', 'field2'])
        resp = app.test_client().post('/test',
                                      json={'field1': 'v1', 'field2': 'v2'})
        self.assertEqual(resp.status_code, 200)

    def test_missing_field_raises_400(self):
        app = self._make_app(['field1', 'field2'])
        resp = app.test_client().post('/test', json={'field1': 'v1'})
        self.assertEqual(resp.status_code, 400)

    def test_empty_json_object_raises_400(self):
        # An empty JSON object {} is falsy in Python → `if not request.json` branch fires
        app = self._make_app(['field1'])
        resp = app.test_client().post('/test', json={})
        self.assertEqual(resp.status_code, 400)

    def test_empty_value_treated_as_missing(self):
        app = self._make_app(['field1'])
        resp = app.test_client().post('/test', json={'field1': ''})
        self.assertEqual(resp.status_code, 400)

    def test_no_required_fields_always_passes(self):
        # Must send a non-empty body; the decorator checks `if not request.json`
        # so an empty {} would also trigger the "no JSON data" branch.
        app = self._make_app([])
        resp = app.test_client().post('/test', json={'anything': 'here'})
        self.assertEqual(resp.status_code, 200)


class TestValidateQueryParams(unittest.TestCase):

    def _make_app(self, required_params):
        from api_service.utils.error_handling import validate_query_params, handle_api_errors
        app = Flask(__name__)

        @app.route('/test')
        @handle_api_errors
        @validate_query_params(required_params)
        def test_view():
            return jsonify({'ok': True}), 200

        return app

    def test_all_params_present(self):
        app = self._make_app(['q', 'page'])
        resp = app.test_client().get('/test?q=hello&page=1')
        self.assertEqual(resp.status_code, 200)

    def test_missing_param_raises_400(self):
        app = self._make_app(['q', 'page'])
        resp = app.test_client().get('/test?q=hello')
        self.assertEqual(resp.status_code, 400)

    def test_no_required_params_always_passes(self):
        app = self._make_app([])
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 200)

    def test_empty_param_value_treated_as_missing(self):
        app = self._make_app(['q'])
        resp = app.test_client().get('/test?q=')
        self.assertEqual(resp.status_code, 400)


class TestLogApiCall(unittest.TestCase):

    def test_pass_through_on_success(self):
        # The decorator accesses request.json in a debug f-string, so send a
        # proper JSON request to avoid UnsupportedMediaType from newer Werkzeug.
        from api_service.utils.error_handling import log_api_call
        app = Flask(__name__)

        @app.route('/t', methods=['POST'])
        @log_api_call
        def t():
            return jsonify({'logged': True}), 200

        resp = app.test_client().post('/t', json={'ping': 'pong'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['logged'])

    def test_reraises_exception(self):
        from api_service.utils.error_handling import log_api_call
        app = Flask(__name__)

        @app.route('/t', methods=['POST'])
        @log_api_call
        def t():
            raise ValueError("rethrown")

        # Flask returns 500 for unhandled exceptions (log_api_call re-raises)
        resp = app.test_client().post('/t', json={'x': 1})
        self.assertEqual(resp.status_code, 500)

    def test_decorator_preserves_name(self):
        from api_service.utils.error_handling import log_api_call

        @log_api_call
        def my_func():
            pass

        self.assertEqual(my_func.__name__, 'my_func')


class TestSuccessResponseErrorHandling(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)

    def test_success_response_default_message(self):
        from api_service.utils.error_handling import success_response
        with self.app.app_context():
            resp, code = success_response()
            self.assertEqual(code, 200)
            data = resp.get_json()
            self.assertIn('message', data)
            self.assertEqual(data['type'], 'success')

    def test_success_response_with_data(self):
        from api_service.utils.error_handling import success_response
        with self.app.app_context():
            resp, code = success_response(data={'items': [1, 2, 3]})
            self.assertEqual(code, 200)
            data = resp.get_json()
            self.assertIn('data', data)
            self.assertEqual(data['data']['items'], [1, 2, 3])

    def test_success_response_without_data_omits_key(self):
        from api_service.utils.error_handling import success_response
        with self.app.app_context():
            resp, _ = success_response()
            self.assertNotIn('data', resp.get_json())

    def test_success_response_custom_message(self):
        from api_service.utils.error_handling import success_response
        with self.app.app_context():
            resp, _ = success_response(message="custom message")
            self.assertEqual(resp.get_json()['message'], 'custom message')

    def test_success_response_outside_app_context_returns_dict(self):
        from api_service.utils.error_handling import success_response
        # No app_context: should fall back to returning a plain dict
        result, code = success_response(data={'x': 1})
        self.assertEqual(code, 200)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['type'], 'success')


class TestPaginatedResponse(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)

    def test_first_page_metadata(self):
        from api_service.utils.error_handling import paginated_response
        with self.app.app_context():
            resp, code = paginated_response([1, 2, 3], page=1, per_page=3, total=10)
            self.assertEqual(code, 200)
            data = resp.get_json()
            pagination = data['pagination']
            self.assertEqual(pagination['page'], 1)
            self.assertEqual(pagination['per_page'], 3)
            self.assertEqual(pagination['total'], 10)
            self.assertTrue(pagination['has_next'])
            self.assertFalse(pagination['has_prev'])

    def test_last_page_no_next(self):
        from api_service.utils.error_handling import paginated_response
        with self.app.app_context():
            resp, _ = paginated_response([10], page=4, per_page=3, total=10)
            pagination = resp.get_json()['pagination']
            self.assertFalse(pagination['has_next'])
            self.assertTrue(pagination['has_prev'])

    def test_total_pages_calculation(self):
        from api_service.utils.error_handling import paginated_response
        with self.app.app_context():
            resp, _ = paginated_response([], page=1, per_page=5, total=11)
            pagination = resp.get_json()['pagination']
            self.assertEqual(pagination['total_pages'], 3)  # ceil(11/5)

    def test_items_included_in_data(self):
        from api_service.utils.error_handling import paginated_response
        with self.app.app_context():
            items = ['a', 'b']
            resp, _ = paginated_response(items, page=1, per_page=2, total=2)
            data = resp.get_json()
            self.assertEqual(data['data'], items)

    def test_single_page_no_next_no_prev(self):
        from api_service.utils.error_handling import paginated_response
        with self.app.app_context():
            resp, _ = paginated_response([1], page=1, per_page=10, total=1)
            pagination = resp.get_json()['pagination']
            self.assertFalse(pagination['has_next'])
            self.assertFalse(pagination['has_prev'])


if __name__ == '__main__':
    unittest.main()
