# utils/error_handlers.py

from functools import wraps
from flask import jsonify

def handle_api_errors(f):
    """
    A decorator to handle errors for API routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as ve:
            return jsonify({'message': str(ve), 'type': 'error'}), 400
        except FileNotFoundError as fnfe:
            return jsonify({'message': str(fnfe), 'type': 'error'}), 404
        except Exception as e:
            return jsonify({'message': f'Unexpected error: {str(e)}', 'type': 'error'}), 500
    return decorated_function

def validate_required_fields(required_fields, data):
    """
    Ensure that the required fields are present in the provided data.
    """
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

def success_response(message, data=None):
    """
    Create a successful response message.
    """
    response = {'message': message, 'type': 'success'}
    if data:
        response['data'] = data
    return jsonify(response), 200

def error_response(message, status_code=400):
    """
    Create an error response message.
    """
    return jsonify({'message': message, 'type': 'error'}), status_code
