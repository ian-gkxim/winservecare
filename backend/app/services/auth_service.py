"""Authentication service for the Carer Mobile App.

Provides JWT token creation/validation, password hashing (bcrypt),
and rate-limiting support (lockout after 5 failed attempts).
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

# JWT configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "winservecare-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Rate limiting
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 60


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        password: The plaintext password to hash.

    Returns:
        The bcrypt hash string.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: The plaintext password to check.
        hashed_password: The stored bcrypt hash.

    Returns:
        True if the password matches the hash.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(carer_id: int) -> tuple[str, int]:
    """Create a JWT access token for a carer.

    Args:
        carer_id: The carer's identifier.

    Returns:
        A tuple of (token_string, expires_in_seconds).
    """
    expires_in = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(carer_id),
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expires_in


def create_refresh_token(carer_id: int) -> tuple[str, datetime]:
    """Create a JWT refresh token for a carer.

    Args:
        carer_id: The carer's identifier.

    Returns:
        A tuple of (token_string, expiry_datetime).
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(carer_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expire


def validate_access_token(token: str) -> int | None:
    """Validate a JWT access token and extract the carer_id.

    Args:
        token: The JWT token string.

    Returns:
        The carer_id if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        carer_id = payload.get("sub")
        if carer_id is None:
            return None
        return int(carer_id)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return None


def validate_refresh_token(token: str) -> int | None:
    """Validate a JWT refresh token and extract the carer_id.

    Args:
        token: The JWT token string.

    Returns:
        The carer_id if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        carer_id = payload.get("sub")
        if carer_id is None:
            return None
        return int(carer_id)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return None


def is_locked_out(lockout_until: str | None) -> bool:
    """Check if a carer is currently locked out.

    Args:
        lockout_until: ISO 8601 lockout expiry timestamp, or None.

    Returns:
        True if the carer is still locked out.
    """
    if not lockout_until:
        return False
    try:
        lockout_time = datetime.fromisoformat(lockout_until)
        # Ensure comparison is timezone-aware
        if lockout_time.tzinfo is None:
            lockout_time = lockout_time.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < lockout_time
    except (ValueError, TypeError):
        return False


def get_lockout_until() -> str:
    """Calculate the lockout expiry timestamp (now + 60 seconds).

    Returns:
        ISO 8601 formatted timestamp for lockout expiry.
    """
    lockout_time = datetime.now(timezone.utc) + timedelta(seconds=LOCKOUT_DURATION_SECONDS)
    return lockout_time.isoformat()
