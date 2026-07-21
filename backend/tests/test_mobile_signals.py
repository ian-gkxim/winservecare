"""Tests for the Carer Mobile App signal ingestion endpoints."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db.mobile_repository import (
    create_auth,
    create_question,
)
from backend.app.services.auth_service import (
    create_access_token,
    hash_password,
)


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema, a test carer, visit, and auth."""
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
            # Insert a second carer for cross-ownership tests
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours)
                   VALUES (2, 'Bob Jones', 51.6, -0.2, '["medication"]', 8.0)"""
            )
            # Insert a test patient
            await db.execute(
                """INSERT INTO patients (id, name, address, lat, lng, priority)
                   VALUES (1, 'Alice Patient', '1 Test St', 51.51, -0.09, 'medium')"""
            )
            # Insert a test visit
            await db.execute(
                """INSERT INTO visits (id, patient_id, window_start, window_end, duration_minutes, required_skills, is_cancelled)
                   VALUES (1, 1, '09:00', '10:00', 30, '["personal_care"]', 0)"""
            )
            await db.commit()

        # Create auth record for carer 1
        password_hash = hash_password("password123")
        await create_auth(1, password_hash)

        yield


@pytest_asyncio.fixture
async def auth_headers(test_db):
    """Return Authorization headers for carer 1."""
    token, _ = create_access_token(1)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers_carer2(test_db):
    """Return Authorization headers for carer 2."""
    token, _ = create_access_token(2)
    return {"Authorization": f"Bearer {token}"}


# --- GPS Signal Endpoint Tests ---


class TestGPSSignals:
    """Tests for POST /api/mobile/signals/gps."""

    @pytest.mark.asyncio
    async def test_submit_gps_batch_success(self, test_db, auth_headers):
        """Submitting a valid GPS batch returns 201 with signal count."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "signals": [
                {
                    "latitude": 51.5074,
                    "longitude": -0.1278,
                    "accuracy_metres": 10.0,
                    "captured_at": "2025-01-15T09:00:00+00:00",
                },
                {
                    "latitude": 51.5075,
                    "longitude": -0.1279,
                    "accuracy_metres": 15.0,
                    "captured_at": "2025-01-15T09:01:00+00:00",
                },
            ]
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/gps",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 201
        data = response.json()
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_gps_low_accuracy_flag_set(self, test_db, auth_headers):
        """GPS signals with accuracy > 50m get low_accuracy flag set."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "signals": [
                {
                    "latitude": 51.5074,
                    "longitude": -0.1278,
                    "accuracy_metres": 55.0,
                    "captured_at": "2025-01-15T09:00:00+00:00",
                },
            ]
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/gps",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 201

        # Verify in DB that low_accuracy is set
        async with database.get_db() as db:
            cursor = await db.execute(
                "SELECT low_accuracy FROM gps_signals WHERE carer_id = 1"
            )
            row = await cursor.fetchone()
            assert row["low_accuracy"] == 1

    @pytest.mark.asyncio
    async def test_gps_low_accuracy_flag_not_set(self, test_db, auth_headers):
        """GPS signals with accuracy <= 50m do not get low_accuracy flag."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "signals": [
                {
                    "latitude": 51.5074,
                    "longitude": -0.1278,
                    "accuracy_metres": 50.0,
                    "captured_at": "2025-01-15T09:02:00+00:00",
                },
            ]
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/gps",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 201

        async with database.get_db() as db:
            cursor = await db.execute(
                "SELECT low_accuracy FROM gps_signals WHERE carer_id = 1 AND accuracy_metres = 50.0"
            )
            row = await cursor.fetchone()
            assert row["low_accuracy"] == 0

    @pytest.mark.asyncio
    async def test_gps_idempotent_deduplication(self, test_db, auth_headers):
        """Submitting the same GPS signal twice only stores it once."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "signals": [
                {
                    "latitude": 51.5074,
                    "longitude": -0.1278,
                    "accuracy_metres": 10.0,
                    "captured_at": "2025-01-15T09:05:00+00:00",
                },
            ]
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First submission
            resp1 = await client.post(
                "/api/mobile/signals/gps", json=payload, headers=auth_headers
            )
            assert resp1.status_code == 201
            assert resp1.json()["count"] == 1

            # Duplicate submission
            resp2 = await client.post(
                "/api/mobile/signals/gps", json=payload, headers=auth_headers
            )
            assert resp2.status_code == 201
            assert resp2.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_gps_requires_auth(self, test_db):
        """GPS endpoint returns 401 without authorization."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "signals": [
                {
                    "latitude": 51.5074,
                    "longitude": -0.1278,
                    "accuracy_metres": 10.0,
                    "captured_at": "2025-01-15T09:00:00+00:00",
                },
            ]
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/mobile/signals/gps", json=payload)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_gps_empty_batch(self, test_db, auth_headers):
        """Submitting an empty GPS batch returns 201 with count 0."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {"signals": []}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/gps", json=payload, headers=auth_headers
            )

        assert response.status_code == 201
        assert response.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_gps_batch_max_50_validation(self, test_db, auth_headers):
        """Submitting more than 50 signals in a batch is rejected."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        signals = [
            {
                "latitude": 51.5074,
                "longitude": -0.1278,
                "accuracy_metres": 10.0,
                "captured_at": f"2025-01-15T09:{i:02d}:00+00:00",
            }
            for i in range(51)
        ]
        payload = {"signals": signals}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/gps", json=payload, headers=auth_headers
            )

        assert response.status_code == 422


# --- Question Response Endpoint Tests ---


class TestQuestionResponse:
    """Tests for POST /api/mobile/signals/question."""

    @pytest.mark.asyncio
    async def test_submit_question_response_success(self, test_db, auth_headers):
        """Submitting a valid question response returns 200."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        # Create a question for carer 1
        question = await create_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )

        payload = {
            "question_id": question["id"],
            "response_text": "yes",
            "responded_at": "2025-01-15T09:10:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/question",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["question_id"] == question["id"]
        assert data["status"] == "answered"

    @pytest.mark.asyncio
    async def test_question_response_not_found(self, test_db, auth_headers):
        """Responding to a non-existent question returns 404."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "question_id": 9999,
            "response_text": "yes",
            "responded_at": "2025-01-15T09:10:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/question",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_question_response_wrong_carer(self, test_db, auth_headers_carer2):
        """Responding to another carer's question returns 403."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        # Create a question for carer 1
        question = await create_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )

        payload = {
            "question_id": question["id"],
            "response_text": "yes",
            "responded_at": "2025-01-15T09:10:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/question",
                json=payload,
                headers=auth_headers_carer2,
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_question_response_already_answered(self, test_db, auth_headers):
        """Responding to an already-answered question returns 409."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        # Create and answer a question
        question = await create_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        from backend.app.db.mobile_repository import update_question_response
        await update_question_response(question["id"], "yes", "2025-01-15T09:05:00")

        payload = {
            "question_id": question["id"],
            "response_text": "no",
            "responded_at": "2025-01-15T09:10:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/question",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_question_response_requires_auth(self, test_db):
        """Question response endpoint returns 401 without authorization."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "question_id": 1,
            "response_text": "yes",
            "responded_at": "2025-01-15T09:10:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/question", json=payload
            )

        assert response.status_code == 401


# --- Proactive Input Endpoint Tests ---


class TestProactiveInput:
    """Tests for POST /api/mobile/signals/proactive."""

    @pytest.mark.asyncio
    async def test_submit_proactive_input_success(self, test_db, auth_headers):
        """Submitting a valid proactive input returns 201."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "visit_id": 1,
            "input_type": "arrived",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "captured_at": "2025-01-15T09:15:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/proactive",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 201
        data = response.json()
        assert data["visit_id"] == 1
        assert data["input_type"] == "arrived"
        assert data["location_unavailable"] is False

    @pytest.mark.asyncio
    async def test_proactive_input_location_unavailable(self, test_db, auth_headers):
        """Proactive input with no coordinates sets location_unavailable=True."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "visit_id": 1,
            "input_type": "visit_started",
            "latitude": None,
            "longitude": None,
            "captured_at": "2025-01-15T09:20:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/proactive",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 201
        data = response.json()
        assert data["location_unavailable"] is True

    @pytest.mark.asyncio
    async def test_proactive_input_with_note(self, test_db, auth_headers):
        """Proactive input accepts optional free-text note."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "visit_id": 1,
            "input_type": "running_late",
            "note": "Stuck in traffic, will be 10 minutes late.",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "captured_at": "2025-01-15T09:25:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/proactive",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_proactive_input_note_too_long(self, test_db, auth_headers):
        """Proactive input with note > 500 chars is rejected."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "visit_id": 1,
            "input_type": "issue_encountered",
            "note": "x" * 501,
            "latitude": 51.5074,
            "longitude": -0.1278,
            "captured_at": "2025-01-15T09:30:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/proactive",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_proactive_input_visit_not_found(self, test_db, auth_headers):
        """Proactive input with non-existent visit_id returns 404."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "visit_id": 9999,
            "input_type": "arrived",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "captured_at": "2025-01-15T09:35:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/proactive",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_proactive_input_idempotent(self, test_db, auth_headers):
        """Submitting the same proactive input twice returns the existing record."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "visit_id": 1,
            "input_type": "visit_completed",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "captured_at": "2025-01-15T09:40:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.post(
                "/api/mobile/signals/proactive",
                json=payload,
                headers=auth_headers,
            )
            assert resp1.status_code == 201

            resp2 = await client.post(
                "/api/mobile/signals/proactive",
                json=payload,
                headers=auth_headers,
            )
            assert resp2.status_code == 201
            assert resp2.json()["id"] == resp1.json()["id"]

    @pytest.mark.asyncio
    async def test_proactive_input_requires_auth(self, test_db):
        """Proactive input endpoint returns 401 without authorization."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "visit_id": 1,
            "input_type": "arrived",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "captured_at": "2025-01-15T09:45:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/proactive", json=payload
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_proactive_input_invalid_type(self, test_db, auth_headers):
        """Proactive input with invalid input_type is rejected."""
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app

        payload = {
            "visit_id": 1,
            "input_type": "invalid_type",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "captured_at": "2025-01-15T09:50:00+00:00",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/mobile/signals/proactive",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 422
