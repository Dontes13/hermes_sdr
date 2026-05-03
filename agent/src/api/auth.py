from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import structlog

from agent.src.config import settings
from agent.src.exceptions import AuthError

log = structlog.get_logger(__name__)

# Hash the dashboard password once at import time
_PASSWORD_HASH: bytes = bcrypt.hashpw(
    settings.DASHBOARD_PASSWORD.encode("utf-8"), bcrypt.gensalt()
)


def hash_password(password: str) -> bytes:
    """bcrypt hash a password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def verify_password(password: str, hashed: bytes) -> bool:
    """bcrypt check a password against a hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed)


def create_jwt(subject: str = "dashboard") -> str:
    """Create a JWT with HS256, secret from settings, exp = now + JWT_EXPIRY_DAYS."""
    payload = {
        "sub": subject,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(days=settings.JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_jwt(token: str) -> dict:
    """Verify and decode a JWT. Raises AuthError on failure."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}") from e
