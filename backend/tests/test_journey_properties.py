"""Property-based tests for Journey Lifecycle Management — Modification State Rules.

Uses Hypothesis to verify correctness properties 5-8 of the journey service.

Feature: journey-lifecycle-management
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from backend.app.db import database
from backend.app.db.journey_repository import (
    create_journey,
    create_journey_plan,
    get_journey,
    get_journey_plan,
    get_journeys_by_plan,
    get_latest_plan_version,
    list_journey_plans,
    update_journey_status,
)
from backend.app.models.journey import (
    JourneyUpdate,
    PlanCreationReason,
)
from backend.app.services.journey_service import JourneyService


# ---------------------------------------------------------------------------
# Database helper — creates a fresh isolated DB for each Hypothesis example
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
_SCHEMA_SQL = _SCHEMA_PATH.read_text(encoding="utf-8")


class _FreshDB:
    """Context manager that patches the database module to use a fresh temp DB."""

    def __init__(self, tmp_dir):
        self._tmp_dir = tmp_dir

    async def setup(self):
        """Create a new database and patch the module-level path."""
        db_path = self._tmp_dir / f"test_{uuid.uuid4().hex}.db"

        self._patch_path = patch.object(database, "DB_PATH", db_path)
        self._patch_dir = patch.object(database, "DB_DIR", self._tmp_dir)
        self._patch_path.start()
        self._patch_dir.start()

        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(_SCHEMA_SQL)
            await db.commit()

        # Insert test carers for FK constraints
        async with database.get_db() as db:
            for i in range(1, 11):
                await db.execute(
                    """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                       VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                    (i, f"Carer {i}"),
                )
            await db.commit()

    async def teardown(self):
        """Remove patches."""
        self._patch_path.stop()
        self._patch_dir.stop()


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid carer IDs that exist in the test DB
st_carer_id = st.integers(min_value=1, max_value=10)

# Latitude/longitude within sensible ranges
st_lat = st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False)
st_lng = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)


@st.composite
def st_journey_update_any_field(draw):
    """Generate a JourneyUpdate with at least one field set."""
    fields = {}

    if draw(st.booleans()):
        fields["carer_id"] = draw(st_carer_id)
    if draw(st.booleans()):
        fields["planned_departure"] = datetime(2025, 6, 1, draw(st.integers(6, 18)), draw(st.integers(0, 59)))
    if draw(st.booleans()):
        fields["planned_arrival"] = datetime(2025, 6, 1, draw(st.integers(6, 23)), draw(st.integers(0, 59)))
    if draw(st.booleans()):
        fields["origin_lat"] = draw(st_lat)
    if draw(st.booleans()):
        fields["origin_lng"] = draw(st_lng)
    if draw(st.booleans()):
        fields["destination_lat"] = draw(st_lat)
    if draw(st.booleans()):
        fields["destination_lng"] = draw(st_lng)

    # Ensure at least one field is set
    if not fields:
        fields["destination_lat"] = draw(st_lat)

    return JourneyUpdate(**fields)


@st.composite
def st_journey_update_planned_fields(draw):
    """Generate a JourneyUpdate with any combination of fields valid for planned status."""
    fields = {}

    if draw(st.booleans()):
        fields["carer_id"] = draw(st_carer_id)
    if draw(st.booleans()):
        fields["planned_departure"] = datetime(2025, 6, 1, draw(st.integers(6, 18)), draw(st.integers(0, 59)))
    if draw(st.booleans()):
        fields["planned_arrival"] = datetime(2025, 6, 1, draw(st.integers(6, 23)), draw(st.integers(0, 59)))
    if draw(st.booleans()):
        fields["origin_lat"] = draw(st_lat)
    if draw(st.booleans()):
        fields["origin_lng"] = draw(st_lng)
    if draw(st.booleans()):
        fields["destination_lat"] = draw(st_lat)
    if draw(st.booleans()):
        fields["destination_lng"] = draw(st_lng)

    # Ensure at least one field
    if not fields:
        fields["destination_lat"] = draw(st_lat)

    return JourneyUpdate(**fields)


@st.composite
def st_journey_update_in_progress_allowed(draw):
    """Generate a JourneyUpdate with only fields allowed for in_progress journeys."""
    fields = {}

    if draw(st.booleans()):
        fields["planned_arrival"] = datetime(2025, 6, 1, draw(st.integers(6, 23)), draw(st.integers(0, 59)))
    if draw(st.booleans()):
        fields["destination_lat"] = draw(st_lat)
    if draw(st.booleans()):
        fields["destination_lng"] = draw(st_lng)

    # Ensure at least one field
    if not fields:
        fields["planned_arrival"] = datetime(2025, 6, 1, draw(st.integers(9, 20)), draw(st.integers(0, 59)))

    return JourneyUpdate(**fields)


@st.composite
def st_journey_update_in_progress_restricted(draw):
    """Generate a JourneyUpdate that includes at least one restricted field for in_progress."""
    restricted_fields = ["carer_id", "planned_departure", "origin_lat", "origin_lng"]
    chosen = draw(st.sampled_from(restricted_fields))

    fields = {}
    if chosen == "carer_id":
        fields["carer_id"] = draw(st_carer_id)
    elif chosen == "planned_departure":
        fields["planned_departure"] = datetime(2025, 6, 1, draw(st.integers(6, 18)), draw(st.integers(0, 59)))
    elif chosen == "origin_lat":
        fields["origin_lat"] = draw(st_lat)
    elif chosen == "origin_lng":
        fields["origin_lng"] = draw(st_lng)

    # Optionally add allowed fields too
    if draw(st.booleans()):
        fields["destination_lat"] = draw(st_lat)
    if draw(st.booleans()):
        fields["planned_arrival"] = datetime(2025, 6, 1, draw(st.integers(9, 23)), draw(st.integers(0, 59)))

    return JourneyUpdate(**fields)


# ---------------------------------------------------------------------------
# Property 4: Plan versioning increments sequentially
# Feature: journey-lifecycle-management, Property 4: Plan versioning increments sequentially
# **Validates: Requirements 1.6, 6.1**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(n=st.integers(min_value=1, max_value=10))
def test_property4_plan_versioning_increments_sequentially(tmp_path, n):
    """Property 4: For any operating day, creating N journey plans for that same
    day should produce plan versions numbered 1 through N consecutively, with all
    prior versions retained and unchanged.

    **Validates: Requirements 1.6, 6.1**
    """

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            operating_day = "2025-06-15"

            # Store created plans to verify retention
            created_plans = []

            for version in range(1, n + 1):
                reason = "initial_creation" if version == 1 else "manual_amendment"
                plan = await create_journey_plan(operating_day, reason, version)
                created_plans.append(plan)

                # Verify version number matches expected
                assert plan["plan_version"] == version, (
                    f"Expected plan_version {version}, got {plan['plan_version']}"
                )
                assert plan["operating_day"] == operating_day
                assert plan["created_at"] is not None

            # Verify latest version is N
            latest_version = await get_latest_plan_version(operating_day)
            assert latest_version == n, (
                f"Expected latest version {n}, got {latest_version}"
            )

            # Verify all prior versions are retained and unchanged
            all_plans = await list_journey_plans(operating_day=operating_day)
            assert len(all_plans) == n, (
                f"Expected {n} plans retained, found {len(all_plans)}"
            )

            # Verify versions are numbered 1 through N consecutively
            versions = sorted(p["plan_version"] for p in all_plans)
            expected_versions = list(range(1, n + 1))
            assert versions == expected_versions, (
                f"Expected versions {expected_versions}, got {versions}"
            )

            # Verify each individual plan is retrievable and unchanged
            for i, original in enumerate(created_plans):
                retrieved = await get_journey_plan(original["id"])
                assert retrieved is not None, f"Plan version {i+1} was not retained"
                assert retrieved["plan_version"] == original["plan_version"]
                assert retrieved["operating_day"] == original["operating_day"]
                assert retrieved["creation_reason"] == original["creation_reason"]
                assert retrieved["created_at"] == original["created_at"]
                assert retrieved["is_archived"] == 0

            # Each version should have a valid creation timestamp
            for plan in all_plans:
                assert plan["created_at"] is not None
                assert len(plan["created_at"]) > 0
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 5: Modifications always create new versions preserving prior state
# Feature: journey-lifecycle-management, Property 5: Modifications always create new versions preserving prior state
# **Validates: Requirements 2.1, 2.6**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(update=st_journey_update_planned_fields())
def test_property5_modification_creates_new_version_preserving_prior(tmp_path, update):
    """Property 5: For any journey modification, the system creates a new
    Plan_Version and the previous Plan_Version's data remains completely
    unchanged. The modified journey in the prior version has status amended.

    **Validates: Requirements 2.1, 2.6**
    """

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            # Create initial plan with a journey
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

            # Capture original journey state
            original_journey_before = await get_journey(journey["id"])
            original_plan_id = plan["id"]

            # Perform modification
            result = await service.modify_journey(plan["id"], journey["id"], update)

            # Property: A new plan version is created
            assert result.plan_version == 2
            assert result.id != original_plan_id
            assert result.creation_reason == PlanCreationReason.MANUAL_AMENDMENT

            # Property: The previous plan's journeys remain in the DB
            old_journeys = await get_journeys_by_plan(original_plan_id)
            assert len(old_journeys) == 1

            # Property: The modified journey in the prior version has status=amended
            old_journey = await get_journey(journey["id"])
            assert old_journey["status"] == "amended"

            # Property: Prior journey data (except status/updated_at) is unchanged
            assert old_journey["plan_id"] == original_journey_before["plan_id"]
            assert old_journey["carer_id"] == original_journey_before["carer_id"]
            assert old_journey["origin_lat"] == original_journey_before["origin_lat"]
            assert old_journey["origin_lng"] == original_journey_before["origin_lng"]
            assert old_journey["destination_lat"] == original_journey_before["destination_lat"]
            assert old_journey["destination_lng"] == original_journey_before["destination_lng"]
            assert old_journey["planned_departure"] == original_journey_before["planned_departure"]
            assert old_journey["planned_arrival"] == original_journey_before["planned_arrival"]
            assert old_journey["planned_distance_miles"] == original_journey_before["planned_distance_miles"]
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 6: Planned journey field editability
# Feature: journey-lifecycle-management, Property 6: Planned journey field editability
# **Validates: Requirements 2.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(update=st_journey_update_planned_fields())
def test_property6_planned_journey_accepts_all_field_updates(tmp_path, update):
    """Property 6: For any journey with status planned, updates to carer ID,
    departure time, arrival time, origin location, and destination location
    should all succeed and be reflected in the new plan version.

    **Validates: Requirements 2.2**
    """

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            # Create initial plan with a planned journey
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

            # Modification should not raise
            result = await service.modify_journey(plan["id"], journey["id"], update)

            # Property: New plan version created
            assert result.plan_version == 2

            # Property: Updated fields are reflected in the new plan version
            update_data = update.model_dump(exclude_none=True)
            assert len(result.journeys) == 1
            modified_journey = result.journeys[0]

            if "carer_id" in update_data:
                assert modified_journey.carer_id == update_data["carer_id"]
            if "planned_departure" in update_data:
                assert modified_journey.planned_departure == update_data["planned_departure"].isoformat()
            if "planned_arrival" in update_data:
                assert modified_journey.planned_arrival == update_data["planned_arrival"].isoformat()
            if "origin_lat" in update_data:
                assert modified_journey.origin_lat == update_data["origin_lat"]
            if "origin_lng" in update_data:
                assert modified_journey.origin_lng == update_data["origin_lng"]
            if "destination_lat" in update_data:
                assert modified_journey.destination_lat == update_data["destination_lat"]
            if "destination_lng" in update_data:
                assert modified_journey.destination_lng == update_data["destination_lng"]
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 7: In-progress journey restricts editable fields
# Feature: journey-lifecycle-management, Property 7: In-progress journey restricts editable fields
# **Validates: Requirements 2.3**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(update=st_journey_update_in_progress_allowed())
def test_property7_in_progress_allows_arrival_and_destination(tmp_path, update):
    """Property 7a: In-progress journeys accept updates to planned_arrival,
    destination_lat, and destination_lng.

    **Validates: Requirements 2.3**
    """

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            # Create plan and set journey to in_progress
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
            await update_journey_status(journey["id"], "in_progress")

            # Modification should succeed
            result = await service.modify_journey(plan["id"], journey["id"], update)

            # Property: New plan version created
            assert result.plan_version == 2

            # Property: Allowed fields are reflected
            update_data = update.model_dump(exclude_none=True)
            modified_journey = result.journeys[0]

            if "planned_arrival" in update_data:
                assert modified_journey.planned_arrival == update_data["planned_arrival"].isoformat()
            if "destination_lat" in update_data:
                assert modified_journey.destination_lat == update_data["destination_lat"]
            if "destination_lng" in update_data:
                assert modified_journey.destination_lng == update_data["destination_lng"]
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(update=st_journey_update_in_progress_restricted())
def test_property7_in_progress_rejects_restricted_fields(tmp_path, update):
    """Property 7b: In-progress journeys reject updates to carer_id,
    planned_departure, origin_lat, or origin_lng with HTTP 409.

    **Validates: Requirements 2.3**
    """

    async def _run():
        from fastapi import HTTPException

        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            # Create plan and set journey to in_progress
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
            await update_journey_status(journey["id"], "in_progress")

            # Property: Modification is rejected with 409
            try:
                await service.modify_journey(plan["id"], journey["id"], update)
                assert False, "Expected HTTPException 409 but no exception was raised"
            except HTTPException as exc:
                assert exc.status_code == 409
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 8: Terminal states reject modification
# Feature: journey-lifecycle-management, Property 8: Terminal states reject modification
# **Validates: Requirements 2.4, 2.5**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    update=st_journey_update_any_field(),
    terminal_status=st.sampled_from(["completed", "cancelled"]),
)
def test_property8_terminal_states_reject_any_modification(tmp_path, update, terminal_status):
    """Property 8: For any journey with status completed or cancelled, and for
    any update payload, the modification should be rejected with an appropriate
    error message (HTTP 409).

    **Validates: Requirements 2.4, 2.5**
    """

    async def _run():
        from fastapi import HTTPException

        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            # Create plan and set journey to terminal state
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

            if terminal_status == "cancelled":
                await update_journey_status(
                    journey["id"], "cancelled", cancelled_at="2025-06-01T07:00:00"
                )
            else:
                await update_journey_status(journey["id"], "completed")

            # Property: Any modification is rejected with 409
            try:
                await service.modify_journey(plan["id"], journey["id"], update)
                assert False, "Expected HTTPException 409 but no exception was raised"
            except HTTPException as exc:
                assert exc.status_code == 409
                assert "terminal state" in exc.detail
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 9: Deletion guard — no active journeys
# Feature: journey-lifecycle-management, Property 9: Deletion guard — no active journeys
# **Validates: Requirements 3.1, 3.2, 3.3**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    future_offset=st.integers(min_value=1, max_value=30),
    num_journeys=st.integers(min_value=1, max_value=5),
    active_journey_indices=st.lists(
        st.integers(min_value=0, max_value=99), min_size=1, max_size=3
    ),
    active_status=st.sampled_from(["in_progress", "completed"]),
)
def test_property9_deletion_guard_rejects_active_journeys(
    tmp_path, future_offset, num_journeys, active_journey_indices, active_status
):
    """Property 9: For any journey plan for a future date where at least one
    journey has status in_progress or completed, deletion should be rejected
    and the error response should list the journey identifiers that prevent
    deletion.

    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException

    async def _run():
        # Use a unique DB file per Hypothesis example to avoid cross-contamination
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers for FK constraints
            async with database.get_db() as db:
                for i in range(1, 6):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            future_day = (date.today() + timedelta(days=future_offset)).isoformat()

            # Create a journey plan for a future date
            plan = await create_journey_plan(future_day, "initial_creation", 1)

            # Create journeys for the plan
            journey_ids = []
            for i in range(num_journeys):
                departure_time = f"{future_day}T{8 + i:02d}:00:00"
                arrival_time = f"{future_day}T{8 + i:02d}:30:00"
                journey = await create_journey(
                    plan_id=plan["id"],
                    carer_id=((i % 5) + 1),
                    visit_id=None,
                    origin_lat=51.5,
                    origin_lng=-0.1,
                    origin_label="Origin",
                    destination_lat=51.6,
                    destination_lng=-0.2,
                    destination_label="Destination",
                    planned_departure=departure_time,
                    planned_arrival=arrival_time,
                    planned_distance_miles=3.0,
                )
                journey_ids.append(journey["id"])

            # Set at least one journey to an active status (in_progress or completed)
            active_indices = set(idx % num_journeys for idx in active_journey_indices)
            blocking_ids = []
            for idx in active_indices:
                await update_journey_status(journey_ids[idx], active_status)
                blocking_ids.append(journey_ids[idx])

            # Attempt to delete the plan — should be rejected
            try:
                await service.delete_plan(plan_id=plan["id"])
                assert False, "Expected HTTPException 409 but no exception was raised"
            except _HTTPException as exc:
                # Verify the error response has status 409
                assert exc.status_code == 409

                # The error should list ALL blocking journey IDs
                for blocking_id in blocking_ids:
                    assert str(blocking_id) in exc.detail, (
                        f"Blocking journey ID {blocking_id} not found in error: {exc.detail}"
                    )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 10: Soft-delete archives with timestamp
# Feature: journey-lifecycle-management, Property 10: Soft-delete archives with timestamp
# **Validates: Requirements 3.1, 3.2, 3.3**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    future_offset=st.integers(min_value=1, max_value=30),
    num_journeys=st.integers(min_value=0, max_value=5),
    statuses=st.lists(
        st.sampled_from(["planned", "cancelled", "amended"]),
        min_size=0,
        max_size=5,
    ),
)
def test_property10_soft_delete_archives_with_timestamp(
    tmp_path, future_offset, num_journeys, statuses
):
    """Property 10: For any successfully deleted journey plan, the plan should
    be marked as archived with a non-null archived_at UTC timestamp and should
    no longer appear in standard list/search operations, but should be
    retrievable via archive-specific queries.

    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    import uuid as _uuid
    from datetime import timezone as _tz

    from backend.app.db.journey_repository import (
        get_archived_plans as _get_archived_plans,
        get_journey_plan as _get_journey_plan,
        list_journey_plans as _list_journey_plans,
    )

    async def _run():
        # Use a unique DB file per Hypothesis example to avoid cross-contamination
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers for FK constraints
            async with database.get_db() as db:
                for i in range(1, 6):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            future_day = (date.today() + timedelta(days=future_offset)).isoformat()

            # Create a journey plan for a future date
            plan = await create_journey_plan(future_day, "initial_creation", 1)

            # Create journeys with non-active statuses only (so deletion is allowed)
            actual_num = min(num_journeys, len(statuses)) if statuses else num_journeys
            for i in range(actual_num):
                departure_time = f"{future_day}T{8 + i:02d}:00:00"
                arrival_time = f"{future_day}T{8 + i:02d}:30:00"
                journey = await create_journey(
                    plan_id=plan["id"],
                    carer_id=((i % 5) + 1),
                    visit_id=None,
                    origin_lat=51.5,
                    origin_lng=-0.1,
                    origin_label="Origin",
                    destination_lat=51.6,
                    destination_lng=-0.2,
                    destination_label="Destination",
                    planned_departure=departure_time,
                    planned_arrival=arrival_time,
                    planned_distance_miles=3.0,
                )
                if i < len(statuses) and statuses[i] != "planned":
                    await update_journey_status(journey["id"], statuses[i])

            # Record the time before deletion for timestamp validation
            before_delete = datetime.now(_tz.utc)

            # Delete the plan
            result = await service.delete_plan(plan_id=plan["id"])

            # Verify the deletion confirmation
            assert result.plan_id == plan["id"]
            assert result.journeys_removed == actual_num

            # 1. Plan is marked as archived with a non-null archived_at timestamp
            archived_plan = await _get_journey_plan(plan["id"])
            assert archived_plan["is_archived"] == 1, "Plan should be marked as archived"
            assert archived_plan["archived_at"] is not None, "archived_at should be non-null"

            # Verify the archived_at timestamp is a valid UTC datetime
            archived_at_str = archived_plan["archived_at"]
            archived_at_dt = datetime.fromisoformat(archived_at_str)
            assert archived_at_dt >= before_delete - timedelta(seconds=5), (
                f"archived_at {archived_at_dt} should be >= {before_delete - timedelta(seconds=5)}"
            )

            # 2. Plan no longer appears in standard list operations
            standard_plans = await _list_journey_plans(
                operating_day=future_day, include_archived=False
            )
            standard_plan_ids = [p["id"] for p in standard_plans]
            assert plan["id"] not in standard_plan_ids, (
                "Archived plan should not appear in standard list operations"
            )

            # 3. Plan IS retrievable via archive-specific queries
            archived_plans = await _get_archived_plans(operating_day=future_day)
            archived_plan_ids = [p["id"] for p in archived_plans]
            assert plan["id"] in archived_plan_ids, (
                "Archived plan should be retrievable via archive-specific queries"
            )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Strategy Generators for Property 1
# ---------------------------------------------------------------------------


def st_operating_day():
    """Generate valid future dates within 365 days from today."""
    today = date.today()
    return st.integers(min_value=0, max_value=364).map(
        lambda offset: (today + timedelta(days=offset)).isoformat()
    )


@st.composite
def st_journey_create(draw):
    """Generate valid JourneyCreate-like payloads as dicts.

    Constrains coordinates to valid lat/lng ranges, ensures arrival is after
    departure, and uses carer IDs from the fixture (1-10).
    """
    carer_id = draw(st.integers(min_value=1, max_value=10))
    visit_id = draw(st.none())  # FK to visits table; use None to avoid FK constraint issues
    origin_lat = draw(st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False))
    origin_lng = draw(st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False))
    origin_label = draw(st.one_of(st.none(), st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z")))))
    destination_lat = draw(st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False))
    destination_lng = draw(st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False))
    destination_label = draw(st.one_of(st.none(), st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z")))))
    # Generate departure hour/minute
    hour = draw(st.integers(min_value=6, max_value=20))
    minute = draw(st.integers(min_value=0, max_value=59))
    planned_departure = f"2025-08-01T{hour:02d}:{minute:02d}:00"
    # Arrival is 15-120 minutes after departure
    duration_minutes = draw(st.integers(min_value=15, max_value=120))
    departure_dt = datetime(2025, 8, 1, hour, minute, 0)
    arrival_dt = departure_dt + timedelta(minutes=duration_minutes)
    planned_arrival = arrival_dt.isoformat()
    planned_distance_miles = draw(st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False))

    return {
        "carer_id": carer_id,
        "visit_id": visit_id,
        "origin_lat": origin_lat,
        "origin_lng": origin_lng,
        "origin_label": origin_label,
        "destination_lat": destination_lat,
        "destination_lng": destination_lng,
        "destination_label": destination_label,
        "planned_departure": planned_departure,
        "planned_arrival": planned_arrival,
        "planned_distance_miles": planned_distance_miles,
    }


# ---------------------------------------------------------------------------
# Property 1: Journey plan creation round-trip
# Feature: journey-lifecycle-management, Property 1: Journey plan creation round-trip
# **Validates: Requirements 1.1, 1.5**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    operating_day=st_operating_day(),
    journeys_data=st.lists(st_journey_create(), min_size=1, max_size=5),
)
def test_property1_plan_creation_round_trip(tmp_path, operating_day, journeys_data):
    """Property 1: For any valid journey plan data (operating day, list of journeys
    with carer ID, origin, destination, departure, arrival, distance, and visit ID),
    creating the plan and then retrieving it should produce an equivalent record
    containing all original fields, a unique identifier, plan version 1, and a
    creation timestamp.

    **Validates: Requirements 1.1, 1.5**
    """

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            # Create the plan
            plan = await create_journey_plan(operating_day, "initial_creation", 1)

            # Create journeys within the plan
            created_journeys = []
            for j_data in journeys_data:
                journey = await create_journey(
                    plan_id=plan["id"],
                    carer_id=j_data["carer_id"],
                    visit_id=j_data["visit_id"],
                    origin_lat=j_data["origin_lat"],
                    origin_lng=j_data["origin_lng"],
                    origin_label=j_data["origin_label"],
                    destination_lat=j_data["destination_lat"],
                    destination_lng=j_data["destination_lng"],
                    destination_label=j_data["destination_label"],
                    planned_departure=j_data["planned_departure"],
                    planned_arrival=j_data["planned_arrival"],
                    planned_distance_miles=j_data["planned_distance_miles"],
                )
                created_journeys.append(journey)

            # Retrieve the plan
            retrieved_plan = await get_journey_plan(plan["id"])

            # Plan-level assertions
            assert retrieved_plan is not None, "Plan should be retrievable after creation"
            assert retrieved_plan["id"] is not None, "Plan should have a unique identifier"
            assert isinstance(retrieved_plan["id"], int), "Plan ID should be an integer"
            assert retrieved_plan["operating_day"] == operating_day, "Operating day should match"
            assert retrieved_plan["plan_version"] == 1, "First plan should have version 1"
            assert retrieved_plan["creation_reason"] == "initial_creation"
            assert retrieved_plan["created_at"] is not None, "Plan should have a creation timestamp"
            assert len(retrieved_plan["created_at"]) > 0, "Creation timestamp should not be empty"
            assert retrieved_plan["is_archived"] == 0, "New plan should not be archived"

            # Retrieve journeys for the plan
            retrieved_journeys = await get_journeys_by_plan(plan["id"])

            # Journey count should match
            assert len(retrieved_journeys) == len(journeys_data), (
                f"Expected {len(journeys_data)} journeys, got {len(retrieved_journeys)}"
            )

            # Verify each created journey's fields by retrieving individually
            for idx, created_j in enumerate(created_journeys):
                retrieved_j = await get_journey(created_j["id"])
                assert retrieved_j is not None, f"Journey {idx} should be retrievable"

                # Find the matching original input data
                j_data = journeys_data[idx]

                # Verify all original fields are preserved (round-trip)
                assert retrieved_j["id"] is not None, "Journey should have a unique ID"
                assert isinstance(retrieved_j["id"], int), "Journey ID should be an integer"
                assert retrieved_j["plan_id"] == plan["id"], "Journey should reference the plan"
                assert retrieved_j["carer_id"] == j_data["carer_id"], "Carer ID should match"
                assert retrieved_j["visit_id"] == j_data["visit_id"], "Visit ID should match"
                assert retrieved_j["origin_lat"] == j_data["origin_lat"], "Origin lat should match"
                assert retrieved_j["origin_lng"] == j_data["origin_lng"], "Origin lng should match"
                assert retrieved_j["origin_label"] == j_data["origin_label"], "Origin label should match"
                assert retrieved_j["destination_lat"] == j_data["destination_lat"], "Dest lat should match"
                assert retrieved_j["destination_lng"] == j_data["destination_lng"], "Dest lng should match"
                assert retrieved_j["destination_label"] == j_data["destination_label"], "Dest label should match"
                assert retrieved_j["planned_departure"] == j_data["planned_departure"], "Departure should match"
                assert retrieved_j["planned_arrival"] == j_data["planned_arrival"], "Arrival should match"
                assert retrieved_j["planned_distance_miles"] == j_data["planned_distance_miles"], "Distance should match"
                assert retrieved_j["status"] == "planned", "Initial status should be 'planned'"
                assert retrieved_j["created_at"] is not None, "Journey should have created_at"
                assert retrieved_j["updated_at"] is not None, "Journey should have updated_at"
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 19: History returns versions in chronological order
# Feature: journey-lifecycle-management, Property 19: History returns versions in chronological order
# **Validates: Requirements 6.3, 6.6**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    num_versions=st.integers(min_value=2, max_value=6),
    num_journeys_per_version=st.integers(min_value=1, max_value=3),
)
def test_property19_history_returns_versions_in_chronological_order(
    tmp_path, num_versions, num_journeys_per_version
):
    """Property 19: For any operating day with multiple plan versions, requesting
    history should return all versions ordered by creation timestamp ascending,
    including version number, creation reason, and the full set of journeys for
    each version.

    **Validates: Requirements 6.3**
    """
    import uuid as _uuid

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers for FK constraints
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            operating_day_str = "2025-07-15"

            # Create multiple plan versions with journeys
            reasons = ["initial_creation"] + ["manual_amendment"] * (num_versions - 1)

            for version in range(1, num_versions + 1):
                plan = await create_journey_plan(
                    operating_day_str, reasons[version - 1], version
                )

                # Add journeys to each plan version
                for j in range(num_journeys_per_version):
                    hour = 8 + j
                    await create_journey(
                        plan_id=plan["id"],
                        carer_id=((j % 10) + 1),
                        visit_id=None,
                        origin_lat=51.5,
                        origin_lng=-0.1,
                        origin_label="Origin",
                        destination_lat=51.6,
                        destination_lng=-0.2,
                        destination_label="Destination",
                        planned_departure=f"{operating_day_str}T{hour:02d}:00:00",
                        planned_arrival=f"{operating_day_str}T{hour:02d}:30:00",
                        planned_distance_miles=3.0 + j,
                    )

            # Request history
            history = await service.get_history(date.fromisoformat(operating_day_str))

            # Property: All versions are returned
            assert len(history) == num_versions, (
                f"Expected {num_versions} versions, got {len(history)}"
            )

            # Property: Versions are ordered by creation timestamp ascending
            for i in range(len(history) - 1):
                assert history[i].created_at <= history[i + 1].created_at, (
                    f"Version {history[i].plan_version} created_at ({history[i].created_at}) "
                    f"should be <= version {history[i+1].plan_version} created_at ({history[i+1].created_at})"
                )

            # Property: Version numbers are in ascending order (chronological)
            for i in range(len(history) - 1):
                assert history[i].plan_version < history[i + 1].plan_version, (
                    f"Version numbers should be ascending: "
                    f"{history[i].plan_version} should be < {history[i+1].plan_version}"
                )

            # Property: Each version includes version number, creation reason, and journeys
            for i, plan_model in enumerate(history):
                # Version number matches expected sequence
                assert plan_model.plan_version == i + 1, (
                    f"Expected version {i+1}, got {plan_model.plan_version}"
                )

                # Creation reason is present and valid
                assert plan_model.creation_reason is not None
                assert plan_model.creation_reason.value in (
                    "initial_creation",
                    "manual_amendment",
                    "re_optimisation",
                )

                # First version should be initial_creation
                if i == 0:
                    assert plan_model.creation_reason.value == "initial_creation"
                else:
                    assert plan_model.creation_reason.value == "manual_amendment"

                # Full set of journeys is included
                assert len(plan_model.journeys) == num_journeys_per_version, (
                    f"Version {plan_model.plan_version} should have "
                    f"{num_journeys_per_version} journeys, got {len(plan_model.journeys)}"
                )

                # Each journey should have essential fields populated
                for journey in plan_model.journeys:
                    assert journey.id is not None
                    assert journey.plan_id == plan_model.id
                    assert journey.carer_id is not None
                    assert journey.planned_departure is not None
                    assert journey.planned_arrival is not None
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 20: Date range validation for historical queries
# Feature: journey-lifecycle-management, Property 20: Date range validation for historical queries
# **Validates: Requirements 6.6**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    days_exceeding=st.integers(min_value=91, max_value=365),
)
def test_property20_date_range_exceeding_90_days_rejected(tmp_path, days_exceeding):
    """Property 20a: For any date range request where the range exceeds 90 days,
    the system should reject the request with an error identifying that the
    90-day constraint was violated.

    **Validates: Requirements 6.6**
    """
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            service = JourneyService()

            start_date = date(2025, 1, 1)
            end_date = start_date + timedelta(days=days_exceeding)

            # Property: Request is rejected
            try:
                await service.get_date_range_summary(start_date, end_date)
                assert False, "Expected HTTPException 422 but no exception was raised"
            except _HTTPException as exc:
                assert exc.status_code == 422
                # Error should identify the 90-day constraint
                assert "90" in exc.detail, (
                    f"Error should mention 90-day limit, got: {exc.detail}"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    start_offset=st.integers(min_value=1, max_value=180),
)
def test_property20_start_after_end_rejected(tmp_path, start_offset):
    """Property 20b: For any date range request where the start date is after
    the end date, the system should reject the request with an error identifying
    that the start/end constraint was violated.

    **Validates: Requirements 6.6**
    """
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            service = JourneyService()

            # Start date is strictly after end date
            end_date = date(2025, 3, 1)
            start_date = end_date + timedelta(days=start_offset)

            # Property: Request is rejected
            try:
                await service.get_date_range_summary(start_date, end_date)
                assert False, "Expected HTTPException 422 but no exception was raised"
            except _HTTPException as exc:
                assert exc.status_code == 422
                # Error should identify the start/end constraint
                assert "start" in exc.detail.lower() or "before" in exc.detail.lower(), (
                    f"Error should mention start/end constraint, got: {exc.detail}"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    days_range=st.integers(min_value=0, max_value=90),
)
def test_property20_valid_date_range_accepted(tmp_path, days_range):
    """Property 20c: For any date range request where the range is at most 90 days
    and the start date is on or before the end date, the system should accept the
    request without error.

    **Validates: Requirements 6.6**
    """
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            service = JourneyService()

            start_date = date(2025, 1, 1)
            end_date = start_date + timedelta(days=days_range)

            # Property: Request should NOT raise (valid range)
            try:
                result = await service.get_date_range_summary(start_date, end_date)
                # Should return a list (possibly empty if no data exists)
                assert isinstance(result, list)
            except _HTTPException:
                assert False, (
                    f"Valid date range ({days_range} days) should not be rejected"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 16: Variance calculation correctness
# Feature: journey-lifecycle-management, Property 16: Variance calculation correctness
# **Validates: Requirements 5.2, 5.3, 5.4**
# ---------------------------------------------------------------------------


@st.composite
def st_matched_journey_pair(draw):
    """Generate a matched pair of planned and actual journey data.

    Produces a dict with planned_departure, planned_arrival, planned_distance,
    actual_departure, actual_arrival, actual_distance that can be used to
    create a planned journey and a corresponding actual journey.
    """
    carer_id = draw(st.integers(min_value=1, max_value=10))

    # Planned departure: some time on 2025-08-01
    planned_hour = draw(st.integers(min_value=6, max_value=18))
    planned_minute = draw(st.integers(min_value=0, max_value=59))
    planned_dep = datetime(2025, 8, 1, planned_hour, planned_minute, 0)

    # Planned arrival: 15-120 minutes after departure
    planned_duration = draw(st.integers(min_value=15, max_value=120))
    planned_arr = planned_dep + timedelta(minutes=planned_duration)

    # Planned distance
    planned_distance = draw(
        st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    # Round to 1 decimal for clean test data
    planned_distance = round(planned_distance, 1)

    # Actual departure: planned_departure +/- up to 60 minutes (within matching window)
    dep_offset_minutes = draw(st.integers(min_value=-59, max_value=59))
    actual_dep = planned_dep + timedelta(minutes=dep_offset_minutes)
    # Ensure actual departure stays on the same day and is valid
    if actual_dep.hour < 0 or actual_dep.day != planned_dep.day:
        actual_dep = planned_dep  # fallback

    # Actual arrival: actual_departure + 10-180 minutes (must be after actual departure)
    actual_duration = draw(st.integers(min_value=10, max_value=180))
    actual_arr = actual_dep + timedelta(minutes=actual_duration)

    # Actual distance
    actual_distance = draw(
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    actual_distance = round(actual_distance, 1)

    return {
        "carer_id": carer_id,
        "planned_departure": planned_dep,
        "planned_arrival": planned_arr,
        "planned_distance": planned_distance,
        "actual_departure": actual_dep,
        "actual_arrival": actual_arr,
        "actual_distance": actual_distance,
    }


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pair=st_matched_journey_pair())
def test_property16_variance_calculation_correctness(tmp_path, pair):
    """Property 16: For any matched pair of planned and actual journey data,
    the departure variance should equal (actual_departure - planned_departure) in
    whole minutes (signed), the arrival variance should equal
    (actual_arrival - planned_arrival) in whole minutes (signed), and the distance
    variance should equal (actual_distance - planned_distance) rounded to 1 decimal
    place (signed).

    **Validates: Requirements 5.2, 5.3, 5.4**
    """

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            from backend.app.db.journey_repository import create_actual_journey

            service = JourneyService()

            operating_day = "2025-08-01"

            # Create a journey plan
            plan = await create_journey_plan(operating_day, "initial_creation", 1)

            # Create the planned journey
            journey = await create_journey(
                plan_id=plan["id"],
                carer_id=pair["carer_id"],
                visit_id=None,
                origin_lat=51.5,
                origin_lng=-0.1,
                origin_label="Origin",
                destination_lat=51.6,
                destination_lng=-0.2,
                destination_label="Destination",
                planned_departure=pair["planned_departure"].isoformat(),
                planned_arrival=pair["planned_arrival"].isoformat(),
                planned_distance_miles=pair["planned_distance"],
            )

            # Create a matched actual journey
            await create_actual_journey(
                journey_id=journey["id"],
                carer_id=pair["carer_id"],
                operating_day=operating_day,
                actual_departure=pair["actual_departure"].isoformat(),
                actual_arrival=pair["actual_arrival"].isoformat(),
                actual_distance_miles=pair["actual_distance"],
                route_coordinates="[]",
                match_status="matched",
            )

            # Run comparison
            result = await service.get_comparison(date(2025, 8, 1))

            # Find our entry
            carer_entries = result.entries_by_carer.get(pair["carer_id"], [])
            assert len(carer_entries) >= 1, "Should have at least one comparison entry"

            # Find the matched entry
            matched_entries = [
                e for e in carer_entries
                if e.match_status.value == "matched"
            ]
            assert len(matched_entries) == 1, "Should have exactly one matched entry"
            entry = matched_entries[0]

            # Verify variance is present
            assert entry.variance is not None, "Matched entries must have variance"

            # Calculate expected variances
            expected_dep_variance = int(
                (pair["actual_departure"] - pair["planned_departure"]).total_seconds() / 60
            )
            expected_arr_variance = int(
                (pair["actual_arrival"] - pair["planned_arrival"]).total_seconds() / 60
            )
            expected_dist_variance = round(
                pair["actual_distance"] - pair["planned_distance"], 1
            )

            # Property assertions
            assert entry.variance.departure_variance_minutes == expected_dep_variance, (
                f"Departure variance: expected {expected_dep_variance}, "
                f"got {entry.variance.departure_variance_minutes}"
            )
            assert entry.variance.arrival_variance_minutes == expected_arr_variance, (
                f"Arrival variance: expected {expected_arr_variance}, "
                f"got {entry.variance.arrival_variance_minutes}"
            )
            assert entry.variance.distance_variance_miles == expected_dist_variance, (
                f"Distance variance: expected {expected_dist_variance}, "
                f"got {entry.variance.distance_variance_miles}"
            )
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 17: Comparison includes unmatched entries with null variances
# Feature: journey-lifecycle-management, Property 17: Comparison includes unmatched entries with null variances
# **Validates: Requirements 5.5**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    num_unstarted=st.integers(min_value=0, max_value=3),
    num_unplanned=st.integers(min_value=0, max_value=3),
    num_matched=st.integers(min_value=0, max_value=3),
)
def test_property17_unmatched_entries_have_null_variances(
    tmp_path, num_unstarted, num_unplanned, num_matched
):
    """Property 17: For any comparison result, planned journeys without matching
    actuals should appear with match_status unstarted and all variance values null.
    Actual journeys without matching planned journeys should appear with
    match_status unplanned and all variance values null.

    **Validates: Requirements 5.5**
    """
    # Need at least one entry to have a meaningful test
    from hypothesis import assume
    assume(num_unstarted + num_unplanned + num_matched > 0)

    async def _run():
        import uuid as _uuid
        from backend.app.db.journey_repository import create_actual_journey

        # Use a unique DB to avoid cross-contamination
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()
            operating_day = "2025-08-01"

            # Create a journey plan
            plan = await create_journey_plan(operating_day, "initial_creation", 1)

            # Create planned journeys that WILL be matched
            matched_journey_ids = []
            for i in range(num_matched):
                dep_time = f"2025-08-01T{8 + i:02d}:00:00"
                arr_time = f"2025-08-01T{8 + i:02d}:30:00"
                journey = await create_journey(
                    plan_id=plan["id"],
                    carer_id=1,
                    visit_id=None,
                    origin_lat=51.5,
                    origin_lng=-0.1,
                    origin_label="Origin",
                    destination_lat=51.6,
                    destination_lng=-0.2,
                    destination_label="Destination",
                    planned_departure=dep_time,
                    planned_arrival=arr_time,
                    planned_distance_miles=5.0,
                )
                matched_journey_ids.append(journey["id"])

            # Create planned journeys that will NOT be matched (unstarted)
            for i in range(num_unstarted):
                dep_time = f"2025-08-01T{12 + i:02d}:00:00"
                arr_time = f"2025-08-01T{12 + i:02d}:30:00"
                await create_journey(
                    plan_id=plan["id"],
                    carer_id=2,
                    visit_id=None,
                    origin_lat=51.5,
                    origin_lng=-0.1,
                    origin_label="Origin",
                    destination_lat=51.6,
                    destination_lng=-0.2,
                    destination_label="Destination",
                    planned_departure=dep_time,
                    planned_arrival=arr_time,
                    planned_distance_miles=3.0,
                )

            # Create actual journeys matched to planned ones
            for i, journey_id in enumerate(matched_journey_ids):
                await create_actual_journey(
                    journey_id=journey_id,
                    carer_id=1,
                    operating_day=operating_day,
                    actual_departure=f"2025-08-01T{8 + i:02d}:05:00",
                    actual_arrival=f"2025-08-01T{8 + i:02d}:35:00",
                    actual_distance_miles=5.2,
                    route_coordinates="[]",
                    match_status="matched",
                )

            # Create unplanned actual journeys (no matching planned journey)
            for i in range(num_unplanned):
                await create_actual_journey(
                    journey_id=None,
                    carer_id=3,
                    operating_day=operating_day,
                    actual_departure=f"2025-08-01T{16 + i:02d}:00:00",
                    actual_arrival=f"2025-08-01T{16 + i:02d}:30:00",
                    actual_distance_miles=4.0,
                    route_coordinates="[]",
                    match_status="unmatched",
                )

            # Run comparison
            result = await service.get_comparison(date(2025, 8, 1))

            # Collect all entries across all carers
            all_entries = []
            for carer_id, entries in result.entries_by_carer.items():
                all_entries.extend(entries)

            # Verify unstarted entries
            unstarted_entries = [
                e for e in all_entries if e.match_status.value == "unstarted"
            ]
            assert len(unstarted_entries) == num_unstarted, (
                f"Expected {num_unstarted} unstarted entries, got {len(unstarted_entries)}"
            )
            for entry in unstarted_entries:
                # Property: unstarted has planned_journey but no actual
                assert entry.planned_journey is not None
                assert entry.actual_journey is None
                # Property: all variance values are null
                assert entry.variance is None, (
                    "Unstarted entries must have null variance"
                )

            # Verify unplanned entries
            unplanned_entries = [
                e for e in all_entries if e.match_status.value == "unplanned"
            ]
            assert len(unplanned_entries) == num_unplanned, (
                f"Expected {num_unplanned} unplanned entries, got {len(unplanned_entries)}"
            )
            for entry in unplanned_entries:
                # Property: unplanned has actual_journey but no planned
                assert entry.actual_journey is not None
                assert entry.planned_journey is None
                # Property: all variance values are null
                assert entry.variance is None, (
                    "Unplanned entries must have null variance"
                )

            # Verify matched entries
            matched_entries = [
                e for e in all_entries if e.match_status.value == "matched"
            ]
            assert len(matched_entries) == num_matched, (
                f"Expected {num_matched} matched entries, got {len(matched_entries)}"
            )
            for entry in matched_entries:
                assert entry.planned_journey is not None
                assert entry.actual_journey is not None
                assert entry.variance is not None, (
                    "Matched entries must have non-null variance"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 18: Comparison results grouped by carer and ordered by departure
# Feature: journey-lifecycle-management, Property 18: Comparison results grouped by carer and ordered by departure
# **Validates: Requirements 5.1**
# ---------------------------------------------------------------------------


@st.composite
def st_multi_carer_journeys(draw):
    """Generate journey data for multiple carers with varying departure times.

    Returns a list of dicts, each with carer_id and a departure hour/minute,
    suitable for creating journeys spread across carers.
    """
    num_carers = draw(st.integers(min_value=1, max_value=4))
    carer_ids = list(range(1, num_carers + 1))

    journeys = []
    for carer_id in carer_ids:
        num_journeys = draw(st.integers(min_value=1, max_value=4))
        # Generate unique departure times for this carer
        used_hours = set()
        for _ in range(num_journeys):
            hour = draw(st.integers(min_value=6, max_value=20))
            minute = draw(st.integers(min_value=0, max_value=59))
            # Ensure uniqueness within carer
            while (hour, minute) in used_hours:
                hour = draw(st.integers(min_value=6, max_value=20))
                minute = draw(st.integers(min_value=0, max_value=59))
            used_hours.add((hour, minute))
            journeys.append({
                "carer_id": carer_id,
                "hour": hour,
                "minute": minute,
            })

    return journeys


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(journey_specs=st_multi_carer_journeys())
def test_property18_comparison_grouped_by_carer_ordered_by_departure(tmp_path, journey_specs):
    """Property 18: For any comparison for an operating day, the results should be
    grouped by carer ID and within each carer group, entries should be ordered by
    planned departure time ascending.

    **Validates: Requirements 5.1**
    """

    async def _run():
        import uuid as _uuid

        # Use a unique DB to avoid cross-contamination
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()
            operating_day = "2025-08-01"

            # Create a journey plan
            plan = await create_journey_plan(operating_day, "initial_creation", 1)

            # Create journeys in a potentially shuffled order
            for spec in journey_specs:
                dep_time = f"2025-08-01T{spec['hour']:02d}:{spec['minute']:02d}:00"
                arr_dt = datetime(2025, 8, 1, spec["hour"], spec["minute"]) + timedelta(minutes=30)
                arr_time = arr_dt.isoformat()
                await create_journey(
                    plan_id=plan["id"],
                    carer_id=spec["carer_id"],
                    visit_id=None,
                    origin_lat=51.5,
                    origin_lng=-0.1,
                    origin_label="Origin",
                    destination_lat=51.6,
                    destination_lng=-0.2,
                    destination_label="Destination",
                    planned_departure=dep_time,
                    planned_arrival=arr_time,
                    planned_distance_miles=5.0,
                )

            # Run comparison
            result = await service.get_comparison(date(2025, 8, 1))

            # Property 1: Results are grouped by carer ID
            # All entries under a carer_id key belong to that carer
            for carer_id, entries in result.entries_by_carer.items():
                for entry in entries:
                    if entry.planned_journey is not None:
                        assert entry.planned_journey.carer_id == carer_id, (
                            f"Entry under carer {carer_id} has journey for carer "
                            f"{entry.planned_journey.carer_id}"
                        )

            # Property 2: Within each carer group, entries are ordered by
            # planned departure time ascending
            for carer_id, entries in result.entries_by_carer.items():
                departure_times = []
                for entry in entries:
                    if entry.planned_journey is not None:
                        departure_times.append(entry.planned_journey.planned_departure)
                    elif entry.actual_journey is not None:
                        departure_times.append(entry.actual_journey.actual_departure)

                # Verify ascending order
                for i in range(len(departure_times) - 1):
                    assert departure_times[i] <= departure_times[i + 1], (
                        f"Entries for carer {carer_id} not ordered by departure: "
                        f"{departure_times[i]} > {departure_times[i + 1]}"
                    )

            # Property 3: All carers with journeys are represented in the result
            expected_carer_ids = set(spec["carer_id"] for spec in journey_specs)
            actual_carer_ids = set(result.entries_by_carer.keys())
            assert expected_carer_ids == actual_carer_ids, (
                f"Expected carers {expected_carer_ids}, got {actual_carer_ids}"
            )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Strategies for actual journey property tests (Properties 11-15)
# ---------------------------------------------------------------------------


@st.composite
def st_route_coordinates(draw):
    """Generate valid route coordinates — list of [lat, lng] pairs (0-1000 items)."""
    num_pairs = draw(st.integers(min_value=0, max_value=50))  # keep small for speed
    coords = []
    for _ in range(num_pairs):
        lat = draw(st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False))
        lng = draw(st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False))
        coords.append([lat, lng])
    return coords


@st.composite
def st_actual_journey_valid(draw):
    """Generate a valid ActualJourneyCreate-like dict.

    Ensures actual_arrival > actual_departure, distance >= 0,
    and route_coordinates <= 1000 pairs.
    """
    carer_id = draw(st.integers(min_value=1, max_value=10))
    operating_day = date.today() + timedelta(days=draw(st.integers(min_value=0, max_value=30)))

    # Generate departure hour/minute
    dep_hour = draw(st.integers(min_value=6, max_value=18))
    dep_minute = draw(st.integers(min_value=0, max_value=59))
    actual_departure = datetime(
        operating_day.year, operating_day.month, operating_day.day,
        dep_hour, dep_minute, 0
    )

    # Arrival must be strictly after departure (add 1-180 minutes)
    duration_minutes = draw(st.integers(min_value=1, max_value=180))
    actual_arrival = actual_departure + timedelta(minutes=duration_minutes)

    # Distance to 1 decimal place, non-negative
    actual_distance_miles = round(draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)), 1)

    route_coordinates = draw(st_route_coordinates())

    return {
        "carer_id": carer_id,
        "operating_day": operating_day,
        "actual_departure": actual_departure,
        "actual_arrival": actual_arrival,
        "actual_distance_miles": actual_distance_miles,
        "route_coordinates": route_coordinates,
    }


# ---------------------------------------------------------------------------
# Property 11: Actual journey data persistence round-trip
# Feature: journey-lifecycle-management, Property 11: Actual journey data persistence round-trip
# **Validates: Requirements 4.1**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=st_actual_journey_valid())
def test_property11_actual_journey_persistence_round_trip(tmp_path, data):
    """Property 11: For any valid actual journey data (carer ID, departure/arrival
    times, distance to 1 decimal, route coordinates ≤1000 pairs), storing the data
    and retrieving it should produce an equivalent record with all fields preserved.

    **Validates: Requirements 4.1**
    """
    import json

    from backend.app.db.journey_repository import (
        create_actual_journey as _create_actual,
        get_actual_journeys_by_day as _get_actuals_by_day,
    )

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            operating_day_str = data["operating_day"].isoformat()
            actual_departure_str = data["actual_departure"].isoformat()
            actual_arrival_str = data["actual_arrival"].isoformat()
            route_coords_json = json.dumps(data["route_coordinates"])

            # Store actual journey
            created = await _create_actual(
                journey_id=None,
                carer_id=data["carer_id"],
                operating_day=operating_day_str,
                actual_departure=actual_departure_str,
                actual_arrival=actual_arrival_str,
                actual_distance_miles=data["actual_distance_miles"],
                route_coordinates=route_coords_json,
                match_status="unmatched",
            )

            # Retrieve actual journeys for the operating day
            actuals = await _get_actuals_by_day(operating_day_str)
            assert len(actuals) >= 1, "Should have at least one actual journey"

            # Find the one we just created
            retrieved = next((a for a in actuals if a["id"] == created["id"]), None)
            assert retrieved is not None, "Created actual journey should be retrievable"

            # Verify all fields preserved
            assert retrieved["id"] is not None
            assert isinstance(retrieved["id"], int)
            assert retrieved["carer_id"] == data["carer_id"]
            assert retrieved["operating_day"] == operating_day_str
            assert retrieved["actual_departure"] == actual_departure_str
            assert retrieved["actual_arrival"] == actual_arrival_str
            assert retrieved["actual_distance_miles"] == data["actual_distance_miles"]

            # Route coordinates round-trip
            stored_coords = json.loads(retrieved["route_coordinates"])
            assert stored_coords == data["route_coordinates"], (
                f"Route coordinates mismatch: {stored_coords} != {data['route_coordinates']}"
            )

            assert retrieved["match_status"] == "unmatched"
            assert retrieved["created_at"] is not None
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 12: State transition — departure triggers in_progress
# Feature: journey-lifecycle-management, Property 12: State transition — departure triggers in_progress
# **Validates: Requirements 4.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    carer_id=st.integers(min_value=1, max_value=10),
    dep_hour=st.integers(min_value=7, max_value=17),
    dep_minute=st.integers(min_value=0, max_value=59),
    duration_minutes=st.integers(min_value=1, max_value=120),
    distance=st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_property12_departure_triggers_in_progress(
    tmp_path, carer_id, dep_hour, dep_minute, duration_minutes, distance
):
    """Property 12: For any journey with status planned, receiving actual
    departure data should transition the journey status to in_progress.

    **Validates: Requirements 4.2**
    """
    from backend.app.models.journey import ActualJourneyCreate

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            # Set up a future operating day
            operating_day = date.today() + timedelta(days=1)
            operating_day_str = operating_day.isoformat()

            # Create a plan with a planned journey
            plan = await create_journey_plan(operating_day_str, "initial_creation", 1)

            planned_departure = datetime(
                operating_day.year, operating_day.month, operating_day.day,
                dep_hour, dep_minute, 0
            )
            planned_arrival = planned_departure + timedelta(minutes=duration_minutes)

            journey = await create_journey(
                plan_id=plan["id"],
                carer_id=carer_id,
                visit_id=None,
                origin_lat=51.5,
                origin_lng=-0.1,
                origin_label="Home",
                destination_lat=51.6,
                destination_lng=-0.2,
                destination_label="Patient",
                planned_departure=planned_departure.isoformat(),
                planned_arrival=planned_arrival.isoformat(),
                planned_distance_miles=round(distance, 1),
            )

            # Verify initial status is planned
            initial = await get_journey(journey["id"])
            assert initial["status"] == "planned"

            # Send actual departure data (within the 60-min window of the planned departure)
            actual_departure = planned_departure + timedelta(minutes=5)
            actual_arrival = actual_departure + timedelta(minutes=duration_minutes)

            actual_data = ActualJourneyCreate(
                carer_id=carer_id,
                operating_day=operating_day,
                actual_departure=actual_departure,
                actual_arrival=actual_arrival,
                actual_distance_miles=round(distance, 1),
                route_coordinates=[],
            )

            result = await service.receive_actual(actual_data)

            # Property: The matched journey should now be in_progress
            updated_journey = await get_journey(journey["id"])
            assert updated_journey["status"] == "in_progress", (
                f"Expected status 'in_progress', got '{updated_journey['status']}'"
            )

            # The actual should be matched to the planned journey
            assert result.journey_id == journey["id"]
            assert result.match_status.value == "matched"
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 13: State transition — arrival triggers completed
# Feature: journey-lifecycle-management, Property 13: State transition — arrival triggers completed
# **Validates: Requirements 4.3**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    carer_id=st.integers(min_value=1, max_value=10),
    dep_hour=st.integers(min_value=7, max_value=17),
    dep_minute=st.integers(min_value=0, max_value=59),
    duration_minutes=st.integers(min_value=1, max_value=120),
    distance=st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_property13_arrival_triggers_completed(
    tmp_path, carer_id, dep_hour, dep_minute, duration_minutes, distance
):
    """Property 13: For any journey with status in_progress, receiving actual
    arrival data should transition the journey status to completed.

    **Validates: Requirements 4.3**
    """
    from backend.app.models.journey import ActualJourneyCreate

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            # Set up a future operating day
            operating_day = date.today() + timedelta(days=1)
            operating_day_str = operating_day.isoformat()

            # Create a plan with a journey
            plan = await create_journey_plan(operating_day_str, "initial_creation", 1)

            planned_departure = datetime(
                operating_day.year, operating_day.month, operating_day.day,
                dep_hour, dep_minute, 0
            )
            planned_arrival = planned_departure + timedelta(minutes=duration_minutes)

            journey = await create_journey(
                plan_id=plan["id"],
                carer_id=carer_id,
                visit_id=None,
                origin_lat=51.5,
                origin_lng=-0.1,
                origin_label="Home",
                destination_lat=51.6,
                destination_lng=-0.2,
                destination_label="Patient",
                planned_departure=planned_departure.isoformat(),
                planned_arrival=planned_arrival.isoformat(),
                planned_distance_miles=round(distance, 1),
            )

            # Set journey to in_progress (simulating departure already received)
            await update_journey_status(journey["id"], "in_progress")

            # Verify it's in_progress
            in_progress_journey = await get_journey(journey["id"])
            assert in_progress_journey["status"] == "in_progress"

            # Send actual arrival data — this represents the second actual event
            # matching the same planned journey (now in_progress)
            actual_departure = planned_departure + timedelta(minutes=5)
            actual_arrival = actual_departure + timedelta(minutes=duration_minutes)

            actual_data = ActualJourneyCreate(
                carer_id=carer_id,
                operating_day=operating_day,
                actual_departure=actual_departure,
                actual_arrival=actual_arrival,
                actual_distance_miles=round(distance, 1),
                route_coordinates=[],
            )

            result = await service.receive_actual(actual_data)

            # Property: The matched journey should now be completed
            updated_journey = await get_journey(journey["id"])
            assert updated_journey["status"] == "completed", (
                f"Expected status 'completed', got '{updated_journey['status']}'"
            )

            # The actual should be matched
            assert result.journey_id == journey["id"]
            assert result.match_status.value == "matched"
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 14: Actual journey validation rejects invalid data
# Feature: journey-lifecycle-management, Property 14: Actual journey validation rejects invalid data
# **Validates: Requirements 4.5**
# ---------------------------------------------------------------------------


@st.composite
def st_invalid_actual_journey(draw):
    """Generate an invalid actual journey payload.

    Generates cases where:
    - actual_arrival <= actual_departure (invalid time ordering)
    """
    carer_id = draw(st.integers(min_value=1, max_value=10))
    operating_day = date.today() + timedelta(days=draw(st.integers(min_value=0, max_value=30)))

    dep_hour = draw(st.integers(min_value=7, max_value=20))
    dep_minute = draw(st.integers(min_value=0, max_value=59))
    actual_departure = datetime(
        operating_day.year, operating_day.month, operating_day.day,
        dep_hour, dep_minute, 0
    )

    # Make arrival <= departure (invalid)
    # Either equal or before
    offset_minutes = draw(st.integers(min_value=0, max_value=120))
    actual_arrival = actual_departure - timedelta(minutes=offset_minutes)

    actual_distance_miles = round(draw(st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False)), 1)

    return {
        "carer_id": carer_id,
        "operating_day": operating_day,
        "actual_departure": actual_departure,
        "actual_arrival": actual_arrival,
        "actual_distance_miles": actual_distance_miles,
        "route_coordinates": [],
    }


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=st_invalid_actual_journey())
def test_property14_actual_journey_validation_rejects_invalid_data(tmp_path, data):
    """Property 14: For any actual journey submission where the actual arrival
    time is not strictly later than the actual departure time, or where required
    fields are missing, the system should reject the data with validation errors
    identifying each invalid field.

    **Validates: Requirements 4.5**
    """
    from fastapi import HTTPException
    from backend.app.models.journey import ActualJourneyCreate

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            actual_data = ActualJourneyCreate(
                carer_id=data["carer_id"],
                operating_day=data["operating_day"],
                actual_departure=data["actual_departure"],
                actual_arrival=data["actual_arrival"],
                actual_distance_miles=data["actual_distance_miles"],
                route_coordinates=data["route_coordinates"],
            )

            # Property: Should be rejected with a validation error (422)
            try:
                await service.receive_actual(actual_data)
                assert False, (
                    "Expected HTTPException 422 but no exception was raised. "
                    f"Departure={data['actual_departure']}, Arrival={data['actual_arrival']}"
                )
            except HTTPException as exc:
                assert exc.status_code == 422, (
                    f"Expected status 422, got {exc.status_code}"
                )
                # Error should identify the invalid field(s)
                assert "arrival" in exc.detail.lower() or "departure" in exc.detail.lower(), (
                    f"Error message should reference time fields: {exc.detail}"
                )
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 15: Actual journey matching selects closest planned departure
# Feature: journey-lifecycle-management, Property 15: Actual journey matching selects closest planned departure
# **Validates: Requirements 4.6**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    carer_id=st.integers(min_value=1, max_value=10),
    base_hour=st.integers(min_value=8, max_value=14),
    base_minute=st.integers(min_value=0, max_value=30),
    offsets=st.lists(
        st.integers(min_value=5, max_value=55),
        min_size=2,
        max_size=4,
        unique=True,
    ),
    actual_offset=st.integers(min_value=0, max_value=55),
)
def test_property15_matching_selects_closest_planned_departure(
    tmp_path, carer_id, base_hour, base_minute, offsets, actual_offset
):
    """Property 15: For any actual journey with multiple candidate planned
    journeys within the 60-minute departure window (same carer, same operating
    day), the system should match to the planned journey with the closest
    departure time to the actual departure time.

    **Validates: Requirements 4.6**
    """
    from backend.app.models.journey import ActualJourneyCreate

    async def _run():
        fresh_db = _FreshDB(tmp_path)
        await fresh_db.setup()
        try:
            service = JourneyService()

            operating_day = date.today() + timedelta(days=1)
            operating_day_str = operating_day.isoformat()

            # Create plan
            plan = await create_journey_plan(operating_day_str, "initial_creation", 1)

            # Base time for all planned journeys
            base_time = datetime(
                operating_day.year, operating_day.month, operating_day.day,
                base_hour, base_minute, 0
            )

            # Create multiple planned journeys at different offsets from base_time
            # All within 60 minutes of each other so they could all be candidates
            journey_ids_with_departures = []
            for offset in sorted(offsets):
                planned_departure = base_time + timedelta(minutes=offset)
                planned_arrival = planned_departure + timedelta(minutes=30)

                journey = await create_journey(
                    plan_id=plan["id"],
                    carer_id=carer_id,
                    visit_id=None,
                    origin_lat=51.5,
                    origin_lng=-0.1,
                    origin_label="Home",
                    destination_lat=51.6,
                    destination_lng=-0.2,
                    destination_label="Patient",
                    planned_departure=planned_departure.isoformat(),
                    planned_arrival=planned_arrival.isoformat(),
                    planned_distance_miles=5.0,
                )
                journey_ids_with_departures.append((journey["id"], planned_departure))

            # The actual departure is at base_time + actual_offset minutes
            actual_departure = base_time + timedelta(minutes=actual_offset)
            actual_arrival = actual_departure + timedelta(minutes=30)

            actual_data = ActualJourneyCreate(
                carer_id=carer_id,
                operating_day=operating_day,
                actual_departure=actual_departure,
                actual_arrival=actual_arrival,
                actual_distance_miles=5.0,
                route_coordinates=[],
            )

            result = await service.receive_actual(actual_data)

            # Determine which planned journey is closest to actual_departure
            # and also within the 60-minute window
            candidates_within_window = [
                (j_id, planned_dep)
                for j_id, planned_dep in journey_ids_with_departures
                if abs((planned_dep - actual_departure).total_seconds()) <= 60 * 60
            ]

            if candidates_within_window:
                # Property: Should match to the closest planned departure
                expected_match_id = min(
                    candidates_within_window,
                    key=lambda x: abs((x[1] - actual_departure).total_seconds()),
                )[0]

                assert result.journey_id == expected_match_id, (
                    f"Expected match to journey {expected_match_id}, got {result.journey_id}. "
                    f"Actual departure: {actual_departure}, "
                    f"Candidates: {[(j_id, dep) for j_id, dep in candidates_within_window]}"
                )
                assert result.match_status.value == "matched"
            else:
                # No candidates within window — should be unmatched
                assert result.journey_id is None
                assert result.match_status.value == "unmatched"
        finally:
            await fresh_db.teardown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 24: Query filter intersection semantics
# Feature: journey-lifecycle-management, Property 24: Query filter intersection semantics
# **Validates: Requirements 8.3, 8.4**
# ---------------------------------------------------------------------------


@st.composite
def st_filter_combination(draw):
    """Generate a combination of query filters (operating_day, carer_id, status).

    At least one filter will be set. All values are valid (existing carers, valid
    statuses, valid dates) so that the test can focus on intersection semantics.
    """
    filters = {}
    # Use a fixed date that we know data exists for
    if draw(st.booleans()):
        filters["operating_day"] = date.today() + timedelta(days=draw(st.sampled_from([1, 2, 3])))
    if draw(st.booleans()):
        filters["carer_id"] = draw(st.integers(min_value=1, max_value=5))
    if draw(st.booleans()):
        filters["status"] = draw(st.sampled_from(["planned", "in_progress", "completed", "cancelled"]))
    # Ensure at least one filter
    if not filters:
        filters["carer_id"] = draw(st.integers(min_value=1, max_value=5))
    return filters


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    filter_combo=st_filter_combination(),
    num_journeys=st.integers(min_value=3, max_value=8),
)
def test_property24_query_filter_intersection_semantics(tmp_path, filter_combo, num_journeys):
    """Property 24: For any combination of query filters (operating_day, carer_id,
    status), all returned journeys should satisfy every specified filter simultaneously.
    Results should come from the latest Plan_Version for each relevant operating day.

    **Validates: Requirements 8.3, 8.4**
    """
    import uuid as _uuid
    from backend.app.models.journey import JourneyFilters, JourneyStatus

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"
        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            # Create journeys across multiple days and plan versions
            days = [
                (date.today() + timedelta(days=1)).isoformat(),
                (date.today() + timedelta(days=2)).isoformat(),
                (date.today() + timedelta(days=3)).isoformat(),
            ]
            statuses_pool = ["planned", "in_progress", "completed", "cancelled"]

            # For each day, create 2 plan versions; only latest matters
            for day_str in days:
                # v1
                plan_v1 = await create_journey_plan(day_str, "initial_creation", 1)
                for i in range(num_journeys):
                    await create_journey(
                        plan_id=plan_v1["id"],
                        carer_id=((i % 5) + 1),
                        visit_id=None,
                        origin_lat=51.5,
                        origin_lng=-0.1,
                        origin_label="Origin",
                        destination_lat=51.6,
                        destination_lng=-0.2,
                        destination_label="Dest",
                        planned_departure=f"{day_str}T{8 + i:02d}:00:00",
                        planned_arrival=f"{day_str}T{8 + i:02d}:30:00",
                        planned_distance_miles=3.0,
                    )

                # v2 (latest) — assign various statuses
                plan_v2 = await create_journey_plan(day_str, "manual_amendment", 2)
                for i in range(num_journeys):
                    j = await create_journey(
                        plan_id=plan_v2["id"],
                        carer_id=((i % 5) + 1),
                        visit_id=None,
                        origin_lat=51.5,
                        origin_lng=-0.1,
                        origin_label="Origin",
                        destination_lat=51.6,
                        destination_lng=-0.2,
                        destination_label="Dest",
                        planned_departure=f"{day_str}T{8 + i:02d}:00:00",
                        planned_arrival=f"{day_str}T{8 + i:02d}:30:00",
                        planned_distance_miles=3.0,
                    )
                    # Assign a status from the pool (distribute across)
                    status = statuses_pool[i % len(statuses_pool)]
                    if status != "planned":
                        await update_journey_status(j["id"], status)

            # Build the filter model
            filters_kwargs = {}
            if "operating_day" in filter_combo:
                filters_kwargs["operating_day"] = filter_combo["operating_day"]
            if "carer_id" in filter_combo:
                filters_kwargs["carer_id"] = filter_combo["carer_id"]
            if "status" in filter_combo:
                filters_kwargs["status"] = JourneyStatus(filter_combo["status"])

            filters = JourneyFilters(**filters_kwargs)

            # Query with large page to get all matching
            result = await service.query_journeys(filters, page=1, page_size=100)

            # Property: All returned journeys satisfy every specified filter simultaneously
            for journey in result.journeys:
                if "operating_day" in filter_combo:
                    expected_day = filter_combo["operating_day"].isoformat()
                    # Verify the journey's departure is on the specified day
                    assert journey.planned_departure.startswith(expected_day), (
                        f"Journey departure {journey.planned_departure} does not match "
                        f"filter operating_day {expected_day}"
                    )
                if "carer_id" in filter_combo:
                    assert journey.carer_id == filter_combo["carer_id"], (
                        f"Journey carer_id {journey.carer_id} does not match "
                        f"filter carer_id {filter_combo['carer_id']}"
                    )
                if "status" in filter_combo:
                    assert journey.status.value == filter_combo["status"], (
                        f"Journey status {journey.status.value} does not match "
                        f"filter status {filter_combo['status']}"
                    )

            # Property: Results come from the latest Plan_Version
            # All returned journeys should belong to plan_version 2 plans (the latest)
            for journey in result.journeys:
                plan = await get_journey_plan(journey.plan_id)
                assert plan is not None
                # It should be the latest version for its operating day
                latest_v = await get_latest_plan_version(plan["operating_day"])
                assert plan["plan_version"] == latest_v, (
                    f"Journey from plan version {plan['plan_version']} but latest is {latest_v}"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 25: Carer query ordering
# Feature: journey-lifecycle-management, Property 25: Carer query ordering
# **Validates: Requirements 8.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    carer_id=st.integers(min_value=1, max_value=5),
    num_days=st.integers(min_value=1, max_value=4),
    journeys_per_day=st.integers(min_value=1, max_value=4),
)
def test_property25_carer_query_ordering(tmp_path, carer_id, num_days, journeys_per_day):
    """Property 25: For any carer with journeys across multiple operating days,
    querying by carer ID should return journeys ordered by planned departure time
    descending, using the latest plan version for each day.

    **Validates: Requirements 8.2**
    """
    import uuid as _uuid
    from backend.app.models.journey import JourneyFilters

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"
        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            # Create journeys for the specified carer across multiple days
            for day_offset in range(1, num_days + 1):
                day_str = (date.today() + timedelta(days=day_offset)).isoformat()

                # Create plan v1 (not latest)
                plan_v1 = await create_journey_plan(day_str, "initial_creation", 1)
                for j in range(journeys_per_day):
                    await create_journey(
                        plan_id=plan_v1["id"],
                        carer_id=carer_id,
                        visit_id=None,
                        origin_lat=51.5,
                        origin_lng=-0.1,
                        origin_label="Origin",
                        destination_lat=51.6,
                        destination_lng=-0.2,
                        destination_label="Dest",
                        planned_departure=f"{day_str}T{8 + j:02d}:00:00",
                        planned_arrival=f"{day_str}T{8 + j:02d}:30:00",
                        planned_distance_miles=3.0,
                    )

                # Create plan v2 (latest) with different departure times
                plan_v2 = await create_journey_plan(day_str, "manual_amendment", 2)
                for j in range(journeys_per_day):
                    await create_journey(
                        plan_id=plan_v2["id"],
                        carer_id=carer_id,
                        visit_id=None,
                        origin_lat=51.5,
                        origin_lng=-0.1,
                        origin_label="Origin",
                        destination_lat=51.6,
                        destination_lng=-0.2,
                        destination_label="Dest",
                        planned_departure=f"{day_str}T{9 + j:02d}:15:00",
                        planned_arrival=f"{day_str}T{9 + j:02d}:45:00",
                        planned_distance_miles=4.0,
                    )

            # Query by carer_id
            filters = JourneyFilters(carer_id=carer_id)
            result = await service.query_journeys(filters, page=1, page_size=100)

            # Property: Journeys are ordered by planned departure time descending
            departures = [j.planned_departure for j in result.journeys]
            for i in range(len(departures) - 1):
                assert departures[i] >= departures[i + 1], (
                    f"Ordering violated: {departures[i]} should be >= {departures[i + 1]} "
                    f"(index {i} vs {i + 1})"
                )

            # Property: Results use the latest plan version for each day
            for journey in result.journeys:
                plan = await get_journey_plan(journey.plan_id)
                assert plan is not None
                latest_v = await get_latest_plan_version(plan["operating_day"])
                assert plan["plan_version"] == latest_v, (
                    f"Journey from plan version {plan['plan_version']} but latest is {latest_v}"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 26: Pagination correctness
# Feature: journey-lifecycle-management, Property 26: Pagination correctness
# **Validates: Requirements 8.5**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    total_journeys=st.integers(min_value=0, max_value=15),
    page=st.integers(min_value=1, max_value=10),
    page_size=st.integers(min_value=1, max_value=10),
)
def test_property26_pagination_correctness(tmp_path, total_journeys, page, page_size):
    """Property 26: For any query result set of size N, requesting page P with
    page_size S should return exactly min(S, N - (P-1)*S) results (or 0 if
    (P-1)*S >= N), and total_count should always equal N regardless of page/page_size.

    **Validates: Requirements 8.5**
    """
    import uuid as _uuid
    from backend.app.models.journey import JourneyFilters

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"
        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            # Create exactly total_journeys for a fixed carer on a single day
            day_str = (date.today() + timedelta(days=1)).isoformat()

            if total_journeys > 0:
                plan = await create_journey_plan(day_str, "initial_creation", 1)
                for i in range(total_journeys):
                    hour = 8 + (i // 4)
                    minute = (i % 4) * 15
                    await create_journey(
                        plan_id=plan["id"],
                        carer_id=1,  # Fixed carer for deterministic count
                        visit_id=None,
                        origin_lat=51.5,
                        origin_lng=-0.1,
                        origin_label="Origin",
                        destination_lat=51.6,
                        destination_lng=-0.2,
                        destination_label="Dest",
                        planned_departure=f"{day_str}T{hour:02d}:{minute:02d}:00",
                        planned_arrival=f"{day_str}T{hour:02d}:{minute + 10:02d}:00",
                        planned_distance_miles=3.0,
                    )

            # Query with specific carer to get deterministic count N = total_journeys
            filters = JourneyFilters(carer_id=1)
            result = await service.query_journeys(filters, page=page, page_size=page_size)

            N = total_journeys
            P = page
            S = page_size

            # Property: total_count always equals N
            assert result.total_count == N, (
                f"Expected total_count={N}, got {result.total_count}"
            )

            # Property: number of returned results matches the pagination formula
            offset = (P - 1) * S
            if offset >= N:
                expected_count = 0
            else:
                expected_count = min(S, N - offset)

            assert len(result.journeys) == expected_count, (
                f"With N={N}, page={P}, page_size={S}: expected {expected_count} "
                f"results, got {len(result.journeys)}"
            )

            # Property: page and page_size in result match requested values
            assert result.page == page
            assert result.page_size == page_size
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 27: Invalid filter rejection
# Feature: journey-lifecycle-management, Property 27: Invalid filter rejection
# **Validates: Requirements 8.6**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    invalid_carer_id=st.integers(min_value=100, max_value=9999),
)
def test_property27_invalid_carer_id_rejected(tmp_path, invalid_carer_id):
    """Property 27a: For any query containing a non-existent carer ID, the system
    should reject the query with an error indicating the carer_id filter is invalid.

    **Validates: Requirements 8.6**
    """
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException
    from backend.app.models.journey import JourneyFilters

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"
        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert only carers with IDs 1-10
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            # Query with a non-existent carer_id (>= 100)
            filters = JourneyFilters(carer_id=invalid_carer_id)

            try:
                await service.query_journeys(filters, page=1, page_size=20)
                assert False, "Expected HTTPException 422 but no exception was raised"
            except _HTTPException as exc:
                assert exc.status_code == 422, (
                    f"Expected status 422, got {exc.status_code}"
                )
                assert "carer_id" in exc.detail.lower() or "carer" in exc.detail.lower(), (
                    f"Error should mention carer_id filter: {exc.detail}"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    page=st.one_of(
        st.integers(min_value=-100, max_value=0),
        st.just(0),
    ),
    page_size=st.one_of(
        st.integers(min_value=-100, max_value=0),
        st.integers(min_value=101, max_value=500),
    ),
)
def test_property27_invalid_pagination_rejected(tmp_path, page, page_size):
    """Property 27b: For any query with invalid pagination parameters (page < 1
    or page_size outside 1-100), the system should reject with an error.

    **Validates: Requirements 8.6**
    """
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException
    from backend.app.models.journey import JourneyFilters

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"
        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert carers
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            filters = JourneyFilters()  # No filters, focus on pagination rejection

            # At least one of page or page_size is invalid
            try:
                await service.query_journeys(filters, page=page, page_size=page_size)
                # If page is valid (>=1) and page_size is valid (1-100), no error expected
                # But our strategy ensures at least one is invalid
                if page < 1 or page_size < 1 or page_size > 100:
                    assert False, (
                        f"Expected HTTPException 422 for page={page}, page_size={page_size} "
                        "but no exception was raised"
                    )
            except _HTTPException as exc:
                assert exc.status_code == 422, (
                    f"Expected status 422, got {exc.status_code}"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 21: Cancellation of planned journey
# Feature: journey-lifecycle-management, Property 21: Cancellation of planned journey
# **Validates: Requirements 7.1**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    carer_id=st_carer_id,
    hour=st.integers(min_value=6, max_value=20),
    minute=st.integers(min_value=0, max_value=59),
    distance=st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_property21_cancellation_of_planned_journey(tmp_path, carer_id, hour, minute, distance):
    """Property 21: For any journey with status planned, cancellation should set
    status to cancelled and record a valid UTC ISO 8601 cancellation timestamp.

    **Validates: Requirements 7.1**
    """
    import uuid as _uuid
    from datetime import timezone as _tz

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers for FK constraints
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            # Create a plan with a planned journey
            plan = await create_journey_plan("2025-06-15", "initial_creation", 1)
            journey = await create_journey(
                plan_id=plan["id"],
                carer_id=carer_id,
                visit_id=None,
                origin_lat=51.5,
                origin_lng=-0.1,
                origin_label="Home",
                destination_lat=51.6,
                destination_lng=-0.2,
                destination_label="Patient A",
                planned_departure=f"2025-06-15T{hour:02d}:{minute:02d}:00",
                planned_arrival=f"2025-06-15T{hour + 1:02d}:{minute:02d}:00" if hour < 23 else f"2025-06-15T23:59:00",
                planned_distance_miles=distance,
            )

            # Verify the journey starts as planned
            assert journey["status"] == "planned"

            # Record time before cancellation
            before_cancel = datetime.now(_tz.utc)

            # Cancel the journey
            result = await service.cancel_journey(journey["id"])

            # Property: Status is set to cancelled
            assert result.status.value == "cancelled", (
                f"Expected status 'cancelled', got '{result.status.value}'"
            )

            # Property: A valid UTC ISO 8601 cancellation timestamp is recorded
            assert result.cancelled_at is not None, "cancelled_at should be non-null"

            # Validate it's a valid ISO 8601 timestamp
            cancelled_at_dt = datetime.fromisoformat(result.cancelled_at)
            assert cancelled_at_dt is not None, "cancelled_at should be parseable as ISO 8601"

            # The timestamp should be close to the time of cancellation (within 5 seconds)
            assert cancelled_at_dt >= before_cancel - timedelta(seconds=5), (
                f"cancelled_at {cancelled_at_dt} should be >= {before_cancel - timedelta(seconds=5)}"
            )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 22: Cancellation of in-progress journey unassigns visits
# Feature: journey-lifecycle-management, Property 22: Cancellation of in-progress journey unassigns visits
# **Validates: Requirements 7.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    carer_id=st_carer_id,
    hour=st.integers(min_value=6, max_value=20),
    minute=st.integers(min_value=0, max_value=59),
    distance=st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_property22_cancellation_of_in_progress_journey_unassigns_visits(
    tmp_path, carer_id, hour, minute, distance
):
    """Property 22: For any journey with status in_progress, cancellation should
    set status to cancelled, record a UTC ISO 8601 timestamp, and mark all
    incomplete visits within the journey as unassigned.

    **Validates: Requirements 7.2**
    """
    import uuid as _uuid
    from datetime import timezone as _tz

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers for FK constraints
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                # Insert a patient for the visit FK
                await db.execute(
                    """INSERT INTO patients (id, name, address, lat, lng, preferences, priority)
                       VALUES (1, 'Patient 1', '123 Street', 51.6, -0.2, '[]', 'medium')""",
                )
                # Insert a visit linked to the patient (not cancelled initially)
                await db.execute(
                    """INSERT INTO visits (id, patient_id, duration_minutes, window_start, window_end, is_cancelled)
                       VALUES (1, 1, 30, '08:00', '12:00', 0)""",
                )
                await db.commit()

            service = JourneyService()

            # Create a plan with an in-progress journey linked to a visit
            plan = await create_journey_plan("2025-06-15", "initial_creation", 1)
            journey = await create_journey(
                plan_id=plan["id"],
                carer_id=carer_id,
                visit_id=1,  # Link to the visit we created
                origin_lat=51.5,
                origin_lng=-0.1,
                origin_label="Home",
                destination_lat=51.6,
                destination_lng=-0.2,
                destination_label="Patient 1",
                planned_departure=f"2025-06-15T{hour:02d}:{minute:02d}:00",
                planned_arrival=f"2025-06-15T{hour + 1:02d}:{minute:02d}:00" if hour < 23 else f"2025-06-15T23:59:00",
                planned_distance_miles=distance,
            )

            # Set journey to in_progress
            await update_journey_status(journey["id"], "in_progress")

            # Record time before cancellation
            before_cancel = datetime.now(_tz.utc)

            # Cancel the in-progress journey
            result = await service.cancel_journey(journey["id"])

            # Property: Status is set to cancelled
            assert result.status.value == "cancelled", (
                f"Expected status 'cancelled', got '{result.status.value}'"
            )

            # Property: A valid UTC ISO 8601 cancellation timestamp is recorded
            assert result.cancelled_at is not None, "cancelled_at should be non-null"
            cancelled_at_dt = datetime.fromisoformat(result.cancelled_at)
            assert cancelled_at_dt >= before_cancel - timedelta(seconds=5), (
                f"cancelled_at {cancelled_at_dt} should be >= {before_cancel - timedelta(seconds=5)}"
            )

            # Property: Incomplete visits within the journey are marked as unassigned (is_cancelled=1)
            async with database.get_db() as db:
                cursor = await db.execute(
                    "SELECT is_cancelled FROM visits WHERE id = ?", (1,)
                )
                visit_row = await cursor.fetchone()
                assert visit_row is not None, "Visit should still exist"
                assert visit_row[0] == 1, (
                    f"Visit should be marked as cancelled/unassigned (is_cancelled=1), got {visit_row[0]}"
                )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 23: Terminal states reject cancellation
# Feature: journey-lifecycle-management, Property 23: Terminal states reject cancellation
# **Validates: Requirements 7.3, 7.4**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    terminal_status=st.sampled_from(["completed", "cancelled"]),
    carer_id=st_carer_id,
    hour=st.integers(min_value=6, max_value=20),
    minute=st.integers(min_value=0, max_value=59),
    distance=st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_property23_terminal_states_reject_cancellation(
    tmp_path, terminal_status, carer_id, hour, minute, distance
):
    """Property 23: For any journey with status completed or cancelled, attempting
    cancellation should be rejected — completed because it cannot be undone,
    cancelled because it is already cancelled.

    **Validates: Requirements 7.3, 7.4**
    """
    import uuid as _uuid
    from fastapi import HTTPException as _HTTPException

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers for FK constraints
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, 51.5, -0.1, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}"),
                    )
                await db.commit()

            service = JourneyService()

            # Create a plan with a journey
            plan = await create_journey_plan("2025-06-15", "initial_creation", 1)
            journey = await create_journey(
                plan_id=plan["id"],
                carer_id=carer_id,
                visit_id=None,
                origin_lat=51.5,
                origin_lng=-0.1,
                origin_label="Home",
                destination_lat=51.6,
                destination_lng=-0.2,
                destination_label="Patient A",
                planned_departure=f"2025-06-15T{hour:02d}:{minute:02d}:00",
                planned_arrival=f"2025-06-15T{hour + 1:02d}:{minute:02d}:00" if hour < 23 else f"2025-06-15T23:59:00",
                planned_distance_miles=distance,
            )

            # Set journey to terminal state
            if terminal_status == "cancelled":
                await update_journey_status(
                    journey["id"], "cancelled", cancelled_at="2025-06-15T07:00:00"
                )
            else:
                await update_journey_status(journey["id"], "completed")

            # Property: Cancellation is rejected with 409
            try:
                await service.cancel_journey(journey["id"])
                assert False, (
                    f"Expected HTTPException 409 for {terminal_status} journey "
                    "but no exception was raised"
                )
            except _HTTPException as exc:
                assert exc.status_code == 409, (
                    f"Expected status code 409, got {exc.status_code}"
                )

                # Verify appropriate error message
                if terminal_status == "completed":
                    assert "completed" in exc.detail.lower() or "cannot" in exc.detail.lower(), (
                        f"Error for completed journey should mention 'completed', got: {exc.detail}"
                    )
                else:
                    assert "already cancelled" in exc.detail.lower() or "already" in exc.detail.lower(), (
                        f"Error for cancelled journey should mention 'already cancelled', got: {exc.detail}"
                    )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 2: Optimiser route conversion produces ordered planned journeys
# Feature: journey-lifecycle-management, Property 2: Optimiser route conversion produces ordered planned journeys
# **Validates: Requirements 1.2**
# ---------------------------------------------------------------------------


@st.composite
def st_route_stops(draw, patient_ids: list[int]):
    """Generate a valid list of RouteStop objects with sequential timing.

    Each stop has incrementally later times to form a valid route sequence.
    """
    from backend.app.models.optimisation import RouteStop

    num_stops = draw(st.integers(min_value=1, max_value=min(5, len(patient_ids))))
    chosen_patients = draw(
        st.lists(
            st.sampled_from(patient_ids),
            min_size=num_stops,
            max_size=num_stops,
            unique=True,
        )
    )

    stops = []
    base_hour = draw(st.integers(min_value=7, max_value=12))
    current_minutes = base_hour * 60  # Convert to minutes from midnight

    for idx, patient_id in enumerate(chosen_patients):
        travel_time = draw(st.integers(min_value=5, max_value=30))
        visit_duration = draw(st.integers(min_value=15, max_value=60))
        mileage = draw(st.floats(min_value=0.5, max_value=20.0, allow_nan=False, allow_infinity=False))

        arrival_minutes = current_minutes + travel_time
        start_minutes = arrival_minutes  # Start immediately on arrival
        end_minutes = start_minutes + visit_duration

        arrival_time = f"{arrival_minutes // 60:02d}:{arrival_minutes % 60:02d}"
        start_time = f"{start_minutes // 60:02d}:{start_minutes % 60:02d}"
        end_time = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"

        stops.append(
            RouteStop(
                visit_id=100 + idx,  # Use synthetic visit IDs
                patient_id=patient_id,
                arrival_time=arrival_time,
                start_time=start_time,
                end_time=end_time,
                travel_time_from_prev=travel_time,
                mileage_from_prev=round(mileage, 1),
            )
        )

        current_minutes = end_minutes

    return stops


@st.composite
def st_route_models(draw):
    """Generate a valid list of RouteModel objects from the optimiser.

    Each route is assigned to a unique carer with sequential stops.
    """
    from backend.app.models.optimisation import RouteModel

    # Use patient IDs 1-10 and carer IDs 1-10
    patient_ids = list(range(1, 11))
    carer_ids = list(range(1, 11))

    num_routes = draw(st.integers(min_value=1, max_value=5))
    chosen_carers = draw(
        st.lists(
            st.sampled_from(carer_ids),
            min_size=num_routes,
            max_size=num_routes,
            unique=True,
        )
    )

    routes = []
    for carer_id in chosen_carers:
        stops = draw(st_route_stops(patient_ids))
        total_travel = sum(s.travel_time_from_prev for s in stops)
        total_mileage = sum(s.mileage_from_prev for s in stops)

        routes.append(
            RouteModel(
                carer_id=carer_id,
                stops=stops,
                total_travel_minutes=total_travel,
                total_mileage=round(total_mileage, 1),
                total_cost=round(total_mileage * 0.45, 2),
            )
        )

    return routes


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(routes=st_route_models())
def test_property2_optimiser_route_conversion_produces_ordered_planned_journeys(tmp_path, routes):
    """Property 2: For any valid list of RouteModel outputs from the optimiser,
    converting them to a journey plan should produce journeys ordered by planned
    departure time within each carer's route, with all Journey_Status values set
    to planned.

    **Validates: Requirements 1.2**
    """
    import uuid as _uuid
    from datetime import date as _date, timedelta as _timedelta

    async def _run():
        db_path = tmp_path / f"test_{_uuid.uuid4().hex}.db"

        _patch_path = patch.object(database, "DB_PATH", db_path)
        _patch_dir = patch.object(database, "DB_DIR", tmp_path)
        _patch_path.start()
        _patch_dir.start()

        try:
            async with aiosqlite.connect(str(db_path)) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript(_SCHEMA_SQL)
                await db.commit()

            # Insert test carers (IDs 1-10) with home locations
            async with database.get_db() as db:
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                           VALUES (?, ?, ?, ?, '["driving"]', 8.0, 6.0, 30)""",
                        (i, f"Carer {i}", 51.5 + i * 0.01, -0.1 + i * 0.01),
                    )
                # Insert test patients (IDs 1-10) with locations
                for i in range(1, 11):
                    await db.execute(
                        """INSERT INTO patients (id, name, address, lat, lng, preferences, priority)
                           VALUES (?, ?, ?, ?, ?, '[]', 'medium')""",
                        (i, f"Patient {i}", f"{i} Test Street", 51.6 + i * 0.01, -0.2 + i * 0.01),
                    )
                # Insert synthetic visits referenced by route stops
                for i in range(100, 110):
                    await db.execute(
                        """INSERT INTO visits (id, patient_id, duration_minutes, window_start, window_end)
                           VALUES (?, 1, 30, '08:00', '12:00')""",
                        (i,),
                    )
                await db.commit()

            service = JourneyService()

            # Use a valid future operating day
            operating_day = _date.today() + _timedelta(days=7)

            # Call create_plan_from_optimiser
            plan = await service.create_plan_from_optimiser(
                operating_day=operating_day, routes=routes
            )

            # Property: All journeys have status "planned"
            for journey in plan.journeys:
                assert journey.status.value == "planned", (
                    f"Expected status 'planned', got '{journey.status.value}' "
                    f"for journey {journey.id}"
                )

            # Property: Journeys are ordered by planned departure time within each carer
            from itertools import groupby

            carer_journeys: dict[int, list] = {}
            for journey in plan.journeys:
                carer_journeys.setdefault(journey.carer_id, []).append(journey)

            for carer_id, journeys in carer_journeys.items():
                departure_times = [j.planned_departure for j in journeys]
                assert departure_times == sorted(departure_times), (
                    f"Journeys for carer {carer_id} are not ordered by planned "
                    f"departure time. Got: {departure_times}"
                )

            # Also verify we got the expected number of journeys
            # Each route with N stops produces N journeys (home->first, then between stops)
            expected_count = sum(len(r.stops) for r in routes)
            assert len(plan.journeys) == expected_count, (
                f"Expected {expected_count} journeys from {len(routes)} routes, "
                f"got {len(plan.journeys)}"
            )
        finally:
            _patch_path.stop()
            _patch_dir.stop()

    asyncio.run(_run())
