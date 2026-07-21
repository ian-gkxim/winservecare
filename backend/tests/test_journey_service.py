"""Unit tests for JourneyService edge cases.

Tests cover:
- 4-hour overdue timeout (Req 4.7)
- Unmatched actual creates exception entry (Req 4.4)
- Empty comparison message (Req 5.6)
- Specific plan version comparison (Req 5.7)
- Today's only plan deletion rejected (Req 3.4)
- Empty query results (Req 8.7)
"""

import json
from datetime import date, datetime, timedelta, timezone
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
    get_journey,
    update_journey_status,
)
from backend.app.models.journey import (
    ActualJourneyCreate,
    ComparisonResult,
    JourneyFilters,
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
                   VALUES (1, 'Carer One', 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)"""
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


# --- Req 4.7: 4-hour overdue timeout ---


@pytest.mark.asyncio
async def test_overdue_timeout_flags_in_progress_journey(test_db, service):
    """A journey in_progress for >4 hours should be flagged as overdue (Req 4.7)."""
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

    # Set the journey to in_progress
    await update_journey_status(journey["id"], "in_progress")

    # Create an actual journey with departure 5 hours ago
    five_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    await create_actual_journey(
        journey_id=journey["id"],
        carer_id=1,
        operating_day="2025-06-01",
        actual_departure=five_hours_ago,
        actual_arrival=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        actual_distance_miles=5.0,
        route_coordinates=json.dumps([]),
        match_status="matched",
    )

    # Run the overdue check
    flagged_ids = await service.check_overdue_journeys()

    # The journey should be flagged as overdue
    assert journey["id"] in flagged_ids

    # Verify the journey status is now overdue
    updated = await get_journey(journey["id"])
    assert updated["status"] == "overdue"


@pytest.mark.asyncio
async def test_overdue_timeout_does_not_flag_recent_journey(test_db, service):
    """A journey in_progress for <4 hours should NOT be flagged as overdue (Req 4.7)."""
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

    # Set the journey to in_progress
    await update_journey_status(journey["id"], "in_progress")

    # Create an actual journey with departure 2 hours ago (within threshold)
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    await create_actual_journey(
        journey_id=journey["id"],
        carer_id=1,
        operating_day="2025-06-01",
        actual_departure=two_hours_ago,
        actual_arrival=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        actual_distance_miles=5.0,
        route_coordinates=json.dumps([]),
        match_status="matched",
    )

    # Run the overdue check
    flagged_ids = await service.check_overdue_journeys()

    # The journey should NOT be flagged
    assert journey["id"] not in flagged_ids

    # Verify the journey status is still in_progress
    updated = await get_journey(journey["id"])
    assert updated["status"] == "in_progress"


# --- Req 4.4: Unmatched actual creates exception entry ---


@pytest.mark.asyncio
async def test_unmatched_actual_creates_unmatched_record(test_db, service):
    """Actual data with no matching planned journey creates unmatched entry (Req 4.4)."""
    # No planned journeys exist for this date/carer
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


# --- Req 5.6: Empty comparison message ---


@pytest.mark.asyncio
async def test_empty_comparison_returns_message(test_db, service):
    """Comparison for a day with no data returns empty result with message (Req 5.6)."""
    result = await service.get_comparison(date(2025, 6, 15))

    assert isinstance(result, ComparisonResult)
    assert result.operating_day == "2025-06-15"
    assert result.plan_version == 0
    assert result.entries_by_carer == {}
    assert result.message is not None
    assert "no data" in result.message.lower()


# --- Req 5.7: Specific plan version comparison ---


@pytest.mark.asyncio
async def test_specific_plan_version_comparison(test_db, service):
    """Comparison with specific plan_version uses that version's journeys (Req 5.7)."""
    # Create version 1
    plan_v1 = await create_journey_plan("2025-06-01", "initial_creation", 1)
    await create_journey(
        plan_id=plan_v1["id"],
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

    # Create version 2 with different journeys
    plan_v2 = await create_journey_plan("2025-06-01", "manual_amendment", 2)
    await create_journey(
        plan_id=plan_v2["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.7,
        destination_lng=-0.3,
        destination_label="Patient B",
        planned_departure="2025-06-01T09:00:00",
        planned_arrival="2025-06-01T09:30:00",
        planned_distance_miles=6.0,
    )

    # Request comparison for version 1
    result = await service.get_comparison(date(2025, 6, 1), plan_version=1)

    assert result.plan_version == 1
    carer1_entries = result.entries_by_carer[1]
    assert len(carer1_entries) == 1
    assert carer1_entries[0].planned_journey.planned_departure == "2025-06-01T08:00:00"
    assert carer1_entries[0].planned_journey.planned_distance_miles == 5.0


# --- Req 3.4: Today's only plan deletion rejected ---


@pytest.mark.asyncio
async def test_todays_only_plan_deletion_rejected(test_db, service):
    """Deleting the only plan for today should raise 409 (Req 3.4)."""
    today = date.today().isoformat()
    plan = await create_journey_plan(today, "initial_creation", 1)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_plan(plan_id=plan["id"])

    assert exc_info.value.status_code == 409
    assert "active day plan" in exc_info.value.detail.lower()


# --- Req 8.7: Empty query results ---


@pytest.mark.asyncio
async def test_empty_query_results(test_db, service):
    """Query with filters that match nothing returns total_count=0 and empty list (Req 8.7)."""
    filters = JourneyFilters()
    result = await service.query_journeys(filters, page=1, page_size=20)

    assert result.total_count == 0
    assert result.page == 1
    assert result.page_size == 20
    assert result.journeys == []
