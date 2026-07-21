"""Tests for the Carer Mobile App authentication endpoints and service."""

from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db.mobile_repository import (
    create_auth,
    get_auth_by_carer_id,
    increment_failed_logins,
    set_lockout,
)
from backend.app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    get_lockout_until,
    hash_password,
    is_locked_out,
    validate_access_token,
    validate_refresh_token,
    verify_password,
)


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and a test carer."""
    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(schema_sql)
            await db.commit()

        # Insert a test carer
        async with database.get_db() as db:
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours)
                   VALUES (1, 'Jane Smith', 51.5, -0.1, '["personal_care"]', 8.0)"""
            )
            await db.commit()

        # Create auth record with known password
        password_hash = hash_password("correct-password")
        await create_auth(1, password_hash)

        yield


# --- Auth Service Unit Tests ---


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_produces_bcrypt_hash(self):
        hashed = hash_password("my-password")
        assert hashed.startswith("$2b$")

    def test_verify_password_with_correct_password(self):
        hashed = hash_password("test123")
        assert verify_password("test123", hashed) is True

    def test_verify_password_with_incorrect_password(self):
        hashed = hash_password("test123")
        assert verify_password("wrong", hashed) is False


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token_returns_token_and_expiry(self):
        token, expires_in = create_access_token(42)
        assert isinstance(token, str)
        assert expires_in == 15 * 60  # 15 minutes in seconds

    def test_create_refresh_token_returns_token_and_datetime(self):
        from datetime import datetime

        token, expires = create_refresh_token(42)
        assert isinstance(token, str)
        assert isinstance(expires, datetime)

    def test_access_token_is_valid(self):
        token, _ = create_access_token(7)
        carer_id = validate_access_token(token)
        assert carer_id == 7

    def test_refresh_token_is_valid(self):
        token, _ = create_refresh_token(7)
        carer_id = validate_refresh_token(token)
        assert carer_id == 7

    def test_access_token_rejects_refresh_token(self):
        token, _ = create_refresh_token(7)
        assert validate_access_token(token) is None

    def test_refresh_token_rejects_access_token(self):
        token, _ = create_access_token(7)
        assert validate_refresh_token(token) is None

    def test_validate_access_token_rejects_garbage(self):
        assert validate_access_token("not.a.real.token") is None

    def test_validate_refresh_token_rejects_garbage(self):
        assert validate_refresh_token("not.a.real.token") is None


class TestLockout:
    """Tests for lockout logic."""

    def test_is_locked_out_with_none(self):
        assert is_locked_out(None) is False

    def test_is_locked_out_with_past_time(self):
        assert is_locked_out("2020-01-01T00:00:00+00:00") is False

    def test_is_locked_out_with_future_time(self):
        assert is_locked_out("2099-01-01T00:00:00+00:00") is True

    def test_get_lockout_until_returns_future_iso(self):
        from datetime import datetime, timezone

        lockout = get_lockout_until()
        lockout_dt = datetime.fromisoformat(lockout)
        assert lockout_dt > datetime.now(timezone.utc)


# --- Endpoint Integration Tests ---


@pytest.mark.asyncio
async def test_login_success(test_db):
    """Successful login returns token pair."""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/mobile/auth/login",
            json={"identifier": "Jane Smith", "password": "correct-password"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["expires_in"] == 900


@pytest.mark.asyncio
async def test_login_invalid_credentials(test_db):
    """Invalid password returns 401."""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/mobile/auth/login",
            json={"identifier": "Jane Smith", "password": "wrong-password"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_identifier(test_db):
    """Unknown identifier returns 401."""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/mobile/auth/login",
            json={"identifier": "Nobody", "password": "anything"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_lockout_after_5_failures(test_db):
    """After 5 failed attempts, returns 429."""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Fail 5 times
        for _ in range(5):
            resp = await client.post(
                "/api/mobile/auth/login",
                json={"identifier": "Jane Smith", "password": "wrong"},
            )
            assert resp.status_code == 401

        # 6th attempt should be locked out
        response = await client.post(
            "/api/mobile/auth/login",
            json={"identifier": "Jane Smith", "password": "correct-password"},
        )

    assert response.status_code == 429


@pytest.mark.asyncio
async def test_refresh_token_flow(test_db):
    """Refresh token issues a new token pair."""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login first
        login_resp = await client.post(
            "/api/mobile/auth/login",
            json={"identifier": "Jane Smith", "password": "correct-password"},
        )
        tokens = login_resp.json()

        # Use refresh token
        response = await client.post(
            "/api/mobile/auth/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["expires_in"] == 900
    # The new access token should be valid
    carer_id = validate_access_token(data["access_token"])
    assert carer_id == 1


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(test_db):
    """Invalid refresh token returns 401."""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/mobile/auth/refresh",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_device_token_registration(test_db):
    """Authenticated carer can register device token."""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login first
        login_resp = await client.post(
            "/api/mobile/auth/login",
            json={"identifier": "Jane Smith", "password": "correct-password"},
        )
        tokens = login_resp.json()

        # Register device token
        response = await client.post(
            "/api/mobile/auth/device-token",
            json={"device_token": "fcm-token-abc123", "platform": "ios"},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

    assert response.status_code == 200

    # Verify token was stored
    auth_record = await get_auth_by_carer_id(1)
    assert auth_record["device_token"] == "fcm-token-abc123"
    assert auth_record["device_platform"] == "ios"


@pytest.mark.asyncio
async def test_device_token_requires_auth(test_db):
    """Device token endpoint returns 401 without auth."""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/mobile/auth/device-token",
            json={"device_token": "fcm-token-abc123", "platform": "ios"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_carer_dependency(test_db):
    """get_current_carer extracts carer_id from valid token."""
    from backend.app.routes.mobile_auth import get_current_carer

    token, _ = create_access_token(1)
    carer_id = await get_current_carer(f"Bearer {token}")
    assert carer_id == 1


@pytest.mark.asyncio
async def test_get_current_carer_rejects_missing_header(test_db):
    """get_current_carer raises 401 without auth header."""
    from backend.app.routes.mobile_auth import get_current_carer
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_current_carer(None)
    assert exc_info.value.status_code == 401
