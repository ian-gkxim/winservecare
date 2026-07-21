"""Tests for JourneyService.get_history and get_date_range_summary methods."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio
from fastapi import HTTPException

from backend.app.db import database
from backend.app.db.journey_repository import (
    create_actual_journey,
    create_journey,
    create_journey_plan,
    archive_journey_plan,
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


@pytest.fixture
def service():
    """Create a JourneyService instance."""
    return JourneyService()


# --- get_history tests ---


@pytest.mark.asyncio
async def test_get_history_empty_day(test_db, service):
    """Requesting history for a day with no plans returns empty list."""
    result = await service.get_history(date(2025, 6, 15))
    assert result == []


@pytest.mark.asyncio
async def test_get_history_single_version(test_db, service):
    """Requesting history for a day with one plan returns that plan."""
    day = date(2025, 7, 1)
    plan = await create_journey_plan(day.isoformat(), "initial_creation", 1)
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
        planned_departure="2025-07-01T09:00:00",
        planned_arrival="2025-07-01T09:30:00",
        planned_distance_miles=3.5,
    )

    result = await service.get_history(day)

    assert len(result) == 1
    assert result[0].plan_version == 1
    assert result[0].creation_reason.value == "initial_creation"
    assert len(result[0].journeys) == 1


@pytest.mark.asyncio
async def test_get_history_multiple_versions_chronological(test_db, service):
    """History returns all versions ordered by plan_version ascending."""
    day = date(2025, 7, 2)
    plan1 = await create_journey_plan(day.isoformat(), "initial_creation", 1)
    plan2 = await create_journey_plan(day.isoformat(), "manual_amendment", 2)
    plan3 = await create_journey_plan(day.isoformat(), "re_optimisation", 3)

    # Add a journey to each plan
    for plan in [plan1, plan2, plan3]:
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
            planned_departure="2025-07-02T09:00:00",
            planned_arrival="2025-07-02T09:30:00",
            planned_distance_miles=3.5,
        )

    result = await service.get_history(day)

    assert len(result) == 3
    assert result[0].plan_version == 1
    assert result[1].plan_version == 2
    assert result[2].plan_version == 3
    assert result[0].creation_reason.value == "initial_creation"
    assert result[1].creation_reason.value == "manual_amendment"
    assert result[2].creation_reason.value == "re_optimisation"


@pytest.mark.asyncio
async def test_get_history_includes_archived(test_db, service):
    """History includes archived (soft-deleted) plan versions."""
    day = date(2025, 7, 3)
    plan1 = await create_journey_plan(day.isoformat(), "initial_creation", 1)
    plan2 = await create_journey_plan(day.isoformat(), "manual_amendment", 2)

    # Archive plan1
    await archive_journey_plan(plan1["id"], "2025-07-03T12:00:00Z")

    result = await service.get_history(day)

    assert len(result) == 2
    assert result[0].plan_version == 1
    assert result[0].is_archived is True
    assert result[1].plan_version == 2
    assert result[1].is_archived is False


# --- get_date_range_summary tests ---


@pytest.mark.asyncio
async def test_date_range_summary_start_after_end(test_db, service):
    """Start date after end date should raise 422."""
    with pytest.raises(HTTPException) as exc_info:
        await service.get_date_range_summary(
            start=date(2025, 7, 10),
            end=date(2025, 7, 5),
        )

    assert exc_info.value.status_code == 422
    assert "start date" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_date_range_summary_exceeds_90_days(test_db, service):
    """Date range exceeding 90 days should raise 422."""
    with pytest.raises(HTTPException) as exc_info:
        await service.get_date_range_summary(
            start=date(2025, 1, 1),
            end=date(2025, 5, 1),  # 120 days
        )

    assert exc_info.value.status_code == 422
    assert "90 days" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_date_range_summary_exactly_90_days(test_db, service):
    """Date range of exactly 90 days should succeed."""
    start = date(2025, 1, 1)
    end = start + timedelta(days=90)

    # No data, so should return empty list
    result = await service.get_date_range_summary(start=start, end=end)
    assert result == []


@pytest.mark.asyncio
async def test_date_range_summary_empty_range(test_db, service):
    """Date range with no data returns empty list."""
    result = await service.get_date_range_summary(
        start=date(2025, 8, 1),
        end=date(2025, 8, 5),
    )
    assert result == []


@pytest.mark.asyncio
async def test_date_range_summary_with_data(test_db, service):
    """Summary returns correct stats for days with data."""
    day = date(2025, 7, 10)
    day_str = day.isoformat()

    # Create two plan versions
    plan1 = await create_journey_plan(day_str, "initial_creation", 1)
    plan2 = await create_journey_plan(day_str, "manual_amendment", 2)

    # Add journeys to the latest plan (plan2)
    j1 = await create_journey(
        plan_id=plan2["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-07-10T09:00:00",
        planned_arrival="2025-07-10T09:30:00",
        planned_distance_miles=3.5,
    )
    j2 = await create_journey(
        plan_id=plan2["id"],
        carer_id=2,
        visit_id=None,
        origin_lat=51.6,
        origin_lng=-0.2,
        origin_label="Home B",
        destination_lat=51.7,
        destination_lng=-0.3,
        destination_label="Patient B",
        planned_departure="2025-07-10T10:00:00",
        planned_arrival="2025-07-10T10:25:00",
        planned_distance_miles=2.8,
    )

    # Create actual journeys matched to planned
    await create_actual_journey(
        journey_id=j1["id"],
        carer_id=1,
        operating_day=day_str,
        actual_departure="2025-07-10T09:05:00",  # 5 min late
        actual_arrival="2025-07-10T09:35:00",
        actual_distance_miles=4.0,  # +0.5 miles
        route_coordinates="[]",
        match_status="matched",
    )
    await create_actual_journey(
        journey_id=j2["id"],
        carer_id=2,
        operating_day=day_str,
        actual_departure="2025-07-10T09:55:00",  # 5 min early
        actual_arrival="2025-07-10T10:20:00",
        actual_distance_miles=3.0,  # +0.2 miles
        route_coordinates="[]",
        match_status="matched",
    )

    result = await service.get_date_range_summary(
        start=day,
        end=day,
    )

    assert len(result) == 1
    summary = result[0]
    assert summary.operating_day == day_str
    assert summary.plan_version_count == 2
    assert summary.total_planned_journeys == 2
    assert summary.total_completed_journeys == 2
    # avg departure variance: (5 + (-5)) / 2 = 0.0
    assert summary.avg_departure_variance_minutes == 0.0
    # avg distance variance: (0.5 + 0.2) / 2 = 0.35 → rounded to 0.4
    assert summary.avg_distance_variance_miles == 0.4


@pytest.mark.asyncio
async def test_date_range_summary_no_matched_actuals(test_db, service):
    """Summary with no matched actuals returns None for variance fields."""
    day = date(2025, 7, 11)
    day_str = day.isoformat()

    plan = await create_journey_plan(day_str, "initial_creation", 1)
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
        planned_departure="2025-07-11T09:00:00",
        planned_arrival="2025-07-11T09:30:00",
        planned_distance_miles=3.5,
    )

    result = await service.get_date_range_summary(start=day, end=day)

    assert len(result) == 1
    summary = result[0]
    assert summary.plan_version_count == 1
    assert summary.total_planned_journeys == 1
    assert summary.total_completed_journeys == 0
    assert summary.avg_departure_variance_minutes is None
    assert summary.avg_distance_variance_miles is None


@pytest.mark.asyncio
async def test_date_range_summary_multi_day(test_db, service):
    """Summary returns entries only for days that have data."""
    day1 = date(2025, 7, 15)
    day3 = date(2025, 7, 17)

    # Data only on day1 and day3, not day2
    plan1 = await create_journey_plan(day1.isoformat(), "initial_creation", 1)
    await create_journey(
        plan_id=plan1["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-07-15T09:00:00",
        planned_arrival="2025-07-15T09:30:00",
        planned_distance_miles=3.5,
    )

    plan3 = await create_journey_plan(day3.isoformat(), "initial_creation", 1)
    await create_journey(
        plan_id=plan3["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-07-17T09:00:00",
        planned_arrival="2025-07-17T09:30:00",
        planned_distance_miles=3.5,
    )

    result = await service.get_date_range_summary(
        start=day1,
        end=day3,
    )

    assert len(result) == 2
    assert result[0].operating_day == day1.isoformat()
    assert result[1].operating_day == day3.isoformat()


@pytest.mark.asyncio
async def test_date_range_summary_single_day(test_db, service):
    """Summary works when start == end (single day)."""
    day = date(2025, 7, 20)
    plan = await create_journey_plan(day.isoformat(), "initial_creation", 1)
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
        planned_departure="2025-07-20T09:00:00",
        planned_arrival="2025-07-20T09:30:00",
        planned_distance_miles=3.5,
    )

    result = await service.get_date_range_summary(start=day, end=day)

    assert len(result) == 1
    assert result[0].operating_day == day.isoformat()
    assert result[0].plan_version_count == 1
