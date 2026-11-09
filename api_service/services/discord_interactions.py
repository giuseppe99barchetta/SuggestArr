"""Discord pieces of rating prompts: signature check, button layout and interaction replies.

Discord signs every interaction it POSTs to a bot's Interactions Endpoint URL with the
application's Ed25519 key: signature over ``timestamp + raw body`` (headers
``X-Signature-Ed25519`` and ``X-Signature-Timestamp``).
"""
import time

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

# Interaction reply types (https://discord.com/developers/docs/interactions/receiving-and-responding)
PONG = 1
CHANNEL_MESSAGE = 4
UPDATE_MESSAGE = 7
EPHEMERAL = 64
MAX_TIMESTAMP_SKEW = 300  # seconds


def verify_signature(public_key_hex: str, timestamp: str, body: bytes, signature_hex: str) -> bool:
    """Whether ``signature_hex`` is a valid Ed25519 signature of ``timestamp + body`` by the given key.

    Never raises: malformed hex, wrong lengths and bad signatures all return False.
    """
    try:
        VerifyKey(bytes.fromhex(public_key_hex)).verify(timestamp.encode('utf-8') + body, bytes.fromhex(signature_hex))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def timestamp_is_fresh(timestamp: str, now: float = None) -> bool:
    """Whether the signed timestamp (Unix seconds) is within five minutes of now."""
    try:
        return abs((time.time() if now is None else now) - int(timestamp)) <= MAX_TIMESTAMP_SKEW
    except (TypeError, ValueError, OverflowError):
        return False


def prompt_components(prompt_id: int, nonce: str) -> list:
    """Two action rows of five buttons, labelled 1-10, each carrying ``rp:<prompt>:<nonce>:<n>``."""
    buttons = [{'type': 2, 'style': 1, 'label': str(n), 'custom_id': f'rp:{prompt_id}:{nonce}:{n}'}
               for n in range(1, 11)]
    return [{'type': 1, 'components': buttons[:5]}, {'type': 1, 'components': buttons[5:]}]


def pong() -> dict:
    return {'type': PONG}


def refused() -> dict:
    """What a person sees when a tap is refused: a private note that says nothing about why."""
    return {'type': CHANNEL_MESSAGE, 'data': {'content': 'Not available', 'flags': EPHEMERAL}}


def updated(text: str) -> dict:
    """Replace the prompt message with ``text`` and drop its buttons."""
    return {'type': UPDATE_MESSAGE, 'data': {'content': text[:2000], 'components': []}}
