"""Tests for JourneyService.query_journeys method."""

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
    update_journey_status,
)
from backend.app.models.journey import JourneyFilters, JourneyStatus
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
                   VALUES (1, 'Test Carer 1', 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)"""
            )
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (2, 'Test Carer 2', 51.6, -0.2, '["driving"]', 8.0, 6.0, 30)"""
            )
            await db.commit()

        yield


@pytest.fixture
def service():
    """Create a JourneyService instance."""
    return JourneyService()


async def _create_test_journey(plan_id, carer_id=1, departure="2025-09-01T09:00:00", arrival="2025-09-01T09:30:00"):
    """Helper to create a test journey with minimal params."""
    return await create_journey(
        plan_id=plan_id,
        carer_id=carer_id,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Origin",
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label="Destination",
        planned_departure=departure,
        planned_arrival=arrival,
        planned_distance_miles=3.5,
    )


# --- Pagination validation tests ---


@pytest.mark.asyncio
async def test_query_page_less_than_one(test_db, service):
    """Page < 1 should raise 422."""
    filters = JourneyFilters()
    with pytest.raises(HTTPException) as exc_info:
        await service.query_journeys(filters, page=0, page_size=20)
    assert exc_info.value.status_code == 422
    assert "page" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_query_page_size_less_than_one(test_db, service):
    """Page size < 1 should raise 422."""
    filters = JourneyFilters()
    with pytest.raises(HTTPException) as exc_info:
        await service.query_journeys(filters, page=1, page_size=0)
    assert exc_info.value.status_code == 422
    assert "page size" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_query_page_size_exceeds_max(test_db, service):
    """Page size > 100 should raise 422."""
    filters = JourneyFilters()
    with pytest.raises(HTTPException) as exc_info:
        await service.query_journeys(filters, page=1, page_size=101)
    assert exc_info.value.status_code == 422
    assert "page size" in exc_info.value.detail.lower()


# --- Filter validation tests ---


@pytest.mark.asyncio
async def test_query_invalid_carer_id(test_db, service):
    """Non-existent carer_id should raise 422."""
    filters = JourneyFilters(carer_id=9999)
    with pytest.raises(HTTPException) as exc_info:
        await service.query_journeys(filters, page=1, page_size=20)
    assert exc_info.value.status_code == 422
    assert "carer_id" in exc_info.value.detail.lower()


# --- Successful query tests ---


@pytest.mark.asyncio
async def test_query_empty_result(test_db, service):
    """Query with no matching journeys returns empty result with total_count=0."""
    filters = JourneyFilters()
    result = await service.query_journeys(filters, page=1, page_size=20)

    assert result.total_count == 0
    assert result.page == 1
    assert result.page_size == 20
    assert result.journeys == []


@pytest.mark.asyncio
async def test_query_returns_journeys_from_latest_plan(test_db, service):
    """Query returns journeys from the latest plan version only."""
    future_day = (date.today() + timedelta(days=5)).isoformat()

    # Create two plan versions for the same operating day
    plan1 = await create_journey_plan(future_day, "initial_creation", 1)
    plan2 = await create_journey_plan(future_day, "manual_amendment", 2)

    # Add journeys to both plans
    await _create_test_journey(plan1["id"], carer_id=1, departure="2025-09-01T08:00:00")
    await _create_test_journey(plan2["id"], carer_id=1, departure="2025-09-01T09:00:00")

    filters = JourneyFilters()
    result = await service.query_journeys(filters, page=1, page_size=20)

    # Should only return the journey from plan2 (latest version)
    assert result.total_count == 1
    assert result.journeys[0].plan_id == plan2["id"]


@pytest.mark.asyncio
async def test_query_filter_by_operating_day(test_db, service):
    """Filtering by operating_day returns only journeys for that day."""
    day1 = (date.today() + timedelta(days=5)).isoformat()
    day2 = (date.today() + timedelta(days=6)).isoformat()

    plan1 = await create_journey_plan(day1, "initial_creation", 1)
    plan2 = await create_journey_plan(day2, "initial_creation", 1)

    await _create_test_journey(plan1["id"], carer_id=1)
    await _create_test_journey(plan2["id"], carer_id=1)

    filters = JourneyFilters(operating_day=date.today() + timedelta(days=5))
    result = await service.query_journeys(filters, page=1, page_size=20)

    assert result.total_count == 1
    assert result.journeys[0].plan_id == plan1["id"]


@pytest.mark.asyncio
async def test_query_filter_by_carer_id(test_db, service):
    """Filtering by carer_id returns only that carer's journeys."""
    future_day = (date.today() + timedelta(days=5)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)

    await _create_test_journey(plan["id"], carer_id=1, departure="2025-09-01T09:00:00")
    await _create_test_journey(plan["id"], carer_id=2, departure="2025-09-01T10:00:00")

    filters = JourneyFilters(carer_id=1)
    result = await service.query_journeys(filters, page=1, page_size=20)

    assert result.total_count == 1
    assert result.journeys[0].carer_id == 1


@pytest.mark.asyncio
async def test_query_filter_by_status(test_db, service):
    """Filtering by status returns only matching journeys."""
    future_day = (date.today() + timedelta(days=5)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)

    j1 = await _create_test_journey(plan["id"], carer_id=1, departure="2025-09-01T09:00:00")
    await _create_test_journey(plan["id"], carer_id=1, departure="2025-09-01T10:00:00")

    # Set one journey to in_progress
    await update_journey_status(j1["id"], "in_progress")

    filters = JourneyFilters(status=JourneyStatus.IN_PROGRESS)
    result = await service.query_journeys(filters, page=1, page_size=20)

    assert result.total_count == 1
    assert result.journeys[0].status == JourneyStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_query_multiple_filters_intersection(test_db, service):
    """Multiple filters are applied as intersection (AND)."""
    future_day = (date.today() + timedelta(days=5)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)

    # Carer 1 with planned status
    await _create_test_journey(plan["id"], carer_id=1, departure="2025-09-01T09:00:00")
    # Carer 2 with planned status
    await _create_test_journey(plan["id"], carer_id=2, departure="2025-09-01T10:00:00")

    # Filter by carer_id=1 AND status=planned
    filters = JourneyFilters(carer_id=1, status=JourneyStatus.PLANNED)
    result = await service.query_journeys(filters, page=1, page_size=20)

    assert result.total_count == 1
    assert result.journeys[0].carer_id == 1
    assert result.journeys[0].status == JourneyStatus.PLANNED


@pytest.mark.asyncio
async def test_query_pagination(test_db, service):
    """Pagination correctly slices the result set."""
    future_day = (date.today() + timedelta(days=5)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)

    # Create 5 journeys
    for i in range(5):
        await _create_test_journey(
            plan["id"],
            carer_id=1,
            departure=f"2025-09-01T{9+i:02d}:00:00",
            arrival=f"2025-09-01T{9+i:02d}:30:00",
        )

    # Get page 1 with page_size=2
    filters = JourneyFilters()
    result = await service.query_journeys(filters, page=1, page_size=2)

    assert result.total_count == 5
    assert result.page == 1
    assert result.page_size == 2
    assert len(result.journeys) == 2

    # Get page 3 with page_size=2 (should have 1 result)
    result = await service.query_journeys(filters, page=3, page_size=2)

    assert result.total_count == 5
    assert len(result.journeys) == 1


@pytest.mark.asyncio
async def test_query_orders_by_departure_descending(test_db, service):
    """Results are ordered by planned departure descending."""
    future_day = (date.today() + timedelta(days=5)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)

    await _create_test_journey(plan["id"], carer_id=1, departure="2025-09-01T08:00:00", arrival="2025-09-01T08:30:00")
    await _create_test_journey(plan["id"], carer_id=1, departure="2025-09-01T12:00:00", arrival="2025-09-01T12:30:00")
    await _create_test_journey(plan["id"], carer_id=1, departure="2025-09-01T10:00:00", arrival="2025-09-01T10:30:00")

    filters = JourneyFilters()
    result = await service.query_journeys(filters, page=1, page_size=20)

    assert result.total_count == 3
    # Should be ordered descending: 12:00, 10:00, 08:00
    departures = [j.planned_departure for j in result.journeys]
    assert departures == sorted(departures, reverse=True)


@pytest.mark.asyncio
async def test_query_excludes_archived_plans(test_db, service):
    """Journeys from archived plans should not appear in query results."""
    from backend.app.db.journey_repository import archive_journey_plan

    future_day = (date.today() + timedelta(days=5)).isoformat()
    plan1 = await create_journey_plan(future_day, "initial_creation", 1)
    await _create_test_journey(plan1["id"], carer_id=1)

    # Archive the plan
    await archive_journey_plan(plan1["id"], "2025-01-01T00:00:00Z")

    filters = JourneyFilters()
    result = await service.query_journeys(filters, page=1, page_size=20)

    assert result.total_count == 0
    assert result.journeys == []


@pytest.mark.asyncio
async def test_query_page_beyond_results(test_db, service):
    """Requesting a page beyond available results returns empty journeys list."""
    future_day = (date.today() + timedelta(days=5)).isoformat()
    plan = await create_journey_plan(future_day, "initial_creation", 1)
    await _create_test_journey(plan["id"], carer_id=1)

    filters = JourneyFilters()
    result = await service.query_journeys(filters, page=100, page_size=20)

    assert result.total_count == 1
    assert result.journeys == []
    assert result.page == 100
