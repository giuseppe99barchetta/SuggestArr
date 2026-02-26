"""
Core authentication primitives: password hashing, JWT issuance/verification,
and opaque refresh-token generation.

Design decisions:
  - bcrypt cost=12: ~250 ms per hash on typical hardware — enough to defeat
    offline attacks without being unacceptable for login UX.
  - Access tokens are short-lived JWTs (15 min, HS256).  HS256 is sufficient
    for a single-instance self-hosted service; RS256 would add complexity with
    no security benefit here.
  - Refresh tokens are opaque random strings (48 url-safe bytes = 288 bits),
    NOT JWTs, so they can be revoked server-side by deleting the stored hash.
  - Only the SHA-256 hash of the refresh token is stored.  A DB compromise
    does not immediately yield usable refresh tokens.
  - JTI (JWT ID) is embedded in every access token to support a future
    per-token revocation list if needed.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt

from api_service.auth.secret_key import load_secret_key
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager.get_logger("AuthService")

_JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Minimum password length enforced at creation time.
MIN_PASSWORD_LENGTH = 8


class AuthService:
    """
    Stateless helper for authentication cryptography.

    All methods are static — no instance state is needed.
    """

    # ------------------------------------------------------------------
    # Password hashing
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a plain-text password with bcrypt (cost factor 12).

        Args:
            password: Plain-text password supplied by the user.

        Returns:
            str: bcrypt hash string (60 characters, includes salt).
        """
        return bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12),
        ).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """
        Constant-time comparison of a plain-text password against a bcrypt hash.

        Never short-circuits on mismatch — callers MUST ensure they always call
        this function even when the username does not exist, using a dummy hash,
        to prevent timing-based username enumeration.

        Args:
            password: Plain-text password supplied by the user.
            hashed:   bcrypt hash to verify against.

        Returns:
            bool: True if the password matches the hash.
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            # Malformed hash — treat as mismatch, never crash the login flow.
            return False

    # ------------------------------------------------------------------
    # JWT access tokens
    # ------------------------------------------------------------------

    @staticmethod
    def create_access_token(user_id: int, username: str, role: str) -> str:
        """
        Issue a short-lived signed JWT access token.

        Payload claims:
          sub      — user ID (string)
          username — display name
          role     — 'admin' or 'viewer'
          iat      — issued-at timestamp
          exp      — expiry timestamp (now + ACCESS_TOKEN_EXPIRE_MINUTES)
          jti      — unique token ID (reserved for future revocation list)

        Args:
            user_id:  Internal DB primary key of the authenticated user.
            username: Display name embedded in the token payload.
            role:     User role string ('admin' | 'viewer').

        Returns:
            str: Signed JWT string.
        """
        now = datetime.now(tz=timezone.utc)
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, load_secret_key(), algorithm=_JWT_ALGORITHM)

    @staticmethod
    def verify_access_token(token: str) -> Optional[dict]:
        """
        Decode and validate a JWT access token.

        Returns None (never raises) so the middleware can produce a uniform 401
        without leaking decode errors to callers.

        Args:
            token: Raw JWT string (the value after 'Bearer ').

        Returns:
            dict | None: Decoded payload dict, or None if invalid/expired.
        """
        try:
            return jwt.decode(
                token,
                load_secret_key(),
                algorithms=[_JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            logger.debug("Rejected expired access token")
            return None
        except jwt.InvalidTokenError as exc:
            logger.debug("Rejected invalid access token: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Opaque refresh tokens
    # ------------------------------------------------------------------

    @staticmethod
    def generate_refresh_token() -> Tuple[str, str]:
        """
        Generate a cryptographically random refresh token.

        Returns a (raw_token, sha256_hex) pair:
          - raw_token  is sent to the browser in an httpOnly cookie.
          - sha256_hex is stored in the database.

        Storing only the hash means a database dump does not yield usable
        refresh tokens (unlike storing the raw value directly).

        Returns:
            Tuple[str, str]: (raw_token, sha256_hex)
        """
        import secrets as _secrets
        raw = _secrets.token_urlsafe(48)   # 288 bits of entropy
        digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        return raw, digest

    @staticmethod
    def hash_refresh_token(raw: str) -> str:
        """
        Hash a raw refresh token to look it up in the database.

        Args:
            raw: Raw refresh token string received from the cookie.

        Returns:
            str: SHA-256 hex digest.
        """
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
