"""Mobile authentication API endpoints for the Carer Mobile App.

Provides login, token refresh, and device token registration endpoints
with rate limiting (5 failed attempts → 60s lockout).
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional

from backend.app.db.database import get_db
from backend.app.db.mobile_repository import (
    get_auth_by_carer_id,
    increment_failed_logins,
    reset_failed_logins,
    set_lockout,
    update_device_token,
    update_refresh_token,
)
from backend.app.models.mobile import (
    DeviceTokenRequest,
    LoginRequest,
    TokenResponse,
)
from backend.app.services.auth_service import (
    MAX_FAILED_ATTEMPTS,
    create_access_token,
    create_refresh_token,
    get_lockout_until,
    is_locked_out,
    validate_access_token,
    validate_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/api/mobile/auth", tags=["mobile-auth"])


async def _get_carer_id_by_identifier(identifier: str) -> int | None:
    """Look up a carer's ID by their name (used as identifier for login).

    Args:
        identifier: The carer's name/identifier.

    Returns:
        The carer_id if found, None otherwise.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM carers WHERE name = ?", (identifier,)
        )
        row = await cursor.fetchone()
        if row:
            return row["id"]
        return None


async def get_current_carer(authorization: Optional[str] = Header(None)) -> int:
    """FastAPI dependency that validates JWT from Authorization: Bearer header.

    Args:
        authorization: The Authorization header value.

    Returns:
        The authenticated carer_id.

    Raises:
        HTTPException: 401 if token is missing or invalid.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    carer_id = validate_access_token(token)
    if carer_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return carer_id


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate a carer and return a JWT token pair.

    Checks lockout state first (returns 429 if locked out).
    On failure: increments failed login counter, sets lockout if count >= 5.
    On success: resets failed logins, generates token pair, stores refresh token.
    """
    # Look up carer by identifier
    carer_id = await _get_carer_id_by_identifier(request.identifier)
    if carer_id is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Get auth record
    auth_record = await get_auth_by_carer_id(carer_id)
    if auth_record is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check lockout state
    if is_locked_out(auth_record.get("lockout_until")):
        raise HTTPException(
            status_code=429,
            detail="Account temporarily locked. Please try again after 60 seconds.",
        )

    # Validate password
    if not verify_password(request.password, auth_record["password_hash"]):
        # Increment failed attempts
        failed_count = await increment_failed_logins(carer_id)
        # Set lockout if threshold reached
        if failed_count >= MAX_FAILED_ATTEMPTS:
            lockout_until = get_lockout_until()
            await set_lockout(carer_id, lockout_until)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Success: reset failed logins
    await reset_failed_logins(carer_id)

    # Generate token pair
    access_token, expires_in = create_access_token(carer_id)
    refresh_token, refresh_expires = create_refresh_token(carer_id)

    # Store refresh token
    await update_refresh_token(
        carer_id, refresh_token, refresh_expires.isoformat()
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(authorization: Optional[str] = Header(None)) -> TokenResponse:
    """Refresh an access token using a valid refresh token.

    Accepts the refresh token via Authorization: Bearer header.
    Validates it (check not expired, matches stored token).
    Issues a new token pair.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header with refresh token required",
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format",
        )

    token = parts[1]

    # Validate the refresh token
    carer_id = validate_refresh_token(token)
    if carer_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Verify token matches what's stored
    auth_record = await get_auth_by_carer_id(carer_id)
    if auth_record is None or auth_record.get("refresh_token") != token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Generate new token pair
    access_token, expires_in = create_access_token(carer_id)
    new_refresh_token, refresh_expires = create_refresh_token(carer_id)

    # Store new refresh token
    await update_refresh_token(
        carer_id, new_refresh_token, refresh_expires.isoformat()
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
    )


@router.post("/device-token", status_code=200)
async def register_device_token(
    request: DeviceTokenRequest,
    carer_id: int = Depends(get_current_carer),
) -> dict:
    """Register or update the push notification device token for the authenticated carer.

    Requires a valid access token in the Authorization header.
    """
    await update_device_token(carer_id, request.device_token, request.platform)
    return {"status": "ok"}
