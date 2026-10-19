"""
OMDb API blueprint — provides an endpoint to test the OMDb API key.
"""

import asyncio
import aiohttp
from flask import Blueprint, request, jsonify
from api_service.config.logger_manager import LoggerManager

omdb_bp = Blueprint('omdb', __name__)
logger = LoggerManager.get_logger("OMDbRoute")

OMDB_BASE_URL = "https://www.omdbapi.com/"

# A stable test title to validate the key (Interstellar)
_TEST_IMDB_ID = "tt0816692"

_INVALID_KEY_MESSAGE = (
    'Invalid OMDb API key. If you just registered, make sure you activated it '
    'using the link in the email sent by OMDb, and paste only the key '
    '(not the whole example URL).'
)


def _error_message_from_payload(payload, status):
    """
    Build a user-facing error message from an OMDb JSON payload.

    :param payload: Parsed JSON body returned by OMDb (may be None or non-dict).
    :param status: HTTP status code of the OMDb response.
    :return: A human-readable error message.
    """
    error = payload.get('Error') if isinstance(payload, dict) else None
    if error == 'Invalid API key!':
        return _INVALID_KEY_MESSAGE
    if error:
        return f'OMDb error: {error}'
    return f'OMDb API returned status {status}'


async def _check_omdb_key(api_key):
    """
    Query OMDb with a known title to validate the given API key.

    :param api_key: The OMDb API key to validate (already stripped).
    :return: Dict with 'status' ('success' or 'error') and 'message'.
    """
    params = {'i': _TEST_IMDB_ID, 'apikey': api_key}
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(OMDB_BASE_URL, params=params) as response:
                # OMDb answers invalid/unactivated keys and exhausted quotas with
                # 401 plus a JSON body describing the error, so always read it.
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    payload = None

                if response.status == 200 and isinstance(payload, dict) \
                        and payload.get('Response') == 'True':
                    return {'status': 'success',
                            'message': 'OMDb API key validated successfully!'}

                message = _error_message_from_payload(payload, response.status)
                logger.warning("OMDb key test failed: HTTP %d - %s", response.status, message)
                return {'status': 'error', 'message': message}
    except asyncio.TimeoutError:
        logger.error("OMDb connection timed out")
        return {'status': 'error', 'message': 'Connection to OMDb API timed out'}
    except aiohttp.ClientError as e:
        logger.error("OMDb connection error: %s", e)
        return {'status': 'error',
                'message': 'Failed to connect to OMDb API. Check that SuggestArr can reach omdbapi.com.'}


@omdb_bp.route('/test', methods=['POST'])
def test_omdb_connection():
    """
    Test OMDb API connection with the provided API key.

    Request body:
        api_key (str): OMDb API key to validate.

    Returns:
        JSON response with status ('success' or 'error') and a message.
    """
    try:
        data = request.get_json(silent=True)
        api_key = data.get('api_key') if isinstance(data, dict) else None
        if not isinstance(api_key, str) or not api_key.strip():
            return jsonify({'status': 'error', 'message': 'OMDb API key is required'}), 400

        from api_service.blueprints.jobs.routes import run_async
        result = run_async(_check_omdb_key(api_key.strip()))

        status_code = 200 if result['status'] == 'success' else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error("Error testing OMDb connection: %s", str(e), exc_info=True)
        return jsonify({'status': 'error',
                        'message': 'Error testing OMDb connection'}), 500
