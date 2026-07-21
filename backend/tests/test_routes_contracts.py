"""Unit tests for care contract API route endpoints."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.db import database
from backend.app.main import app


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and minimal seed data."""
    import aiosqlite

    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db_conn:
            await db_conn.execute("PRAGMA foreign_keys=ON")
            await db_conn.executescript(schema_sql)
            await db_conn.commit()

        # Seed minimal test data: patients and skills
        async with database.get_db() as db_conn:
            await db_conn.execute(
                """INSERT INTO patients (name, address, lat, lng, preferences, priority, continuity_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Patient A", "1 High St", 51.51, -0.11, json.dumps(["morning"]), "high", 85.0),
            )
            await db_conn.execute(
                """INSERT INTO patients (name, address, lat, lng, preferences, priority, continuity_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Patient B", "2 Low St", 51.52, -0.12, json.dumps(["evening"]), "low", 60.0),
            )
            await db_conn.execute("INSERT INTO skills (name) VALUES (?)", ("personal_care",))
            await db_conn.execute("INSERT INTO skills (name) VALUES (?)", ("medication",))
            await db_conn.commit()
        yield


@pytest_asyncio.fixture
async def client(test_db):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _valid_contract_payload(**overrides) -> dict:
    """Helper to build a valid contract creation payload."""
    defaults = {
        "visit_frequency": "daily",
        "days_of_week": None,
        "visits_per_day": 1,
        "start_date": "2025-01-01",
        "end_date": None,
        "excluded_dates": [],
        "visit_slots": [
            {
                "label": "Morning visit",
                "earliest_start": "08:00",
                "latest_start": "09:00",
                "duration_minutes": 30,
                "required_skills": ["personal_care"],
            }
        ],
    }
    defaults.update(overrides)
    return defaults


# --- GET /api/patients/{patient_id}/contract ---


@pytest.mark.asyncio
async def test_get_contract_returns_null_when_none(client):
    resp = await client.get("/api/patients/1/contract")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_contract_returns_contract_after_creation(client):
    payload = _valid_contract_payload()
    await client.put("/api/patients/1/contract", json=payload)

    resp = await client.get("/api/patients/1/contract")
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == 1
    assert data["visit_frequency"] == "daily"
    assert data["visits_per_day"] == 1
    assert len(data["visit_slots"]) == 1
    assert data["visit_slots"][0]["label"] == "Morning visit"
    assert data["visit_slots"][0]["earliest_start"] == "08:00"
    assert data["visit_slots"][0]["latest_start"] == "09:00"
    assert data["visit_slots"][0]["required_skills"] == ["personal_care"]


@pytest.mark.asyncio
async def test_get_contract_404_for_nonexistent_patient(client):
    resp = await client.get("/api/patients/999/contract")
    assert resp.status_code == 404
    assert "999" in resp.json()["detail"]


# --- PUT /api/patients/{patient_id}/contract ---


@pytest.mark.asyncio
async def test_create_contract_returns_201(client):
    payload = _valid_contract_payload()
    resp = await client.put("/api/patients/1/contract", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["patient_id"] == 1
    assert data["visit_frequency"] == "daily"


@pytest.mark.asyncio
async def test_update_contract_returns_200(client):
    payload = _valid_contract_payload()
    await client.put("/api/patients/1/contract", json=payload)

    # Update the same contract
    updated_payload = _valid_contract_payload(
        visits_per_day=2,
        visit_slots=[
            {"label": "Morning", "earliest_start": "08:00", "latest_start": "09:00", "duration_minutes": 30, "required_skills": []},
            {"label": "Afternoon", "earliest_start": "14:00", "latest_start": "15:00", "duration_minutes": 45, "required_skills": []},
        ],
    )
    resp = await client.put("/api/patients/1/contract", json=updated_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["visits_per_day"] == 2
    assert len(data["visit_slots"]) == 2


@pytest.mark.asyncio
async def test_422_when_slot_count_mismatch(client):
    # visits_per_day=2 but only 1 slot
    payload = _valid_contract_payload(visits_per_day=2)
    resp = await client.put("/api/patients/1/contract", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("visit_slots count" in e["message"] for e in errors)


@pytest.mark.asyncio
async def test_422_when_earliest_after_latest(client):
    payload = _valid_contract_payload(
        visit_slots=[
            {"label": "Bad slot", "earliest_start": "10:00", "latest_start": "09:00", "duration_minutes": 30, "required_skills": []}
        ],
    )
    resp = await client.put("/api/patients/1/contract", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("must be before latest_start" in e["message"] for e in errors)


@pytest.mark.asyncio
async def test_422_when_end_date_before_start_date(client):
    payload = _valid_contract_payload(
        start_date="2025-06-01",
        end_date="2025-05-01",
        visit_slots=[
            {"label": "Visit", "earliest_start": "08:00", "latest_start": "09:00", "duration_minutes": 30, "required_skills": []}
        ],
    )
    resp = await client.put("/api/patients/1/contract", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("end_date must be on or after start_date" in e["message"] for e in errors)


@pytest.mark.asyncio
async def test_422_when_skill_does_not_exist(client):
    payload = _valid_contract_payload(
        visit_slots=[
            {"label": "Visit", "earliest_start": "08:00", "latest_start": "09:00", "duration_minutes": 30, "required_skills": ["nonexistent_skill"]}
        ],
    )
    resp = await client.put("/api/patients/1/contract", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("nonexistent_skill" in e["message"] for e in errors)


@pytest.mark.asyncio
async def test_422_when_earliest_start_before_0600(client):
    payload = _valid_contract_payload(
        visit_slots=[
            {"label": "Too early", "earliest_start": "05:00", "latest_start": "06:00", "duration_minutes": 30, "required_skills": []}
        ],
    )
    resp = await client.put("/api/patients/1/contract", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("must be between 06:00 and 22:00" in e["message"] for e in errors)


@pytest.mark.asyncio
async def test_422_when_latest_start_after_2200(client):
    payload = _valid_contract_payload(
        visit_slots=[
            {"label": "Too late", "earliest_start": "21:00", "latest_start": "23:00", "duration_minutes": 30, "required_skills": []}
        ],
    )
    resp = await client.put("/api/patients/1/contract", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("must be between 06:00 and 22:00" in e["message"] for e in errors)


@pytest.mark.asyncio
async def test_422_when_specific_days_without_days_of_week(client):
    payload = _valid_contract_payload(
        visit_frequency="specific_days",
        days_of_week=None,
        visit_slots=[
            {"label": "Visit", "earliest_start": "08:00", "latest_start": "09:00", "duration_minutes": 30, "required_skills": []}
        ],
    )
    resp = await client.put("/api/patients/1/contract", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("days_of_week must be non-empty" in e["message"] for e in errors)


@pytest.mark.asyncio
async def test_put_contract_404_for_nonexistent_patient(client):
    payload = _valid_contract_payload()
    resp = await client.put("/api/patients/999/contract", json=payload)
    assert resp.status_code == 404


# --- DELETE /api/patients/{patient_id}/contract ---


@pytest.mark.asyncio
async def test_delete_contract_returns_204(client):
    # First create a contract
    payload = _valid_contract_payload()
    await client.put("/api/patients/1/contract", json=payload)

    # Then delete it
    resp = await client.delete("/api/patients/1/contract")
    assert resp.status_code == 204

    # Confirm it's gone
    resp = await client.get("/api/patients/1/contract")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_delete_contract_returns_404_when_no_contract(client):
    resp = await client.delete("/api/patients/1/contract")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_contract_404_for_nonexistent_patient(client):
    resp = await client.delete("/api/patients/999/contract")
    assert resp.status_code == 404
