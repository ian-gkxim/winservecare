"""Tests for the mobile schedule and visit status endpoints."""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.db import database
from backend.app.main import app


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and seed data for mobile schedule tests."""
    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(schema_sql)
            await db.commit()

        # Seed test data
        async with database.get_db() as db:
            # Create carers
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (1, 'Alice Carer', 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)"""
            )
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (2, 'Bob Carer', 51.6, -0.2, '["manual_handling"]', 8.0, 6.0, 30)"""
            )

            # Create patients
            await db.execute(
                """INSERT INTO patients (id, name, address, lat, lng, preferences, priority)
                   VALUES (1, 'Patient One', '10 High Street', 51.51, -0.11, '["no pets", "prefers morning"]', 'high')"""
            )
            await db.execute(
                """INSERT INTO patients (id, name, address, lat, lng, preferences, priority)
                   VALUES (2, 'Patient Two', '20 Oak Road', 51.52, -0.12, '["wheelchair access"]', 'medium')"""
            )
            await db.execute(
                """INSERT INTO patients (id, name, address, lat, lng, preferences, priority)
                   VALUES (3, 'Patient Three', '30 Elm Lane', 51.53, -0.13, '[]', 'low')"""
            )

            # Create visits
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes, window_start, window_end, required_skills)
                   VALUES (1, 1, 30, '09:00', '10:00', '["driving"]')"""
            )
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes, window_start, window_end, required_skills)
                   VALUES (2, 2, 45, '11:00', '12:00', '["manual_handling"]')"""
            )
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes, window_start, window_end, required_skills)
                   VALUES (3, 3, 30, '08:00', '09:00', '[]')"""
            )
            # A cancelled visit that should not appear
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes, window_start, window_end, required_skills, is_cancelled)
                   VALUES (4, 1, 30, '14:00', '15:00', '[]', 1)"""
            )

            # Create a journey plan for today
            today = date.today().isoformat()
            await db.execute(
                """INSERT INTO journey_plans (id, operating_day, creation_reason, plan_version)
                   VALUES (1, ?, 'initial_creation', 1)""",
                (today,),
            )

            # Assign visits to carers via journeys
            # Visit 3 at 08:00, Visit 1 at 09:00 — assigned to carer 1
            await db.execute(
                """INSERT INTO journeys (id, plan_id, carer_id, visit_id, origin_lat, origin_lng, destination_lat, destination_lng, planned_departure, planned_arrival, planned_distance_miles)
                   VALUES (1, 1, 1, 1, 51.5, -0.1, 51.51, -0.11, '2025-01-01T08:30:00', '2025-01-01T09:00:00', 2.0)"""
            )
            await db.execute(
                """INSERT INTO journeys (id, plan_id, carer_id, visit_id, origin_lat, origin_lng, destination_lat, destination_lng, planned_departure, planned_arrival, planned_distance_miles)
                   VALUES (2, 1, 1, 3, 51.5, -0.1, 51.53, -0.13, '2025-01-01T07:30:00', '2025-01-01T08:00:00', 3.0)"""
            )
            # Visit 2 assigned to carer 2
            await db.execute(
                """INSERT INTO journeys (id, plan_id, carer_id, visit_id, origin_lat, origin_lng, destination_lat, destination_lng, planned_departure, planned_arrival, planned_distance_miles)
                   VALUES (3, 1, 2, 2, 51.6, -0.2, 51.52, -0.12, '2025-01-01T10:30:00', '2025-01-01T11:00:00', 1.5)"""
            )
            # Cancelled visit 4 — should not appear even if assigned
            await db.execute(
                """INSERT INTO journeys (id, plan_id, carer_id, visit_id, origin_lat, origin_lng, destination_lat, destination_lng, planned_departure, planned_arrival, planned_distance_miles)
                   VALUES (4, 1, 1, 4, 51.5, -0.1, 51.51, -0.11, '2025-01-01T13:30:00', '2025-01-01T14:00:00', 2.0)"""
            )

            # Add a visit status for visit 1
            await db.execute(
                """INSERT INTO visit_status (id, visit_id, carer_id, status, confidence_score, inferred_by, is_current)
                   VALUES (1, 1, 1, 'travelling', 75, 'gps', 1)"""
            )

            await db.commit()

        yield


@pytest_asyncio.fixture
async def client(test_db):
    """Provide an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- GET /api/mobile/schedule ---


@pytest.mark.asyncio
async def test_get_schedule_returns_visits_for_carer(client):
    """Should return all non-cancelled visits assigned to the carer for today."""
    response = await client.get(
        "/api/mobile/schedule",
        headers={"X-Carer-Id": "1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # visit 1 and visit 3 (not cancelled visit 4)


@pytest.mark.asyncio
async def test_get_schedule_sorted_by_window_start(client):
    """Should return visits sorted chronologically by window_start."""
    response = await client.get(
        "/api/mobile/schedule",
        headers={"X-Carer-Id": "1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Visit 3 (08:00) should come before Visit 1 (09:00)
    assert data[0]["window_start"] == "08:00"
    assert data[1]["window_start"] == "09:00"


@pytest.mark.asyncio
async def test_get_schedule_includes_status_and_confidence(client):
    """Should include current visit status and confidence score."""
    response = await client.get(
        "/api/mobile/schedule",
        headers={"X-Carer-Id": "1"},
    )
    data = response.json()
    # Visit 1 has status 'travelling' with confidence 75
    visit_1 = next(v for v in data if v["id"] == 1)
    assert visit_1["status"] == "travelling"
    assert visit_1["confidence_score"] == 75

    # Visit 3 has no status record — should default to pending/0
    visit_3 = next(v for v in data if v["id"] == 3)
    assert visit_3["status"] == "pending"
    assert visit_3["confidence_score"] == 0


@pytest.mark.asyncio
async def test_get_schedule_empty_for_carer_with_no_visits(client):
    """Should return empty list if carer has no visits for today."""
    response = await client.get(
        "/api/mobile/schedule",
        headers={"X-Carer-Id": "999"},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_schedule_requires_auth_header(client):
    """Should return 422 if X-Carer-Id header is missing."""
    response = await client.get("/api/mobile/schedule")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_schedule_visit_fields(client):
    """Should return all required fields for each visit summary."""
    response = await client.get(
        "/api/mobile/schedule",
        headers={"X-Carer-Id": "2"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    visit = data[0]
    assert visit["id"] == 2
    assert visit["patient_name"] == "Patient Two"
    assert visit["patient_address"] == "20 Oak Road"
    assert visit["patient_lat"] == 51.52
    assert visit["patient_lng"] == -0.12
    assert visit["window_start"] == "11:00"
    assert visit["window_end"] == "12:00"
    assert visit["duration_minutes"] == 45
    assert visit["required_skills"] == ["manual_handling"]
    assert visit["status"] == "pending"
    assert visit["confidence_score"] == 0


# --- GET /api/mobile/schedule/{visit_id} ---


@pytest.mark.asyncio
async def test_get_visit_detail_returns_full_info(client):
    """Should return visit detail with patient preferences."""
    response = await client.get(
        "/api/mobile/schedule/1",
        headers={"X-Carer-Id": "1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["patient_name"] == "Patient One"
    assert data["patient_preferences"] == ["no pets", "prefers morning"]
    assert data["status"] == "travelling"
    assert data["confidence_score"] == 75


@pytest.mark.asyncio
async def test_get_visit_detail_not_found(client):
    """Should return 404 if visit not found in carer's schedule."""
    response = await client.get(
        "/api/mobile/schedule/999",
        headers={"X-Carer-Id": "1"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_visit_detail_not_assigned_to_carer(client):
    """Should return 404 if visit exists but is not assigned to this carer."""
    # Visit 2 is assigned to carer 2, not carer 1
    response = await client.get(
        "/api/mobile/schedule/2",
        headers={"X-Carer-Id": "1"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_visit_detail_empty_preferences(client):
    """Should return empty list for patient with no preferences."""
    response = await client.get(
        "/api/mobile/schedule/3",
        headers={"X-Carer-Id": "1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["patient_preferences"] == []


# --- GET /api/mobile/visits/{visit_id}/status ---


@pytest.mark.asyncio
async def test_get_visit_status_existing(client):
    """Should return current status and confidence for a visit with status."""
    response = await client.get(
        "/api/mobile/visits/1/status",
        headers={"X-Carer-Id": "1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["visit_id"] == 1
    assert data["status"] == "travelling"
    assert data["confidence_score"] == 75
    assert "last_updated" in data


@pytest.mark.asyncio
async def test_get_visit_status_default_when_no_record(client):
    """Should return default pending status with confidence 0 if no status record."""
    response = await client.get(
        "/api/mobile/visits/3/status",
        headers={"X-Carer-Id": "1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["visit_id"] == 3
    assert data["status"] == "pending"
    assert data["confidence_score"] == 0
    assert "last_updated" in data


@pytest.mark.asyncio
async def test_get_visit_status_requires_auth(client):
    """Should return 422 if auth header is missing."""
    response = await client.get("/api/mobile/visits/1/status")
    assert response.status_code == 422
