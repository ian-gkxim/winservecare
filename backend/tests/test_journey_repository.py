"""Tests for the journey repository layer."""

from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db.journey_repository import (
    archive_journey_plan,
    create_journey,
    create_journey_plan,
    get_archived_plans,
    get_journey,
    get_journey_plan,
    get_journeys_by_carer,
    get_journeys_by_plan,
    get_latest_plan_version,
    list_journey_plans,
    query_journeys,
    update_journey_status,
)


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and seed data."""
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


@pytest.mark.asyncio
async def test_create_journey_returns_dict_with_planned_status(test_db):
    """Creating a journey should return a dict with status 'planned'."""
    plan = await create_journey_plan("2025-03-01", "initial_creation", 1)

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
        planned_departure="2025-03-01T08:00:00",
        planned_arrival="2025-03-01T08:30:00",
        planned_distance_miles=5.2,
    )

    assert journey["status"] == "planned"
    assert journey["plan_id"] == plan["id"]
    assert journey["carer_id"] == 1
    assert journey["origin_lat"] == 51.5
    assert journey["destination_label"] == "Patient A"
    assert journey["planned_distance_miles"] == 5.2
    assert journey["id"] is not None


@pytest.mark.asyncio
async def test_get_journey_existing(test_db):
    """get_journey should return the journey dict for an existing ID."""
    plan = await create_journey_plan("2025-03-01", "initial_creation", 1)
    created = await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label=None,
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label=None,
        planned_departure="2025-03-01T09:00:00",
        planned_arrival="2025-03-01T09:20:00",
        planned_distance_miles=3.0,
    )

    result = await get_journey(created["id"])
    assert result is not None
    assert result["id"] == created["id"]
    assert result["carer_id"] == 1


@pytest.mark.asyncio
async def test_get_journey_nonexistent(test_db):
    """get_journey should return None for a non-existent ID."""
    result = await get_journey(9999)
    assert result is None


@pytest.mark.asyncio
async def test_update_journey_status(test_db):
    """update_journey_status should change status and updated_at."""
    plan = await create_journey_plan("2025-03-01", "initial_creation", 1)
    journey = await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label=None,
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label=None,
        planned_departure="2025-03-01T09:00:00",
        planned_arrival="2025-03-01T09:20:00",
        planned_distance_miles=3.0,
    )

    await update_journey_status(journey["id"], "in_progress")
    updated = await get_journey(journey["id"])
    assert updated["status"] == "in_progress"
    assert updated["updated_at"] != journey["updated_at"]


@pytest.mark.asyncio
async def test_update_journey_status_with_cancelled_at(test_db):
    """update_journey_status with cancelled_at should set both fields."""
    plan = await create_journey_plan("2025-03-01", "initial_creation", 1)
    journey = await create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=None,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label=None,
        destination_lat=51.6,
        destination_lng=-0.2,
        destination_label=None,
        planned_departure="2025-03-01T09:00:00",
        planned_arrival="2025-03-01T09:20:00",
        planned_distance_miles=3.0,
    )

    cancelled_time = "2025-03-01T10:00:00"
    await update_journey_status(journey["id"], "cancelled", cancelled_at=cancelled_time)
    updated = await get_journey(journey["id"])
    assert updated["status"] == "cancelled"
    assert updated["cancelled_at"] == cancelled_time


@pytest.mark.asyncio
async def test_update_journey_status_not_found(test_db):
    """update_journey_status should raise KeyError for non-existent ID."""
    with pytest.raises(KeyError):
        await update_journey_status(9999, "in_progress")


@pytest.mark.asyncio
async def test_get_journeys_by_plan_ordered(test_db):
    """get_journeys_by_plan should return journeys ordered by planned_departure."""
    plan = await create_journey_plan("2025-03-01", "initial_creation", 1)

    # Create journeys out of order
    await create_journey(
        plan_id=plan["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T10:00:00",
        planned_arrival="2025-03-01T10:30:00",
        planned_distance_miles=5.0,
    )
    await create_journey(
        plan_id=plan["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T08:00:00",
        planned_arrival="2025-03-01T08:30:00",
        planned_distance_miles=5.0,
    )

    journeys = await get_journeys_by_plan(plan["id"])
    assert len(journeys) == 2
    assert journeys[0]["planned_departure"] < journeys[1]["planned_departure"]


@pytest.mark.asyncio
async def test_query_journeys_with_filters(test_db):
    """query_journeys should filter by operating_day, carer_id, and status."""
    plan = await create_journey_plan("2025-03-01", "initial_creation", 1)

    await create_journey(
        plan_id=plan["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T08:00:00",
        planned_arrival="2025-03-01T08:30:00",
        planned_distance_miles=5.0,
    )
    await create_journey(
        plan_id=plan["id"], carer_id=2, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T09:00:00",
        planned_arrival="2025-03-01T09:30:00",
        planned_distance_miles=3.0,
    )

    # Filter by carer_id
    results, total = await query_journeys(carer_id=2)
    assert total == 1
    assert results[0]["carer_id"] == 2

    # Filter by operating_day
    results, total = await query_journeys(operating_day="2025-03-01")
    assert total == 2

    # Filter by non-existent day
    results, total = await query_journeys(operating_day="2025-04-01")
    assert total == 0


@pytest.mark.asyncio
async def test_query_journeys_pagination(test_db):
    """query_journeys should paginate correctly."""
    plan = await create_journey_plan("2025-03-01", "initial_creation", 1)

    for i in range(5):
        await create_journey(
            plan_id=plan["id"], carer_id=1, visit_id=None,
            origin_lat=51.5, origin_lng=-0.1, origin_label=None,
            destination_lat=51.6, destination_lng=-0.2, destination_label=None,
            planned_departure=f"2025-03-01T{8+i:02d}:00:00",
            planned_arrival=f"2025-03-01T{8+i:02d}:30:00",
            planned_distance_miles=3.0,
        )

    results, total = await query_journeys(page=1, page_size=2)
    assert total == 5
    assert len(results) == 2

    results, total = await query_journeys(page=3, page_size=2)
    assert total == 5
    assert len(results) == 1  # last page has 1 item


@pytest.mark.asyncio
async def test_query_journeys_uses_latest_plan_version(test_db):
    """query_journeys should only return journeys from the latest plan version."""
    plan_v1 = await create_journey_plan("2025-03-01", "initial_creation", 1)
    plan_v2 = await create_journey_plan("2025-03-01", "manual_amendment", 2)

    await create_journey(
        plan_id=plan_v1["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T08:00:00",
        planned_arrival="2025-03-01T08:30:00",
        planned_distance_miles=5.0,
    )
    await create_journey(
        plan_id=plan_v2["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T09:00:00",
        planned_arrival="2025-03-01T09:30:00",
        planned_distance_miles=4.0,
    )

    results, total = await query_journeys(operating_day="2025-03-01")
    assert total == 1
    assert results[0]["plan_id"] == plan_v2["id"]


@pytest.mark.asyncio
async def test_get_journeys_by_carer(test_db):
    """get_journeys_by_carer should return journeys from latest plan, ordered DESC."""
    plan = await create_journey_plan("2025-03-01", "initial_creation", 1)

    await create_journey(
        plan_id=plan["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T08:00:00",
        planned_arrival="2025-03-01T08:30:00",
        planned_distance_miles=5.0,
    )
    await create_journey(
        plan_id=plan["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T10:00:00",
        planned_arrival="2025-03-01T10:30:00",
        planned_distance_miles=3.0,
    )
    # Different carer - should not appear
    await create_journey(
        plan_id=plan["id"], carer_id=2, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T09:00:00",
        planned_arrival="2025-03-01T09:30:00",
        planned_distance_miles=4.0,
    )

    results = await get_journeys_by_carer(1)
    assert len(results) == 2
    # DESC ordering
    assert results[0]["planned_departure"] > results[1]["planned_departure"]
    # Only carer 1
    for r in results:
        assert r["carer_id"] == 1


@pytest.mark.asyncio
async def test_get_journeys_by_carer_uses_latest_plan(test_db):
    """get_journeys_by_carer should only use the latest non-archived plan per day."""
    plan_v1 = await create_journey_plan("2025-03-01", "initial_creation", 1)
    plan_v2 = await create_journey_plan("2025-03-01", "manual_amendment", 2)

    # Journey in old plan
    await create_journey(
        plan_id=plan_v1["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T08:00:00",
        planned_arrival="2025-03-01T08:30:00",
        planned_distance_miles=5.0,
    )
    # Journey in latest plan
    await create_journey(
        plan_id=plan_v2["id"], carer_id=1, visit_id=None,
        origin_lat=51.5, origin_lng=-0.1, origin_label=None,
        destination_lat=51.6, destination_lng=-0.2, destination_label=None,
        planned_departure="2025-03-01T09:00:00",
        planned_arrival="2025-03-01T09:30:00",
        planned_distance_miles=4.0,
    )

    results = await get_journeys_by_carer(1)
    assert len(results) == 1
    assert results[0]["plan_id"] == plan_v2["id"]


# --- Journey Plan CRUD tests ---


@pytest.mark.asyncio
async def test_create_journey_plan_returns_complete_dict(test_db):
    """create_journey_plan should return a dict with all expected fields."""
    plan = await create_journey_plan("2025-04-01", "initial_creation", 1)

    assert plan["id"] is not None
    assert plan["operating_day"] == "2025-04-01"
    assert plan["plan_version"] == 1
    assert plan["creation_reason"] == "initial_creation"
    assert plan["is_archived"] == 0
    assert plan["archived_at"] is None
    assert plan["created_at"] is not None


@pytest.mark.asyncio
async def test_get_journey_plan_existing(test_db):
    """get_journey_plan should return the plan dict for an existing ID."""
    created = await create_journey_plan("2025-04-01", "initial_creation", 1)

    result = await get_journey_plan(created["id"])
    assert result is not None
    assert result["id"] == created["id"]
    assert result["operating_day"] == "2025-04-01"
    assert result["plan_version"] == 1
    assert result["creation_reason"] == "initial_creation"


@pytest.mark.asyncio
async def test_get_journey_plan_nonexistent(test_db):
    """get_journey_plan should return None for a non-existent ID."""
    result = await get_journey_plan(9999)
    assert result is None


@pytest.mark.asyncio
async def test_list_journey_plans_excludes_archived_by_default(test_db):
    """list_journey_plans should not return archived plans by default."""
    plan1 = await create_journey_plan("2025-04-01", "initial_creation", 1)
    plan2 = await create_journey_plan("2025-04-02", "initial_creation", 1)

    # Archive plan2
    await archive_journey_plan(plan2["id"], "2025-04-10T12:00:00Z")

    plans = await list_journey_plans()
    assert len(plans) == 1
    assert plans[0]["id"] == plan1["id"]


@pytest.mark.asyncio
async def test_list_journey_plans_include_archived(test_db):
    """list_journey_plans with include_archived=True should return all plans."""
    await create_journey_plan("2025-04-01", "initial_creation", 1)
    plan2 = await create_journey_plan("2025-04-02", "initial_creation", 1)

    await archive_journey_plan(plan2["id"], "2025-04-10T12:00:00Z")

    plans = await list_journey_plans(include_archived=True)
    assert len(plans) == 2


@pytest.mark.asyncio
async def test_list_journey_plans_filter_by_operating_day(test_db):
    """list_journey_plans should filter by operating_day when specified."""
    await create_journey_plan("2025-04-01", "initial_creation", 1)
    await create_journey_plan("2025-04-02", "initial_creation", 1)

    plans = await list_journey_plans(operating_day="2025-04-01")
    assert len(plans) == 1
    assert plans[0]["operating_day"] == "2025-04-01"


@pytest.mark.asyncio
async def test_get_latest_plan_version_returns_max(test_db):
    """get_latest_plan_version should return the highest version for a day."""
    await create_journey_plan("2025-04-01", "initial_creation", 1)
    await create_journey_plan("2025-04-01", "manual_amendment", 2)
    await create_journey_plan("2025-04-01", "re_optimisation", 3)

    version = await get_latest_plan_version("2025-04-01")
    assert version == 3


@pytest.mark.asyncio
async def test_get_latest_plan_version_returns_zero_when_none(test_db):
    """get_latest_plan_version should return 0 for a day with no plans."""
    version = await get_latest_plan_version("2099-12-31")
    assert version == 0


@pytest.mark.asyncio
async def test_archive_journey_plan_sets_fields(test_db):
    """archive_journey_plan should set is_archived=1 and archived_at."""
    plan = await create_journey_plan("2025-04-01", "initial_creation", 1)
    timestamp = "2025-04-10T14:30:00Z"

    result = await archive_journey_plan(plan["id"], timestamp)
    assert result is True

    # Verify the plan is archived
    updated = await get_journey_plan(plan["id"])
    assert updated["is_archived"] == 1
    assert updated["archived_at"] == timestamp


@pytest.mark.asyncio
async def test_archive_journey_plan_nonexistent(test_db):
    """archive_journey_plan should return False for a non-existent plan."""
    result = await archive_journey_plan(9999, "2025-04-10T14:30:00Z")
    assert result is False


@pytest.mark.asyncio
async def test_get_archived_plans_returns_only_archived(test_db):
    """get_archived_plans should return only plans with is_archived=1."""
    plan1 = await create_journey_plan("2025-04-01", "initial_creation", 1)
    plan2 = await create_journey_plan("2025-04-02", "initial_creation", 1)

    await archive_journey_plan(plan2["id"], "2025-04-10T12:00:00Z")

    archived = await get_archived_plans()
    assert len(archived) == 1
    assert archived[0]["id"] == plan2["id"]
    assert archived[0]["is_archived"] == 1


@pytest.mark.asyncio
async def test_get_archived_plans_filter_by_operating_day(test_db):
    """get_archived_plans should filter by operating_day."""
    plan1 = await create_journey_plan("2025-04-01", "initial_creation", 1)
    plan2 = await create_journey_plan("2025-04-02", "initial_creation", 1)

    await archive_journey_plan(plan1["id"], "2025-04-10T12:00:00Z")
    await archive_journey_plan(plan2["id"], "2025-04-10T12:00:00Z")

    # Filter for just one day
    archived = await get_archived_plans(operating_day="2025-04-01")
    assert len(archived) == 1
    assert archived[0]["operating_day"] == "2025-04-01"
