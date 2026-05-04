import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock other missing dependencies
sys.modules['api_service.config.logger_manager'] = MagicMock()
sys.modules['api_service.exceptions.api_exceptions'] = MagicMock()
sys.modules['api_service.exceptions.database_exceptions'] = MagicMock()

# Mock Flask and related modules before importing error_handling
mock_flask = MagicMock()
sys.modules['flask'] = mock_flask
sys.modules['flask.jsonify'] = MagicMock()

# Manually mock the request object that the decorators will import from flask
mock_request = MagicMock()
mock_flask.request = mock_request

# Import the decorators
from api_service.utils.error_handling import validate_query_params, validate_request_data

class TestErrorHandlingDecorators(unittest.TestCase):
    def setUp(self):
        # Reset request mock
        mock_request.args = {}
        mock_request.json = None

    def test_validate_query_params_success(self):
        @validate_query_params(['param1', 'param2'])
        def mock_route():
            return "success"

        # Setup request.args
        mock_request.args = {'param1': 'val1', 'param2': 'val2'}

        result = mock_route()
        self.assertEqual(result, "success")

    def test_validate_query_params_missing(self):
        @validate_query_params(['param1', 'param2'])
        def mock_route():
            return "success"

        # Setup request.args (param2 missing)
        mock_request.args = {'param1': 'val1'}

        with self.assertRaises(ValueError) as cm:
            mock_route()
        self.assertEqual(str(cm.exception), "Missing required parameters: param2")

    def test_validate_query_params_empty_list(self):
        """Edge case: ensuring it allows the request when required_params is an empty list."""
        @validate_query_params([])
        def mock_route():
            return "success"

        # Setup request.args (empty)
        mock_request.args = {}

        result = mock_route()
        self.assertEqual(result, "success")

    def test_validate_query_params_empty_value(self):
        @validate_query_params(['param1'])
        def mock_route():
            return "success"

        # Setup request.args (param1 is present but empty)
        mock_request.args = {'param1': ''}

        with self.assertRaises(ValueError) as cm:
            mock_route()
        self.assertEqual(str(cm.exception), "Missing required parameters: param1")

    def test_validate_request_data_success(self):
        @validate_request_data(['field1'])
        def mock_route():
            return "success"

        # Setup request.json
        mock_request.json = {'field1': 'val1'}

        result = mock_route()
        self.assertEqual(result, "success")

    def test_validate_request_data_missing_field(self):
        @validate_request_data(['field1', 'field2'])
        def mock_route():
            return "success"

        # Setup request.json (field2 missing)
        mock_request.json = {'field1': 'val1'}

        with self.assertRaises(ValueError) as cm:
            mock_route()
        self.assertEqual(str(cm.exception), "Missing required fields: field2")

    def test_validate_request_data_no_json(self):
        @validate_request_data(['field1'])
        def mock_route():
            return "success"

        # Setup request.json as None
        mock_request.json = None

        with self.assertRaises(ValueError) as cm:
            mock_route()
        self.assertEqual(str(cm.exception), "Request must include JSON data")

if __name__ == '__main__':
    unittest.main()
