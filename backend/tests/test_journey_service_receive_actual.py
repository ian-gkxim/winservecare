"""Tests for JourneyService.receive_actual method."""

from datetime import date, datetime
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
    ActualJourneyCreate,
    ActualJourneyModel,
    MatchStatus,
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
async def plan_with_planned_journey(test_db):
    """Create a plan with a single planned journey for matching tests."""
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


# --- Validation tests (422) ---


@pytest.mark.asyncio
async def test_receive_actual_rejects_invalid_carer_id(test_db, service):
    """receive_actual raises 422 when carer_id does not exist."""
    from fastapi import HTTPException

    data = ActualJourneyCreate(
        carer_id=9999,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 5),
        actual_arrival=datetime(2025, 6, 1, 8, 35),
        actual_distance_miles=5.2,
        route_coordinates=[[51.5, -0.1], [51.6, -0.2]],
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.receive_actual(data)

    assert exc_info.value.status_code == 422
    assert "does not exist" in exc_info.value.detail


@pytest.mark.asyncio
async def test_receive_actual_rejects_arrival_not_after_departure(test_db, service):
    """receive_actual raises 422 when arrival is not strictly later than departure."""
    from fastapi import HTTPException

    # arrival == departure
    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 0),
        actual_arrival=datetime(2025, 6, 1, 8, 0),
        actual_distance_miles=5.0,
        route_coordinates=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.receive_actual(data)

    assert exc_info.value.status_code == 422
    assert "strictly later" in exc_info.value.detail


@pytest.mark.asyncio
async def test_receive_actual_rejects_arrival_before_departure(test_db, service):
    """receive_actual raises 422 when arrival is before departure."""
    from fastapi import HTTPException

    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 9, 0),
        actual_arrival=datetime(2025, 6, 1, 8, 0),
        actual_distance_miles=5.0,
        route_coordinates=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.receive_actual(data)

    assert exc_info.value.status_code == 422
    assert "strictly later" in exc_info.value.detail


# --- Matching tests ---


@pytest.mark.asyncio
async def test_receive_actual_matches_planned_journey(test_db, service, plan_with_planned_journey):
    """receive_actual matches to planned journey within 60-min window."""
    plan, journey = plan_with_planned_journey

    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 10),  # 10 min after planned
        actual_arrival=datetime(2025, 6, 1, 8, 40),
        actual_distance_miles=5.2,
        route_coordinates=[[51.5, -0.1], [51.55, -0.15], [51.6, -0.2]],
    )

    result = await service.receive_actual(data)

    assert isinstance(result, ActualJourneyModel)
    assert result.journey_id == journey["id"]
    assert result.match_status == MatchStatus.MATCHED
    assert result.carer_id == 1
    assert result.operating_day == "2025-06-01"
    assert result.actual_distance_miles == 5.2
    assert len(result.route_coordinates) == 3


@pytest.mark.asyncio
async def test_receive_actual_unmatched_when_no_planned_journey(test_db, service):
    """receive_actual creates unmatched record when no planned journey exists."""
    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 0),
        actual_arrival=datetime(2025, 6, 1, 8, 30),
        actual_distance_miles=4.5,
        route_coordinates=[],
    )

    result = await service.receive_actual(data)

    assert result.journey_id is None
    assert result.match_status == MatchStatus.UNMATCHED


@pytest.mark.asyncio
async def test_receive_actual_unmatched_outside_60_min_window(test_db, service, plan_with_planned_journey):
    """receive_actual creates unmatched record when departure is >60 min from planned."""
    plan, journey = plan_with_planned_journey

    # Actual departure 90 minutes after planned departure (outside 60-min window)
    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 9, 31),
        actual_arrival=datetime(2025, 6, 1, 10, 0),
        actual_distance_miles=5.0,
        route_coordinates=[],
    )

    result = await service.receive_actual(data)

    assert result.journey_id is None
    assert result.match_status == MatchStatus.UNMATCHED


@pytest.mark.asyncio
async def test_receive_actual_unmatched_different_carer(test_db, service, plan_with_planned_journey):
    """receive_actual creates unmatched record when carer doesn't match planned journey."""
    plan, journey = plan_with_planned_journey

    data = ActualJourneyCreate(
        carer_id=2,  # Different carer than planned journey (carer_id=1)
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 5),
        actual_arrival=datetime(2025, 6, 1, 8, 35),
        actual_distance_miles=5.0,
        route_coordinates=[],
    )

    result = await service.receive_actual(data)

    assert result.journey_id is None
    assert result.match_status == MatchStatus.UNMATCHED


# --- State transition tests ---


@pytest.mark.asyncio
async def test_receive_actual_transitions_planned_to_in_progress(test_db, service, plan_with_planned_journey):
    """receive_actual transitions matched planned journey to in_progress."""
    plan, journey = plan_with_planned_journey

    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 5),
        actual_arrival=datetime(2025, 6, 1, 8, 35),
        actual_distance_miles=5.2,
        route_coordinates=[],
    )

    await service.receive_actual(data)

    # Check the planned journey's status has transitioned
    updated_journey = await get_journey(journey["id"])
    assert updated_journey["status"] == "in_progress"


@pytest.mark.asyncio
async def test_receive_actual_transitions_in_progress_to_completed(test_db, service, plan_with_planned_journey):
    """receive_actual transitions matched in_progress journey to completed."""
    plan, journey = plan_with_planned_journey
    # First set journey to in_progress
    await update_journey_status(journey["id"], "in_progress")

    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 5),
        actual_arrival=datetime(2025, 6, 1, 8, 35),
        actual_distance_miles=5.2,
        route_coordinates=[],
    )

    await service.receive_actual(data)

    # Check the planned journey's status has transitioned
    updated_journey = await get_journey(journey["id"])
    assert updated_journey["status"] == "completed"


# --- Data persistence tests ---


@pytest.mark.asyncio
async def test_receive_actual_persists_distance_to_one_decimal(test_db, service, plan_with_planned_journey):
    """receive_actual rounds actual_distance_miles to 1 decimal place."""
    plan, journey = plan_with_planned_journey

    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 5),
        actual_arrival=datetime(2025, 6, 1, 8, 35),
        actual_distance_miles=5.678,
        route_coordinates=[],
    )

    result = await service.receive_actual(data)

    assert result.actual_distance_miles == 5.7


@pytest.mark.asyncio
async def test_receive_actual_returns_correct_model(test_db, service, plan_with_planned_journey):
    """receive_actual returns a well-formed ActualJourneyModel."""
    plan, journey = plan_with_planned_journey

    data = ActualJourneyCreate(
        carer_id=1,
        operating_day=date(2025, 6, 1),
        actual_departure=datetime(2025, 6, 1, 8, 5),
        actual_arrival=datetime(2025, 6, 1, 8, 35),
        actual_distance_miles=5.0,
        route_coordinates=[[51.5, -0.1]],
    )

    result = await service.receive_actual(data)

    assert isinstance(result, ActualJourneyModel)
    assert result.id is not None
    assert result.carer_id == 1
    assert result.operating_day == "2025-06-01"
    assert result.actual_departure == "2025-06-01T08:05:00"
    assert result.actual_arrival == "2025-06-01T08:35:00"
    assert result.actual_distance_miles == 5.0
    assert result.route_coordinates == [[51.5, -0.1]]
    assert result.created_at is not None
