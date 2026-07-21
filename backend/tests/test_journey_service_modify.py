"""Tests for JourneyService.modify_journey method."""

from datetime import datetime
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
    update_journey_status,
)
from backend.app.models.journey import (
    JourneyUpdate,
    PlanCreationReason,
)
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

        # Insert test carers for FK constraints
        async with database.get_db() as db:
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (1, 'Test Carer', 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)"""
            )
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (2, 'Carer Two', 51.6, -0.2, '["driving"]', 8.0, 6.0, 30)"""
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
async def test_modify_journey_not_found(test_db, service):
    """modify_journey raises 404 when journey does not exist."""
    from fastapi import HTTPException

    plan = await create_journey_plan("2025-06-01", "initial_creation", 1)
    update = JourneyUpdate(destination_lat=52.0)

    with pytest.raises(HTTPException) as exc_info:
        await service.modify_journey(plan["id"], 9999, update)

    assert exc_info.value.status_code == 404
    assert "Journey not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_modify_journey_wrong_plan(test_db, service):
    """modify_journey raises 404 when journey belongs to a different plan."""
    from fastapi import HTTPException

    plan1 = await create_journey_plan("2025-06-01", "initial_creation", 1)
    plan2 = await create_journey_plan("2025-06-02", "initial_creation", 1)
    journey = await create_journey(
        plan_id=plan1["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label=None,
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label=None,
        planned_departure="2025-06-01T08:00:00",
        planned_arrival="2025-06-01T08:30:00",
        planned_distance_miles=5.0,
    )

    update = JourneyUpdate(destination_lat=52.0)

    with pytest.raises(HTTPException) as exc_info:
        await service.modify_journey(plan2["id"], journey["id"], update)

    assert exc_info.value.status_code == 404
    assert "not found in the specified plan" in exc_info.value.detail


# --- Terminal state (409) tests ---


@pytest.mark.asyncio
async def test_modify_journey_completed_raises_409(test_db, service, plan_with_journey):
    """modify_journey raises 409 for a completed journey."""
    from fastapi import HTTPException

    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "completed")

    update = JourneyUpdate(destination_lat=52.0)

    with pytest.raises(HTTPException) as exc_info:
        await service.modify_journey(plan["id"], journey["id"], update)

    assert exc_info.value.status_code == 409
    assert "terminal state" in exc_info.value.detail


@pytest.mark.asyncio
async def test_modify_journey_cancelled_raises_409(test_db, service, plan_with_journey):
    """modify_journey raises 409 for a cancelled journey."""
    from fastapi import HTTPException

    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "cancelled", cancelled_at="2025-06-01T07:00:00")

    update = JourneyUpdate(planned_arrival=datetime(2025, 6, 1, 9, 0))

    with pytest.raises(HTTPException) as exc_info:
        await service.modify_journey(plan["id"], journey["id"], update)

    assert exc_info.value.status_code == 409
    assert "terminal state" in exc_info.value.detail


# --- In-progress restricted fields (409) tests ---


@pytest.mark.asyncio
async def test_modify_in_progress_rejects_carer_id(test_db, service, plan_with_journey):
    """modify_journey raises 409 when changing carer_id on in_progress journey."""
    from fastapi import HTTPException

    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    update = JourneyUpdate(carer_id=2)

    with pytest.raises(HTTPException) as exc_info:
        await service.modify_journey(plan["id"], journey["id"], update)

    assert exc_info.value.status_code == 409
    assert "carer_id" in exc_info.value.detail


@pytest.mark.asyncio
async def test_modify_in_progress_rejects_planned_departure(test_db, service, plan_with_journey):
    """modify_journey raises 409 when changing planned_departure on in_progress journey."""
    from fastapi import HTTPException

    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    update = JourneyUpdate(planned_departure=datetime(2025, 6, 1, 9, 0))

    with pytest.raises(HTTPException) as exc_info:
        await service.modify_journey(plan["id"], journey["id"], update)

    assert exc_info.value.status_code == 409
    assert "planned_departure" in exc_info.value.detail


@pytest.mark.asyncio
async def test_modify_in_progress_rejects_origin_lat(test_db, service, plan_with_journey):
    """modify_journey raises 409 when changing origin_lat on in_progress journey."""
    from fastapi import HTTPException

    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    update = JourneyUpdate(origin_lat=52.0)

    with pytest.raises(HTTPException) as exc_info:
        await service.modify_journey(plan["id"], journey["id"], update)

    assert exc_info.value.status_code == 409
    assert "origin_lat" in exc_info.value.detail


@pytest.mark.asyncio
async def test_modify_in_progress_rejects_origin_lng(test_db, service, plan_with_journey):
    """modify_journey raises 409 when changing origin_lng on in_progress journey."""
    from fastapi import HTTPException

    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    update = JourneyUpdate(origin_lng=-1.0)

    with pytest.raises(HTTPException) as exc_info:
        await service.modify_journey(plan["id"], journey["id"], update)

    assert exc_info.value.status_code == 409
    assert "origin_lng" in exc_info.value.detail


# --- In-progress allowed fields ---


@pytest.mark.asyncio
async def test_modify_in_progress_allows_planned_arrival(test_db, service, plan_with_journey):
    """modify_journey allows changing planned_arrival on in_progress journey."""
    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    new_arrival = datetime(2025, 6, 1, 9, 15)
    update = JourneyUpdate(planned_arrival=new_arrival)

    result = await service.modify_journey(plan["id"], journey["id"], update)

    assert result.plan_version == 2
    assert result.creation_reason == PlanCreationReason.MANUAL_AMENDMENT
    # Find the modified journey in the new plan
    modified = [j for j in result.journeys if j.carer_id == 1][0]
    assert modified.planned_arrival == new_arrival.isoformat()


@pytest.mark.asyncio
async def test_modify_in_progress_allows_destination_lat(test_db, service, plan_with_journey):
    """modify_journey allows changing destination_lat on in_progress journey."""
    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    update = JourneyUpdate(destination_lat=52.5)

    result = await service.modify_journey(plan["id"], journey["id"], update)

    modified = [j for j in result.journeys if j.carer_id == 1][0]
    assert modified.destination_lat == 52.5


@pytest.mark.asyncio
async def test_modify_in_progress_allows_destination_lng(test_db, service, plan_with_journey):
    """modify_journey allows changing destination_lng on in_progress journey."""
    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    update = JourneyUpdate(destination_lng=-1.5)

    result = await service.modify_journey(plan["id"], journey["id"], update)

    modified = [j for j in result.journeys if j.carer_id == 1][0]
    assert modified.destination_lng == -1.5


# --- Planned journey allows all fields ---


@pytest.mark.asyncio
async def test_modify_planned_allows_all_fields(test_db, service, plan_with_journey):
    """modify_journey allows all JourneyUpdate fields on a planned journey."""
    plan, journey = plan_with_journey

    update = JourneyUpdate(
        carer_id=2,
        planned_departure=datetime(2025, 6, 1, 10, 0),
        planned_arrival=datetime(2025, 6, 1, 10, 45),
        origin_lat=52.0,
        origin_lng=-0.5,
        destination_lat=53.0,
        destination_lng=-1.0,
    )

    result = await service.modify_journey(plan["id"], journey["id"], update)

    assert result.plan_version == 2
    # Find the modified journey (now assigned to carer 2)
    modified = [j for j in result.journeys if j.origin_lat == 52.0][0]
    assert modified.carer_id == 2
    assert modified.planned_departure == "2025-06-01T10:00:00"
    assert modified.planned_arrival == "2025-06-01T10:45:00"
    assert modified.origin_lng == -0.5
    assert modified.destination_lat == 53.0
    assert modified.destination_lng == -1.0


# --- New plan version creation ---


@pytest.mark.asyncio
async def test_modify_creates_new_plan_version(test_db, service, plan_with_journey):
    """modify_journey creates a new plan version with incremented version number."""
    plan, journey = plan_with_journey

    update = JourneyUpdate(destination_lat=52.0)

    result = await service.modify_journey(plan["id"], journey["id"], update)

    assert result.id != plan["id"]
    assert result.plan_version == 2
    assert result.operating_day == "2025-06-01"
    assert result.creation_reason == PlanCreationReason.MANUAL_AMENDMENT


@pytest.mark.asyncio
async def test_modify_marks_original_journey_as_amended(test_db, service, plan_with_journey):
    """modify_journey marks the original journey as 'amended' in the old plan."""
    plan, journey = plan_with_journey

    update = JourneyUpdate(destination_lat=52.0)

    await service.modify_journey(plan["id"], journey["id"], update)

    # Check the original journey is now marked as amended
    original = await get_journey(journey["id"])
    assert original["status"] == "amended"


@pytest.mark.asyncio
async def test_modify_copies_all_journeys_to_new_plan(test_db, service):
    """modify_journey copies all journeys from the old plan to the new one."""
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

    update = JourneyUpdate(destination_lat=52.0)

    result = await service.modify_journey(plan["id"], j1["id"], update)

    # New plan should contain both journeys
    assert len(result.journeys) == 2
    # The modified journey should have the new destination
    modified = [j for j in result.journeys if j.carer_id == 1][0]
    assert modified.destination_lat == 52.0
    # The unmodified journey should be unchanged
    unmodified = [j for j in result.journeys if j.carer_id == 2][0]
    assert unmodified.destination_lat == 51.8


@pytest.mark.asyncio
async def test_modify_resets_modified_journey_status_to_planned(test_db, service, plan_with_journey):
    """The modified journey in the new plan should have status 'planned'."""
    plan, journey = plan_with_journey
    await update_journey_status(journey["id"], "in_progress")

    update = JourneyUpdate(destination_lat=52.0)

    result = await service.modify_journey(plan["id"], journey["id"], update)

    modified = [j for j in result.journeys if j.carer_id == 1][0]
    assert modified.status.value == "planned"


@pytest.mark.asyncio
async def test_modify_returns_journey_plan_model(test_db, service, plan_with_journey):
    """modify_journey returns a JourneyPlanModel with correct structure."""
    from backend.app.models.journey import JourneyPlanModel

    plan, journey = plan_with_journey

    update = JourneyUpdate(destination_lat=52.0)

    result = await service.modify_journey(plan["id"], journey["id"], update)

    assert isinstance(result, JourneyPlanModel)
    assert result.id is not None
    assert result.operating_day == "2025-06-01"
    assert result.is_archived is False
    assert result.archived_at is None
    assert result.created_at is not None
    assert len(result.journeys) == 1
