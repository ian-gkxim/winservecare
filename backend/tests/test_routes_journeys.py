"""Integration tests for journey lifecycle management API endpoints.

Tests cover end-to-end flows:
1. Create plan → Modify → Receive actuals → Compare
2. Deletion flow
3. Cancellation flow
4. Query/filter flow with pagination
5. Error cases
"""

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.db import database
from backend.app.main import app


def _future_day(days_ahead: int = 3) -> str:
    """Return a future date string in YYYY-MM-DD format."""
    return (date.today() + timedelta(days=days_ahead)).isoformat()


def _make_journey_payload(carer_id: int = 1, departure_offset_hours: int = 0) -> dict:
    """Build a single journey creation payload."""
    base_departure = datetime.now(timezone.utc).replace(
        hour=9, minute=0, second=0, microsecond=0
    ) + timedelta(days=3, hours=departure_offset_hours)
    base_arrival = base_departure + timedelta(minutes=30)
    return {
        "carer_id": carer_id,
        "origin_lat": 51.5,
        "origin_lng": -0.1,
        "origin_label": "Home",
        "destination_lat": 51.51,
        "destination_lng": -0.11,
        "destination_label": "Patient A",
        "planned_departure": base_departure.isoformat(),
        "planned_arrival": base_arrival.isoformat(),
        "planned_distance_miles": 2.5,
    }


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and seed data."""
    import aiosqlite
    from pathlib import Path

    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db_conn:
            await db_conn.execute("PRAGMA foreign_keys=ON")
            await db_conn.executescript(schema_sql)
            await db_conn.commit()

        # Seed minimal test data: 2 carers + 2 patients + 1 visit
        async with database.get_db() as db_conn:
            await db_conn.execute(
                """INSERT INTO carers (name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Alice", 51.5, -0.1, json.dumps(["personal_care", "medication"]), 8.0, 6.0, 30),
            )
            await db_conn.execute(
                """INSERT INTO carers (name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Bob", 51.6, -0.2, json.dumps(["personal_care"]), 10.0, 6.0, 30),
            )
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
            await db_conn.execute(
                """INSERT INTO visits (patient_id, duration_minutes, window_start, window_end, required_skills)
                   VALUES (?, ?, ?, ?, ?)""",
                (1, 30, "09:00", "10:00", json.dumps(["personal_care"])),
            )
            await db_conn.commit()
        yield


@pytest_asyncio.fixture
async def client(test_db):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================
# Flow 1: Create → Modify → Actuals → Compare
# ============================================================


@pytest.mark.asyncio
async def test_full_lifecycle_create_modify_actuals_compare(client):
    """End-to-end: create plan, modify journey, receive actuals, compare."""
    operating_day = _future_day(3)

    # 1. Create a plan with 2 journeys
    journey1 = _make_journey_payload(carer_id=1, departure_offset_hours=0)
    journey2 = _make_journey_payload(carer_id=1, departure_offset_hours=1)

    resp = await client.post("/api/journey-plans", json={
        "operating_day": operating_day,
        "journeys": [journey1, journey2],
    })
    assert resp.status_code == 201
    plan = resp.json()
    assert plan["plan_version"] == 1
    assert plan["operating_day"] == operating_day
    assert len(plan["journeys"]) == 2
    plan_id = plan["id"]
    journey_id = plan["journeys"][0]["id"]

    # 2. Modify the first journey (change destination)
    resp = await client.put(
        f"/api/journey-plans/{plan_id}/journeys/{journey_id}",
        json={"destination_lat": 51.55, "destination_lng": -0.15},
    )
    assert resp.status_code == 200
    modified_plan = resp.json()
    assert modified_plan["plan_version"] == 2
    assert modified_plan["creation_reason"] == "manual_amendment"
    # The modified journey in the new version should have updated destination
    modified_journey = next(
        j for j in modified_plan["journeys"]
        if j["destination_lat"] == 51.55
    )
    assert modified_journey["destination_lng"] == -0.15
    assert modified_journey["status"] == "planned"

    # 3. Receive actual journey data
    actual_departure = datetime.fromisoformat(journey1["planned_departure"])
    actual_arrival = actual_departure + timedelta(minutes=35)

    resp = await client.post("/api/actual-journeys", json={
        "carer_id": 1,
        "operating_day": operating_day,
        "actual_departure": actual_departure.isoformat(),
        "actual_arrival": actual_arrival.isoformat(),
        "actual_distance_miles": 2.8,
        "route_coordinates": [[51.5, -0.1], [51.51, -0.11]],
    })
    assert resp.status_code == 201
    actual = resp.json()
    assert actual["carer_id"] == 1
    assert actual["actual_distance_miles"] == 2.8

    # 4. Compare plan vs actual
    resp = await client.get(f"/api/journey-comparison/{operating_day}")
    assert resp.status_code == 200
    comparison = resp.json()
    assert comparison["operating_day"] == operating_day
    assert comparison["plan_version"] == 2  # Uses latest version


# ============================================================
# Flow 2: Deletion flow
# ============================================================


@pytest.mark.asyncio
async def test_deletion_flow(client):
    """Create a plan for a future day, delete it, verify 404 on GET, verify archived plan accessible."""
    operating_day = _future_day(5)

    # Create the plan
    journey = _make_journey_payload(carer_id=1)
    resp = await client.post("/api/journey-plans", json={
        "operating_day": operating_day,
        "journeys": [journey],
    })
    assert resp.status_code == 201
    plan_id = resp.json()["id"]

    # Delete the plan
    resp = await client.delete(f"/api/journey-plans/{plan_id}")
    assert resp.status_code == 200
    confirmation = resp.json()
    assert confirmation["plan_id"] == plan_id
    assert confirmation["journeys_removed"] == 1

    # GET should still return the plan (it's soft-deleted / archived)
    resp = await client.get(f"/api/journey-plans/{plan_id}")
    assert resp.status_code == 200
    archived_plan = resp.json()
    assert archived_plan["is_archived"] is True
    assert archived_plan["archived_at"] is not None

    # Archived plan should NOT appear in standard list
    resp = await client.get(f"/api/journey-plans?operating_day={operating_day}")
    assert resp.status_code == 200
    plans = resp.json()
    assert all(p["id"] != plan_id for p in plans)

    # Archived plan SHOULD appear when include_archived=true
    resp = await client.get(f"/api/journey-plans?operating_day={operating_day}&include_archived=true")
    assert resp.status_code == 200
    plans = resp.json()
    assert any(p["id"] == plan_id for p in plans)


# ============================================================
# Flow 3: Cancellation flow
# ============================================================


@pytest.mark.asyncio
async def test_cancellation_flow(client):
    """Create a plan, cancel a journey, verify new plan version created."""
    operating_day = _future_day(4)

    # Create the plan
    journey = _make_journey_payload(carer_id=1)
    resp = await client.post("/api/journey-plans", json={
        "operating_day": operating_day,
        "journeys": [journey],
    })
    assert resp.status_code == 201
    plan = resp.json()
    journey_id = plan["journeys"][0]["id"]

    # Cancel the journey
    resp = await client.post(f"/api/journeys/{journey_id}/cancel")
    assert resp.status_code == 200
    cancelled = resp.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None

    # A new plan version should have been created
    resp = await client.get(f"/api/journey-plans?operating_day={operating_day}")
    assert resp.status_code == 200
    plans = resp.json()
    # Should have version 1 (original) + version 2 (after cancellation)
    versions = sorted(p["plan_version"] for p in plans)
    assert versions == [1, 2]


# ============================================================
# Flow 4: Query/filter flow with pagination
# ============================================================


@pytest.mark.asyncio
async def test_query_filter_and_pagination(client):
    """Create multiple plans/journeys, test GET /api/journeys with filters and pagination."""
    operating_day = _future_day(6)

    # Create a plan with 3 journeys (2 for carer 1, 1 for carer 2)
    journeys = [
        _make_journey_payload(carer_id=1, departure_offset_hours=0),
        _make_journey_payload(carer_id=1, departure_offset_hours=1),
        _make_journey_payload(carer_id=2, departure_offset_hours=2),
    ]
    resp = await client.post("/api/journey-plans", json={
        "operating_day": operating_day,
        "journeys": journeys,
    })
    assert resp.status_code == 201

    # Query all journeys for this day
    resp = await client.get(f"/api/journeys?operating_day={operating_day}")
    assert resp.status_code == 200
    result = resp.json()
    assert result["total_count"] == 3
    assert len(result["journeys"]) == 3

    # Filter by carer_id
    resp = await client.get(f"/api/journeys?operating_day={operating_day}&carer_id=1")
    assert resp.status_code == 200
    result = resp.json()
    assert result["total_count"] == 2
    assert all(j["carer_id"] == 1 for j in result["journeys"])

    # Filter by status
    resp = await client.get(f"/api/journeys?operating_day={operating_day}&status=planned")
    assert resp.status_code == 200
    result = resp.json()
    assert result["total_count"] == 3
    assert all(j["status"] == "planned" for j in result["journeys"])

    # Pagination: page_size=2, page=1
    resp = await client.get(f"/api/journeys?operating_day={operating_day}&page=1&page_size=2")
    assert resp.status_code == 200
    result = resp.json()
    assert result["total_count"] == 3
    assert result["page"] == 1
    assert result["page_size"] == 2
    assert len(result["journeys"]) == 2

    # Pagination: page=2 should return the remaining journey
    resp = await client.get(f"/api/journeys?operating_day={operating_day}&page=2&page_size=2")
    assert resp.status_code == 200
    result = resp.json()
    assert result["total_count"] == 3
    assert len(result["journeys"]) == 1


# ============================================================
# Flow 5: Error cases
# ============================================================


@pytest.mark.asyncio
async def test_create_plan_for_past_date_returns_422(client):
    """POST plan for past date should return 422."""
    past_day = (date.today() - timedelta(days=1)).isoformat()
    journey = _make_journey_payload(carer_id=1)
    resp = await client.post("/api/journey-plans", json={
        "operating_day": past_day,
        "journeys": [journey],
    })
    assert resp.status_code == 422
    assert "past" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_plan_with_active_journeys_returns_409(client):
    """DELETE plan with in_progress journeys should return 409."""
    operating_day = _future_day(7)

    # Create a plan
    journey = _make_journey_payload(carer_id=1)
    resp = await client.post("/api/journey-plans", json={
        "operating_day": operating_day,
        "journeys": [journey],
    })
    assert resp.status_code == 201
    plan_id = resp.json()["id"]
    journey_id = resp.json()["journeys"][0]["id"]

    # Manually set journey to in_progress via actual departure
    dep_time = datetime.fromisoformat(journey["planned_departure"])
    arr_time = dep_time + timedelta(minutes=35)
    resp = await client.post("/api/actual-journeys", json={
        "carer_id": 1,
        "operating_day": operating_day,
        "actual_departure": dep_time.isoformat(),
        "actual_arrival": arr_time.isoformat(),
        "actual_distance_miles": 2.5,
        "route_coordinates": [],
    })
    assert resp.status_code == 201

    # Now try to delete — should be rejected
    resp = await client.delete(f"/api/journey-plans/{plan_id}")
    assert resp.status_code == 409
    assert "active" in resp.json()["detail"].lower() or "journeys" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancel_completed_journey_returns_409(client):
    """Cancel a completed journey should return 409."""
    operating_day = _future_day(8)

    # Create a plan
    journey = _make_journey_payload(carer_id=1)
    resp = await client.post("/api/journey-plans", json={
        "operating_day": operating_day,
        "journeys": [journey],
    })
    assert resp.status_code == 201
    plan = resp.json()
    journey_id = plan["journeys"][0]["id"]

    # Send departure actual → in_progress
    dep_time = datetime.fromisoformat(journey["planned_departure"])
    arr_time1 = dep_time + timedelta(minutes=20)
    resp = await client.post("/api/actual-journeys", json={
        "carer_id": 1,
        "operating_day": operating_day,
        "actual_departure": dep_time.isoformat(),
        "actual_arrival": arr_time1.isoformat(),
        "actual_distance_miles": 2.0,
        "route_coordinates": [],
    })
    assert resp.status_code == 201

    # Send arrival actual → completed
    dep_time2 = dep_time + timedelta(minutes=1)
    arr_time2 = dep_time + timedelta(minutes=35)
    resp = await client.post("/api/actual-journeys", json={
        "carer_id": 1,
        "operating_day": operating_day,
        "actual_departure": dep_time2.isoformat(),
        "actual_arrival": arr_time2.isoformat(),
        "actual_distance_miles": 2.5,
        "route_coordinates": [],
    })
    assert resp.status_code == 201

    # Now the journey in the latest plan should be completed.
    # The cancel endpoint uses the journey_id from the original plan's first journey.
    # But after the actual data reception, the original journey (journey_id) should
    # have transitioned to completed. Try to cancel it.
    resp = await client.post(f"/api/journeys/{journey_id}/cancel")
    assert resp.status_code == 409
    assert "completed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_modify_journey_not_found_returns_404(client):
    """Modify a non-existent journey returns 404."""
    resp = await client.put(
        "/api/journey-plans/9999/journeys/9999",
        json={"destination_lat": 51.6},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_plan_returns_404(client):
    """GET a non-existent plan returns 404."""
    resp = await client.get("/api/journey-plans/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_status_filter_returns_422(client):
    """Query with invalid status filter returns 422."""
    resp = await client.get("/api/journeys?status=invalid_status")
    assert resp.status_code == 422
    assert "status" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()
