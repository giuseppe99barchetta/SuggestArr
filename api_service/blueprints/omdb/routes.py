"""
OMDb API blueprint — provides an endpoint to test the OMDb API key.
"""

import asyncio
import aiohttp
from flask import Blueprint, request, jsonify
from api_service.config.logger_manager import LoggerManager

omdb_bp = Blueprint('omdb', __name__)
logger = LoggerManager.get_logger("OMDbRoute")

# A stable test title to validate the key (Interstellar)
_TEST_IMDB_ID = "tt0816692"


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
        data = request.json
        if not data or 'api_key' not in data:
            return jsonify({'status': 'error', 'message': 'OMDb API key is required'}), 400

        api_key = data['api_key']
        test_url = f"https://www.omdbapi.com/?i={_TEST_IMDB_ID}&apikey={api_key}"

        async def _test():
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(test_url) as response:
                        if response.status == 200:
                            result = await response.json()
                            if result.get('Response') == 'True':
                                return {'status': 'success',
                                        'message': 'OMDb API key validated successfully!'}
                            elif result.get('Error') == 'Invalid API key!':
                                return {'status': 'error', 'message': 'Invalid OMDb API key'}
                            else:
                                return {'status': 'error',
                                        'message': result.get('Error', 'Unknown OMDb error')}
                        else:
                            return {'status': 'error',
                                    'message': f'OMDb API returned status {response.status}'}
            except aiohttp.ClientTimeout:
                return {'status': 'error', 'message': 'Connection to OMDb API timed out'}
            except aiohttp.ClientError as e:
                logger.error("OMDb connection error: %s", e)
                return {'status': 'error',
                        'message': 'Failed to connect to OMDb API'}

        from api_service.blueprints.jobs.routes import run_async
        result = run_async(_test())

        status_code = 200 if result['status'] == 'success' else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error("Error testing OMDb connection: %s", str(e), exc_info=True)
        return jsonify({'status': 'error',
                        'message': 'Error testing OMDb connection'}), 500
