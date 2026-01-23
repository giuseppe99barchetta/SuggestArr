"""
Centralized error handling decorators and utilities for Flask routes.
"""
import functools
import traceback
from flask import jsonify, request
from typing import Callable, Any

from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.api_exceptions import (
    APIClientError, PlexConnectionError, JellyfinConnectionError,
    TMDBConnectionError, SeerConnectionError
)
from api_service.exceptions.database_exceptions import DatabaseError


logger = LoggerManager.get_logger("ErrorHandler")


def handle_api_errors(f: Callable) -> Callable:
    """
    Decorator for consistent API error handling.
    
    Provides standardized error responses and logging for API endpoints.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs) -> Any:
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {f.__name__}: {str(e)}")
            return jsonify({
                'message': f'Invalid input: {str(e)}',
                'type': 'validation_error',
                'endpoint': f.__name__
            }), 400
            
        except (PlexConnectionError, JellyfinConnectionError, 
                TMDBConnectionError, SeerConnectionError) as e:
            logger.error(f"Connection error in {f.__name__}: {str(e)}")
            return jsonify({
                'message': f'Service connection failed: {str(e)}',
                'type': 'connection_error',
                'service': e.service_name,
                'endpoint': f.__name__
            }), 503
            
        except APIClientError as e:
            logger.error(f"API client error in {f.__name__}: {str(e)}")
            return jsonify({
                'message': f'API error: {str(e)}',
                'type': 'api_error',
                'service': e.service_name,
                'endpoint': f.__name__
            }), 500
            
        except DatabaseError as e:
            logger.error(f"Database error in {f.__name__}: {str(e)}")
            return jsonify({
                'message': 'Database operation failed',
                'type': 'database_error',
                'database': e.db_type,
                'endpoint': f.__name__
            }), 500
            
        except PermissionError as e:
            logger.warning(f"Permission error in {f.__name__}: {str(e)}")
            return jsonify({
                'message': 'Access denied',
                'type': 'permission_error',
                'endpoint': f.__name__
            }), 403
            
        except FileNotFoundError as e:
            logger.warning(f"Resource not found in {f.__name__}: {str(e)}")
            return jsonify({
                'message': 'Requested resource not found',
                'type': 'not_found_error',
                'endpoint': f.__name__
            }), 404
            
        except TimeoutError as e:
            logger.error(f"Timeout error in {f.__name__}: {str(e)}")
            return jsonify({
                'message': 'Request timeout',
                'type': 'timeout_error',
                'endpoint': f.__name__
            }), 504
            
        except Exception as e:
            # Log full traceback for unexpected errors
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}\n{traceback.format_exc()}")
            return jsonify({
                'message': 'Internal server error',
                'type': 'internal_error',
                'endpoint': f.__name__
            }), 500
    
    return decorated_function


def validate_request_data(required_fields: list) -> Callable:
    """
    Decorator for validating required JSON fields in request data.
    
    Args:
        required_fields: List of field names that must be present in request.json
        
    Returns:
        Decorator function that validates request data
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs) -> Any:
            if not request.json:
                raise ValueError("Request must include JSON data")
                
            missing_fields = [field for field in required_fields 
                           if field not in request.json or not request.json[field]]
            
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def validate_query_params(required_params: list) -> Callable:
    """
    Decorator for validating required query parameters.
    
    Args:
        required_params: List of parameter names that must be present in request.args
        
    Returns:
        Decorator function that validates query parameters
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs) -> Any:
            missing_params = [param for param in required_params 
                           if param not in request.args or not request.args[param]]
            
            if missing_params:
                raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_api_call(f: Callable) -> Callable:
    """
    Decorator for logging API calls with request details.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs) -> Any:
        logger.info(f"API call to {f.__name__} from {request.remote_addr}")
        logger.debug(f"Request data: {request.json if request.json else dict(request.args)}")
        
        try:
            result = f(*args, **kwargs)
            logger.info(f"API call to {f.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"API call to {f.__name__} failed: {str(e)}")
            raise
            
    return decorated_function


def success_response(data: Any = None, message: str = "Operation successful") -> tuple:
    """
    Create a standardized success response.
    
    Args:
        data: Optional data to include in response
        message: Success message
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    response = {
        'message': message,
        'type': 'success'
    }
    
    if data is not None:
        response['data'] = data
        
    # Return dict instead of jsonify for testing contexts
    try:
        return jsonify(response), 200
    except RuntimeError:
        # Working outside application context (testing)
        return response, 200


def paginated_response(items: list, page: int, per_page: int, total: int) -> tuple:
    """
    Create a standardized paginated response.
    
    Args:
        items: List of items for current page
        page: Current page number
        per_page: Items per page
        total: Total number of items
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    total_pages = (total + per_page - 1) // per_page
    
    response = {
        'message': f'Retrieved {len(items)} items',
        'type': 'success',
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        },
        'data': items
    }
    
    return jsonify(response), 200