"""Tests for JourneyService.cancel_journey method."""

from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db.journey_repository import (
    create_journey,
    create_journey_plan,
    get_journey,
    get_journeys_by_plan,
    update_journey_status,
)
from backend.app.models.journey import JourneyModel, JourneyStatus
from backend.app.services.journey_service import JourneyService


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema."""
    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(schema_sql)
            await db.commit()

        # Insert test carers and a patient/visit for FK constraints
        async with database.get_db() as db:
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (1, 'Test Carer', 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)"""
            )
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (2, 'Carer Two', 51.6, -0.2, '["driving"]', 8.0, 6.0, 30)"""
            )
            await db.execute(
                """INSERT INTO patients (id, name, address, lat, lng, priority)
                   VALUES (1, 'Patient A', '123 Main St', 51.6, -0.2, 'medium')"""
            )
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes, window_start, window_end, is_cancelled)
                   VALUES (1, 1, 30, '08:00', '10:00', 0)"""
            )
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes, window_start, window_end, is_cancelled)
                   VALUES (2, 1, 30, '10:00', '12:00', 0)"""
            )
            await db.commit()

        yield


@pytest_asyncio.fixture
async def service():
    """Create a JourneyService instance."""
    return JourneyService()


@pytest_asyncio.fixture
async def plan_with_journey(test_db):
    """Create a plan with a single planned journey and return both."""
    plan = await create_journey_plan("2025-06-01", "initial_creation", 1)
    journey = await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-06-01T08:00:00",
        planned_arrival="2025-06-01T08:30:00",
        planned_distance_miles=5.0,
    )
    return plan, journey


# --- 404 tests ---


@pytest.mark.asyncio
async def test_cancel_journey_not_found(test_db, service):
    """cancel_journey raises 404 when journey does not exist."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_journey(9999)

    assert exc_info.value.status_code == 404
    assert "Journey not found" in exc_info.value.detail


# --- Terminal state (409) tests ---


@pytest.mark.asyncio
async def test_cancel_completed_journey_raises_409(test_db, service, plan_with_journey):
    """cancel_journey raises 409 for a completed journey."""
    from fastapi import HTTPException

    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "completed")

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_journey(journey["id"])

    assert exc_info.value.status_code == 409
    assert "completed Journeys cannot be cancelled" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cancel_already_cancelled_journey_raises_409(test_db, service, plan_with_journey):
    """cancel_journey raises 409 for an already cancelled journey."""
    from fastapi import HTTPException

    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "cancelled", cancelled_at="2025-06-01T07:00:00Z")

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_journey(journey["id"])

    assert exc_info.value.status_code == 409
    assert "Journey is already cancelled" in exc_info.value.detail


# --- Successful cancellation of planned journey ---


@pytest.mark.asyncio
async def test_cancel_planned_journey_returns_cancelled_model(test_db, service, plan_with_journey):
    """cancel_journey returns a JourneyModel with status cancelled and timestamp."""
    plan, journey = plan_with_journey

    result = await service.cancel_journey(journey["id"])

    assert isinstance(result, JourneyModel)
    assert result.status == JourneyStatus.CANCELLED
    assert result.cancelled_at is not None


@pytest.mark.asyncio
async def test_cancel_planned_journey_creates_new_plan_version(test_db, service, plan_with_journey):
    """cancel_journey creates a new plan version."""
    plan, journey = plan_with_journey

    result = await service.cancel_journey(journey["id"])

    # The new journey should be in a new plan (plan_version 2)
    assert result.plan_id != plan["id"]


@pytest.mark.asyncio
async def test_cancel_preserves_old_plan_version(test_db, service, plan_with_journey):
    """The old plan version retains the journey in its pre-cancellation state."""
    plan, journey = plan_with_journey

    await service.cancel_journey(journey["id"])

    # Original journey in old plan should still be 'planned'
    original = await get_journey(journey["id"])
    assert original["status"] == "planned"


@pytest.mark.asyncio
async def test_cancel_copies_all_journeys_to_new_plan(test_db, service):
    """cancel_journey copies all journeys to the new plan version."""
    plan = await create_journey_plan("2025-06-01", "initial_creation", 1)
    j1 = await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-06-01T08:00:00",
        planned_arrival="2025-06-01T08:30:00",
        planned_distance_miles=5.0,
    )
    j2 = await create_journey(
        plan_id=plan["id"],
        carer_id=2,
        visit_id=None,
        origin_lat=51.7,
        origin_lng=-0.3,
        origin_label="Home B",
        destination_lat=51.8,
        destination_lng=-0.4,
        destination_label="Patient B",
        planned_departure="2025-06-01T09:00:00",
        planned_arrival="2025-06-01T09:30:00",
        planned_distance_miles=4.0,
    )

    result = await service.cancel_journey(j1["id"])

    # Get all journeys in the new plan
    new_plan_journeys = await get_journeys_by_plan(result.plan_id)
    assert len(new_plan_journeys) == 2

    # The cancelled one
    cancelled = [j for j in new_plan_journeys if j["carer_id"] == 1][0]
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None

    # The other journey should be unchanged
    other = [j for j in new_plan_journeys if j["carer_id"] == 2][0]
    assert other["status"] == "planned"


# --- Cancellation of in-progress journey ---


@pytest.mark.asyncio
async def test_cancel_in_progress_journey_succeeds(test_db, service, plan_with_journey):
    """cancel_journey succeeds for an in_progress journey."""
    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    result = await service.cancel_journey(journey["id"])

    assert result.status == JourneyStatus.CANCELLED
    assert result.cancelled_at is not None


@pytest.mark.asyncio
async def test_cancel_in_progress_journey_marks_visit_unassigned(test_db, service):
    """cancel_journey marks incomplete visits as unassigned (is_cancelled=1) for in_progress journeys."""
    plan = await create_journey_plan("2025-06-01", "initial_creation", 1)
    journey = await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=1,  # Links to a visit
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-06-01T08:00:00",
        planned_arrival="2025-06-01T08:30:00",
        planned_distance_miles=5.0,
    )
    await update_journey_status(journey["id"], "in_progress")

    await service.cancel_journey(journey["id"])

    # Verify the visit is now marked as cancelled/unassigned
    async with database.get_db() as db:
        cursor = await db.execute("SELECT is_cancelled FROM visits WHERE id = 1")
        row = await cursor.fetchone()
        assert row["is_cancelled"] == 1


@pytest.mark.asyncio
async def test_cancel_in_progress_no_visit_id_does_not_error(test_db, service, plan_with_journey):
    """cancel_journey on in_progress journey without visit_id does not error."""
    plan, journey = plan_with_journey
    # journey has visit_id=None
    await update_journey_status(journey["id"], "in_progress")

    result = await service.cancel_journey(journey["id"])

    assert result.status == JourneyStatus.CANCELLED


# --- cancelled_at timestamp format ---


@pytest.mark.asyncio
async def test_cancel_journey_records_utc_iso8601_timestamp(test_db, service, plan_with_journey):
    """cancel_journey records a valid UTC ISO 8601 timestamp."""
    plan, journey = plan_with_journey

    result = await service.cancel_journey(journey["id"])

    # Should be a valid ISO 8601 string containing timezone info
    assert result.cancelled_at is not None
    assert "T" in result.cancelled_at
