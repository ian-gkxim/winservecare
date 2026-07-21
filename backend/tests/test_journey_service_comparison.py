"""Tests for JourneyService.get_comparison method."""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db.journey_repository import (
    create_actual_journey,
    create_journey,
    create_journey_plan,
)
from backend.app.models.journey import (
    ComparisonResult,
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


@pytest_asyncio.fixture
async def service():
    """Create a JourneyService instance."""
    return JourneyService()


@pytest_asyncio.fixture
async def plan_with_journeys(test_db):
    """Create a plan with two journeys for two carers."""
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
        origin_lat=51.6,
        origin_lng=-0.2,
        origin_label="Home",
        destination_lat=51.7,
        destination_lng=-0.3,
        destination_label="Patient B",
        planned_departure="2025-06-01T09:00:00",
        planned_arrival="2025-06-01T09:45:00",
        planned_distance_miles=8.0,
    )
    return plan, j1, j2


# --- Empty comparison (Req 5.6) ---


@pytest.mark.asyncio
async def test_get_comparison_empty_no_data(test_db, service):
    """get_comparison returns empty result with message when no data exists."""
    result = await service.get_comparison(date(2025, 6, 1))

    assert isinstance(result, ComparisonResult)
    assert result.operating_day == "2025-06-01"
    assert result.plan_version == 0
    assert result.entries_by_carer == {}
    assert result.message is not None
    assert "no data" in result.message.lower()


# --- Basic matching (Req 5.1) ---


@pytest.mark.asyncio
async def test_get_comparison_matched_pair(test_db, service, plan_with_journeys):
    """get_comparison pairs planned journeys with matching actuals."""
    plan, j1, j2 = plan_with_journeys

    # Create matching actual for journey 1
    await create_actual_journey(
        journey_id=j1["id"],
        carer_id=1,
        operating_day="2025-06-01",
        actual_departure="2025-06-01T08:05:00",
        actual_arrival="2025-06-01T08:35:00",
        actual_distance_miles=5.3,
        route_coordinates=json.dumps([[51.5, -0.1], [51.6, -0.2]]),
        match_status="matched",
    )

    result = await service.get_comparison(date(2025, 6, 1))

    assert result.operating_day == "2025-06-01"
    assert result.plan_version == 1

    # Carer 1 should have one matched entry
    assert 1 in result.entries_by_carer
    carer1_entries = result.entries_by_carer[1]
    assert len(carer1_entries) == 1
    entry = carer1_entries[0]
    assert entry.match_status == MatchStatus.MATCHED
    assert entry.planned_journey is not None
    assert entry.actual_journey is not None
    assert entry.variance is not None

    # Carer 2 should have one unstarted entry
    assert 2 in result.entries_by_carer
    carer2_entries = result.entries_by_carer[2]
    assert len(carer2_entries) == 1
    assert carer2_entries[0].match_status == MatchStatus.UNSTARTED


# --- Variance calculation (Req 5.2, 5.3, 5.4) ---


@pytest.mark.asyncio
async def test_get_comparison_variance_calculation(test_db, service, plan_with_journeys):
    """get_comparison calculates correct variance values."""
    plan, j1, j2 = plan_with_journeys

    # Actual departs 10 min late, arrives 5 min late, travels 0.3 miles longer
    await create_actual_journey(
        journey_id=j1["id"],
        carer_id=1,
        operating_day="2025-06-01",
        actual_departure="2025-06-01T08:10:00",
        actual_arrival="2025-06-01T08:35:00",
        actual_distance_miles=5.3,
        route_coordinates=json.dumps([]),
        match_status="matched",
    )

    result = await service.get_comparison(date(2025, 6, 1))
    entry = result.entries_by_carer[1][0]

    assert entry.variance.departure_variance_minutes == 10  # 10 min late
    assert entry.variance.arrival_variance_minutes == 5  # 5 min late
    assert entry.variance.distance_variance_miles == 0.3  # 0.3 miles longer


@pytest.mark.asyncio
async def test_get_comparison_negative_variance(test_db, service, plan_with_journeys):
    """get_comparison calculates negative variance for early/shorter."""
    plan, j1, j2 = plan_with_journeys

    # Actual departs 5 min early, arrives 10 min early, travels 1.5 miles shorter
    await create_actual_journey(
        journey_id=j1["id"],
        carer_id=1,
        operating_day="2025-06-01",
        actual_departure="2025-06-01T07:55:00",
        actual_arrival="2025-06-01T08:20:00",
        actual_distance_miles=3.5,
        route_coordinates=json.dumps([]),
        match_status="matched",
    )

    result = await service.get_comparison(date(2025, 6, 1))
    entry = result.entries_by_carer[1][0]

    assert entry.variance.departure_variance_minutes == -5  # 5 min early
    assert entry.variance.arrival_variance_minutes == -10  # 10 min early
    assert entry.variance.distance_variance_miles == -1.5  # 1.5 miles shorter


# --- Unstarted entries (Req 5.5) ---


@pytest.mark.asyncio
async def test_get_comparison_unstarted_journey(test_db, service, plan_with_journeys):
    """get_comparison marks planned journeys without actuals as unstarted."""
    plan, j1, j2 = plan_with_journeys
    # No actuals created

    result = await service.get_comparison(date(2025, 6, 1))

    # Both journeys should be unstarted
    for carer_id in [1, 2]:
        entries = result.entries_by_carer[carer_id]
        assert len(entries) == 1
        entry = entries[0]
        assert entry.match_status == MatchStatus.UNSTARTED
        assert entry.planned_journey is not None
        assert entry.actual_journey is None
        assert entry.variance is None


# --- Unplanned entries (Req 5.5) ---


@pytest.mark.asyncio
async def test_get_comparison_unplanned_actual(test_db, service, plan_with_journeys):
    """get_comparison marks actuals without matching planned as unplanned."""
    plan, j1, j2 = plan_with_journeys

    # Create an actual with no matching journey_id (unmatched)
    await create_actual_journey(
        journey_id=None,
        carer_id=1,
        operating_day="2025-06-01",
        actual_departure="2025-06-01T14:00:00",
        actual_arrival="2025-06-01T14:30:00",
        actual_distance_miles=3.0,
        route_coordinates=json.dumps([]),
        match_status="unmatched",
    )

    result = await service.get_comparison(date(2025, 6, 1))

    # Carer 1 should have the planned unstarted entry + the unplanned actual
    carer1_entries = result.entries_by_carer[1]
    assert len(carer1_entries) == 2

    unplanned_entries = [e for e in carer1_entries if e.match_status == MatchStatus.UNPLANNED]
    assert len(unplanned_entries) == 1
    assert unplanned_entries[0].planned_journey is None
    assert unplanned_entries[0].actual_journey is not None
    assert unplanned_entries[0].variance is None


# --- Grouping by carer (Req 5.1) ---


@pytest.mark.asyncio
async def test_get_comparison_groups_by_carer(test_db, service, plan_with_journeys):
    """get_comparison groups results by carer_id."""
    plan, j1, j2 = plan_with_journeys

    result = await service.get_comparison(date(2025, 6, 1))

    # Should have entries for both carers
    assert 1 in result.entries_by_carer
    assert 2 in result.entries_by_carer

    # Each carer has exactly one entry
    assert len(result.entries_by_carer[1]) == 1
    assert len(result.entries_by_carer[2]) == 1


# --- Ordering by departure time (Req 5.1) ---


@pytest.mark.asyncio
async def test_get_comparison_orders_by_departure(test_db, service):
    """get_comparison orders entries within each carer group by planned departure."""
    plan = await create_journey_plan("2025-06-01", "initial_creation", 1)

    # Create journeys in reverse order to test ordering
    await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5, origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6, destination_lng=-0.2,
        destination_label="Patient B",
        planned_departure="2025-06-01T10:00:00",
        planned_arrival="2025-06-01T10:30:00",
        planned_distance_miles=5.0,
    )
    await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5, origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.7, destination_lng=-0.3,
        destination_label="Patient A",
        planned_departure="2025-06-01T08:00:00",
        planned_arrival="2025-06-01T08:30:00",
        planned_distance_miles=4.0,
    )

    result = await service.get_comparison(date(2025, 6, 1))

    carer1_entries = result.entries_by_carer[1]
    assert len(carer1_entries) == 2
    # Should be ordered 08:00 before 10:00
    assert carer1_entries[0].planned_journey.planned_departure == "2025-06-01T08:00:00"
    assert carer1_entries[1].planned_journey.planned_departure == "2025-06-01T10:00:00"


# --- Specific plan version (Req 5.7) ---


@pytest.mark.asyncio
async def test_get_comparison_specific_plan_version(test_db, service):
    """get_comparison uses specified plan version instead of latest."""
    # Create version 1
    plan_v1 = await create_journey_plan("2025-06-01", "initial_creation", 1)
    j1 = await create_journey(
        plan_id=plan_v1["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5, origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6, destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-06-01T08:00:00",
        planned_arrival="2025-06-01T08:30:00",
        planned_distance_miles=5.0,
    )

    # Create version 2
    plan_v2 = await create_journey_plan("2025-06-01", "manual_amendment", 2)
    j2 = await create_journey(
        plan_id=plan_v2["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5, origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.7, destination_lng=-0.3,
        destination_label="Patient B",
        planned_departure="2025-06-01T09:00:00",
        planned_arrival="2025-06-01T09:30:00",
        planned_distance_miles=6.0,
    )

    # Request comparison for version 1 specifically
    result = await service.get_comparison(date(2025, 6, 1), plan_version=1)

    assert result.plan_version == 1
    carer1_entries = result.entries_by_carer[1]
    assert len(carer1_entries) == 1
    # Should be the journey from version 1 (departure 08:00, distance 5.0)
    assert carer1_entries[0].planned_journey.planned_departure == "2025-06-01T08:00:00"
    assert carer1_entries[0].planned_journey.planned_distance_miles == 5.0


@pytest.mark.asyncio
async def test_get_comparison_uses_latest_version_by_default(test_db, service):
    """get_comparison uses latest plan version when no version specified."""
    # Create version 1
    plan_v1 = await create_journey_plan("2025-06-01", "initial_creation", 1)
    await create_journey(
        plan_id=plan_v1["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5, origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.6, destination_lng=-0.2,
        destination_label="Patient A",
        planned_departure="2025-06-01T08:00:00",
        planned_arrival="2025-06-01T08:30:00",
        planned_distance_miles=5.0,
    )

    # Create version 2
    plan_v2 = await create_journey_plan("2025-06-01", "manual_amendment", 2)
    await create_journey(
        plan_id=plan_v2["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5, origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.7, destination_lng=-0.3,
        destination_label="Patient B",
        planned_departure="2025-06-01T09:00:00",
        planned_arrival="2025-06-01T09:30:00",
        planned_distance_miles=6.0,
    )

    # Request comparison without specifying version
    result = await service.get_comparison(date(2025, 6, 1))

    assert result.plan_version == 2
    carer1_entries = result.entries_by_carer[1]
    assert len(carer1_entries) == 1
    # Should be the journey from version 2 (departure 09:00, distance 6.0)
    assert carer1_entries[0].planned_journey.planned_departure == "2025-06-01T09:00:00"
    assert carer1_entries[0].planned_journey.planned_distance_miles == 6.0


# --- Only actuals exist (no plan) ---


@pytest.mark.asyncio
async def test_get_comparison_only_actuals_no_plan(test_db, service):
    """get_comparison returns unplanned entries when actuals exist but no plan."""
    await create_actual_journey(
        journey_id=None,
        carer_id=1,
        operating_day="2025-06-01",
        actual_departure="2025-06-01T08:00:00",
        actual_arrival="2025-06-01T08:30:00",
        actual_distance_miles=4.5,
        route_coordinates=json.dumps([]),
        match_status="unmatched",
    )

    result = await service.get_comparison(date(2025, 6, 1))

    assert result.plan_version == 0
    assert result.message is None  # Not empty because actuals exist
    assert 1 in result.entries_by_carer
    entries = result.entries_by_carer[1]
    assert len(entries) == 1
    assert entries[0].match_status == MatchStatus.UNPLANNED
    assert entries[0].actual_journey is not None
    assert entries[0].planned_journey is None
