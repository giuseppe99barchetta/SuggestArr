"""
Tests for the new error handling system.
"""
import unittest
from unittest.mock import Mock, patch
import json

# Add path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_service.utils.error_handling import (
    handle_api_errors, validate_request_data, success_response,
    paginated_response
)
from api_service.exceptions.api_exceptions import PlexConnectionError
from api_service.exceptions.database_exceptions import DatabaseError


class TestErrorHandling(unittest.TestCase):
    """Test error handling decorators and utilities."""
    
    def setUp(self):
        """Set up test Flask app context."""
        self.mock_request = Mock()
        
    @patch('api_service.utils.error_handling.request')
    def test_validate_request_data_success(self, mock_request):
        """Test successful request data validation."""
        mock_request.json = {'PLEX_API_URL': 'http://test', 'PLEX_TOKEN': 'token'}
        
        @validate_request_data(['PLEX_API_URL', 'PLEX_TOKEN'])
        def test_endpoint():
            return 'success'
        
        result = test_endpoint()
        self.assertEqual(result, 'success')
    
    @patch('api_service.utils.error_handling.request')
    def test_validate_request_data_missing_fields(self, mock_request):
        """Test request validation with missing fields."""
        mock_request.json = {'PLEX_API_URL': 'http://test'}
        
        @validate_request_data(['PLEX_API_URL', 'PLEX_TOKEN'])
        def test_endpoint():
            return 'success'
        
        with self.assertRaises(ValueError) as context:
            test_endpoint()
        
        self.assertIn('Missing required fields', str(context.exception))
    
    @patch('api_service.utils.error_handling.request')
    def test_validate_request_data_no_json(self, mock_request):
        """Test request validation with no JSON data."""
        mock_request.json = None
        
        @validate_request_data(['test_field'])
        def test_endpoint():
            return 'success'
        
        with self.assertRaises(ValueError) as context:
            test_endpoint()
        
        self.assertIn('Request must include JSON data', str(context.exception))
    
    def test_success_response_basic(self):
        """Test basic success response creation."""
        response_data, status_code = success_response()
        
        # Test both dict and Flask response formats
        if hasattr(response_data, 'data'):
            # Flask response
            response_json = json.loads(response_data.data)
        else:
            # Dict response (for testing)
            response_json = response_data
            
        self.assertEqual(status_code, 200)
        self.assertEqual(response_json['type'], 'success')
        self.assertEqual(response_json['message'], 'Operation successful')
        self.assertNotIn('data', response_json)
    
    def test_success_response_with_data(self):
        """Test success response with data."""
        test_data = {'id': 1, 'name': 'test'}
        response_data, status_code = success_response(test_data, 'Custom message')
        
        response_json = json.loads(response_data.data)
        self.assertEqual(status_code, 200)
        self.assertEqual(response_json['type'], 'success')
        self.assertEqual(response_json['message'], 'Custom message')
        self.assertEqual(response_json['data'], test_data)
    
    def test_paginated_response(self):
        """Test paginated response creation."""
        items = [{'id': 1}, {'id': 2}]
        response_data, status_code = paginated_response(items, page=1, per_page=10, total=2)
        
        response_json = json.loads(response_data.data)
        self.assertEqual(status_code, 200)
        self.assertEqual(response_json['data'], items)
        self.assertEqual(response_json['pagination']['page'], 1)
        self.assertEqual(response_json['pagination']['per_page'], 10)
        self.assertEqual(response_json['pagination']['total'], 2)
        self.assertEqual(response_json['pagination']['total_pages'], 1)
        self.assertFalse(response_json['pagination']['has_next'])
        self.assertFalse(response_json['pagination']['has_prev'])
    
    @patch('api_service.utils.error_handling.request')
    def test_handle_api_errors_validation_error(self, mock_request):
        """Test handling of ValueError."""
        mock_request.remote_addr = '127.0.0.1'
        
        @handle_api_errors
        def test_endpoint():
            raise ValueError('Invalid input')
        
        response_data, status_code = test_endpoint()
        response_json = json.loads(response_data.data)
        
        self.assertEqual(status_code, 400)
        self.assertEqual(response_json['type'], 'validation_error')
        self.assertIn('Invalid input', response_json['message'])
    
    @patch('api_service.utils.error_handling.request')
    def test_handle_api_errors_connection_error(self, mock_request):
        """Test handling of connection errors."""
        mock_request.remote_addr = '127.0.0.1'
        
        @handle_api_errors
        def test_endpoint():
            raise PlexConnectionError('Connection failed')
        
        response_data, status_code = test_endpoint()
        response_json = json.loads(response_data.data)
        
        self.assertEqual(status_code, 503)
        self.assertEqual(response_json['type'], 'connection_error')
        self.assertEqual(response_json['service'], 'Plex')
        self.assertIn('Connection failed', response_json['message'])
    
    @patch('api_service.utils.error_handling.request')
    def test_handle_api_errors_database_error(self, mock_request):
        """Test handling of database errors."""
        mock_request.remote_addr = '127.0.0.1'
        
        @handle_api_errors
        def test_endpoint():
            raise DatabaseError('sqlite', 'Table not found')
        
        response_data, status_code = test_endpoint()
        response_json = json.loads(response_data.data)
        
        self.assertEqual(status_code, 500)
        self.assertEqual(response_json['type'], 'database_error')
        self.assertEqual(response_json['database'], 'sqlite')
        self.assertIn('Database operation failed', response_json['message'])
    
    @patch('api_service.utils.error_handling.request')
    def test_handle_api_errors_success(self, mock_request):
        """Test successful execution with error handler."""
        mock_request.remote_addr = '127.0.0.1'
        
        @handle_api_errors
        def test_endpoint():
            return 'success_result'
        
        result = test_endpoint()
        self.assertEqual(result, 'success_result')


if __name__ == '__main__':
    unittest.main()