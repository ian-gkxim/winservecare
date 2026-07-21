"""Tests for JourneyService.delete_plan method."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio
from fastapi import HTTPException

from backend.app.db import database
from backend.app.db.journey_repository import (
    create_journey,
    create_journey_plan,
    get_journey_plan,
    update_journey_status,
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
            await db.commit()

        yield


@pytest.fixture
def service():
    """Create a JourneyService instance."""
    return JourneyService()


@pytest.mark.asyncio
async def test_delete_plan_not_found(test_db, service):
    """Deleting a non-existent plan should raise 404."""
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_plan(plan_id=9999)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_delete_plan_past_date(test_db, service):
    """Deleting a plan for a past operating day should raise 409."""
    past_day = (date.today() - timedelta(days=5)).isoformat()
    plan = await create_journey_plan(past_day, "initial_creation", 1)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_plan(plan_id=plan["id"])

    assert exc_info.value.status_code == 409
    assert "past" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_delete_plan_today_only_plan(test_db, service):
    """Deleting the only plan for today should raise 409."""
    today = date.today().isoformat()
    plan = await create_journey_plan(today, "initial_creation", 1)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_plan(plan_id=plan["id"])

    assert exc_info.value.status_code == 409
    assert "active day plan" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_delete_plan_today_with_multiple_plans(test_db, service):
    """Deleting one of multiple plans for today should succeed."""
    today = date.today().isoformat()
    plan1 = await create_journey_plan(today, "initial_creation", 1)
    await create_journey_plan(today, "manual_amendment", 2)

    # Plan1 has no journeys, multiple plans exist for today
    result = await service.delete_plan(plan_id=plan1["id"])

    assert result.plan_id == plan1["id"]
    assert result.journeys_removed == 0


@pytest.mark.asyncio
async def test_delete_plan_with_active_journeys(test_db, service):
    """Deleting a plan with in_progress journeys should raise 409 with journey IDs."""
    future_day = (date.today() + timedelta(days=3)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)

    # Create a journey and set it to in_progress
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
        planned_departure="2025-09-01T09:00:00",
        planned_arrival="2025-09-01T09:30:00",
        planned_distance_miles=3.5,
    )
    await update_journey_status(journey["id"], "in_progress")

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_plan(plan_id=plan["id"])

    assert exc_info.value.status_code == 409
    assert str(journey["id"]) in exc_info.value.detail


@pytest.mark.asyncio
async def test_delete_plan_future_date_success(test_db, service):
    """Deleting a future plan with only planned journeys should succeed."""
    future_day = (date.today() + timedelta(days=7)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)

    # Create two planned journeys
    await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-09-01T09:00:00",
        planned_arrival="2025-09-01T09:30:00",
        planned_distance_miles=3.5,
    )
    await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.6,
        origin_lng=-0.2,
        origin_label="Patient A",
        destination_lat=51.7,
        destination_lng=-0.3,
        destination_label="Patient B",
        planned_departure="2025-09-01T10:00:00",
        planned_arrival="2025-09-01T10:25:00",
        planned_distance_miles=2.8,
    )

    result = await service.delete_plan(plan_id=plan["id"])

    assert result.plan_id == plan["id"]
    assert result.journeys_removed == 2

    # Verify the plan is now archived
    archived_plan = await get_journey_plan(plan["id"])
    assert archived_plan["is_archived"] == 1
    assert archived_plan["archived_at"] is not None


@pytest.mark.asyncio
async def test_delete_plan_with_completed_journey(test_db, service):
    """Deleting a plan with a completed journey should raise 409."""
    future_day = (date.today() + timedelta(days=3)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)

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
        planned_departure="2025-09-01T09:00:00",
        planned_arrival="2025-09-01T09:30:00",
        planned_distance_miles=3.5,
    )
    await update_journey_status(journey["id"], "completed")

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_plan(plan_id=plan["id"])

    assert exc_info.value.status_code == 409
    assert str(journey["id"]) in exc_info.value.detail
