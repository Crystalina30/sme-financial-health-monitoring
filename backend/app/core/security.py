"""Password hashing and JSON Web Token handling.

Passwords are never stored or compared in plaintext: only a bcrypt hash is
persisted, and verification re-hashes the candidate password internally.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt truncates silently beyond 72 bytes; reject rather than truncate.
MAX_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of the given password."""
    if len(plain_password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password must not exceed 72 bytes when UTF-8 encoded.")
    return _password_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True when the plaintext password matches the stored hash."""
    try:
        return _password_context.verify(plain_password, hashed_password)
    except ValueError:
        # Malformed hash in the database: treat as a failed verification
        # rather than raising, so authentication simply fails.
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT access token for the given subject (user id)."""
    minutes = expires_minutes or settings.access_token_expire_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": str(subject),
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the subject of a valid token, or None when it is not valid."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    subject = payload.get("sub")
    return str(subject) if subject is not None else None
