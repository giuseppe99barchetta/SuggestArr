import asyncio
from flask import Blueprint, request, jsonify
import aiohttp
from api_service.config.logger_manager import LoggerManager
from api_service.services.tmdb.tmdb_client import TMDbClient

tmdb_bp = Blueprint('tmdb', __name__)
logger = LoggerManager.get_logger("TMDBRoute")


@tmdb_bp.route('/test', methods=['POST'])
async def test_tmdb_connection():
    """
    Test TMDB API connection with provided API key.
    """
    try:
        data = request.json
        if not data or 'api_key' not in data:
            return jsonify({
                'message': 'TMDB API key is required',
                'status': 'error'
            }), 400

        api_key = data['api_key']
        proxy = data.get('proxy', None)
        result = await TMDbClient.test_connection(api_key, proxy)

        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f'Error testing TMDB connection: {str(e)}')
        return jsonify({
            'message': f'Error testing TMDB connection: {str(e)}',
            'status': 'error'
        }), 500

@tmdb_bp.route('/genres/movie', methods=['GET'])
def get_movie_genres():
    """
    Get list of movie genres from TMDB.
    """
    try:
        # Get API key from query parameter or use a default for testing
        api_key = request.args.get('api_key')
        if not api_key:
            return jsonify({
                'message': 'TMDB API key is required',
                'status': 'error'
            }), 400

        genres_url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={api_key}&language=en-US"

        async def fetch_genres():
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(genres_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {
                                'status': 'success',
                                'genres': data.get('genres', [])
                            }
                        else:
                            return {
                                'status': 'error',
                                'message': f'Failed to fetch genres: HTTP {response.status}'
                            }
            except Exception as e:
                return {
                    'status': 'error',
                    'message': f'Error fetching genres: {str(e)}'
                }

        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(fetch_genres())
        finally:
            loop.close()

        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f'Error fetching movie genres: {str(e)}')
        return jsonify({
            'message': f'Error fetching movie genres: {str(e)}',
            'status': 'error'
        }), 500

@tmdb_bp.route('/genres/tv', methods=['GET'])
def get_tv_genres():
    """
    Get list of TV show genres from TMDB.
    """
    try:
        # Get API key from query parameter or use a default for testing
        api_key = request.args.get('api_key')
        if not api_key:
            return jsonify({
                'message': 'TMDB API key is required',
                'status': 'error'
            }), 400

        genres_url = f"https://api.themoviedb.org/3/genre/tv/list?api_key={api_key}&language=en-US"

        async def fetch_genres():
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(genres_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {
                                'status': 'success',
                                'genres': data.get('genres', [])
                            }
                        else:
                            return {
                                'status': 'error',
                                'message': f'Failed to fetch genres: HTTP {response.status}'
                            }
            except Exception as e:
                return {
                    'status': 'error',
                    'message': f'Error fetching genres: {str(e)}'
                }

        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(fetch_genres())
        finally:
            loop.close()

        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f'Error fetching TV genres: {str(e)}')
        return jsonify({
            'message': f'Error fetching TV genres: {str(e)}',
            'status': 'error'
        }), 500
