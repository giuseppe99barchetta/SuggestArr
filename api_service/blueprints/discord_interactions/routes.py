"""Public, signature-verified endpoint Discord calls when someone taps a rating button.

Discord also calls it once with a PING when the URL is saved in the Developer Portal. The
route sits outside the login wall (``PUBLIC_ROUTES``): the Ed25519 signature is the only
credential, checked against the public keys of users who saved Discord credentials.
"""
import json

from flask import Blueprint, jsonify, request

from api_service.auth.limiter import limiter
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.jobs.rating_prompts import answer_discord_interaction
from api_service.services import discord_interactions as discord

discord_interactions_bp = Blueprint('discord_interactions', __name__)
logger = LoggerManager.get_logger('DiscordInteractions')
MAX_BODY_BYTES = 16 * 1024
PING, MESSAGE_COMPONENT = 1, 3


def _unauthorized():
    return jsonify({}), 401


@discord_interactions_bp.route('/interactions', methods=['POST'])
@limiter.limit('120 per minute')
def interactions():
    """Verify Discord's signature, then answer a PING or apply a button tap."""
    if request.content_length is None or request.content_length > MAX_BODY_BYTES:
        return _unauthorized()
    body = request.get_data(cache=False)
    signature = request.headers.get('X-Signature-Ed25519', '')
    timestamp = request.headers.get('X-Signature-Timestamp', '')
    if not discord.timestamp_is_fresh(timestamp):
        return _unauthorized()
    db = DatabaseManager()
    public_key = next((key for key in db.discord_public_keys()
                       if discord.verify_signature(key, timestamp, body, signature)), None)
    if not public_key:
        return _unauthorized()
    try:
        interaction = json.loads(body)
    except ValueError:
        return jsonify({'error': 'Invalid JSON'}), 400
    kind = interaction.get('type') if isinstance(interaction, dict) else None
    if kind == PING:
        return jsonify(discord.pong()), 200
    if kind == MESSAGE_COMPONENT:
        try:
            return jsonify(answer_discord_interaction(db, public_key, interaction)), 200
        except Exception as exc:
            logger.warning('Could not handle a Discord rating tap: %s', type(exc).__name__)
            return jsonify(discord.refused()), 200
    return jsonify({'error': 'Unsupported interaction'}), 400
