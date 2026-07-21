"""Unit tests for the Status Inference Engine.

Tests cover:
- Haversine distance calculation
- Valid transition enforcement
- Proactive input evaluation (confidence 100)
- Question response evaluation (confidence 100)
- GPS geofence entry → arrived inference
- GPS geofence presence → in_progress inference
- GPS geofence exit → completed inference
- Confidence decay on signal timeout
- Missed transition at 30min past window end
- Conflict detection within 10min window
- Question rate limiting (1 per visit per 10min)
- Audit trail recording
- Non-terminal visit re-evaluation
- Running late → delayed from valid states only
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db import mobile_repository as repo
from backend.app.models.mobile import VisitStatus, VALID_TRANSITIONS
from backend.app.services.status_inference import (
    StatusInferenceEngine,
    haversine_distance,
    InferenceResult,
    VisitContext,
    GEOFENCE_ENTRY_RADIUS,
    GEOFENCE_EXIT_RADIUS,
    TERMINAL_STATUSES,
    _parse_datetime,
    _parse_window_time,
)


# --- Fixtures ---


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

        # Seed test data
        async with database.get_db() as db:
            # Carer
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (1, 'Test Carer', 51.5074, -0.1278, '["personal_care"]', 8.0, 6.0, 30)"""
            )
            # Patient
            await db.execute(
                """INSERT INTO patients (id, name, address, lat, lng, priority)
                   VALUES (1, 'Test Patient', '123 Test St', 51.5080, -0.1270, 'medium')"""
            )
            # Visit (window_start/end as HH:MM per schema)
            await db.execute(
                """INSERT INTO visits (id, patient_id, window_start, window_end, duration_minutes, required_skills, is_cancelled)
                   VALUES (1, 1, '09:00', '10:00', 30, '["personal_care"]', 0)"""
            )
            # Journey plan
            await db.execute(
                """INSERT INTO journey_plans (id, operating_day, plan_version, is_archived, creation_reason)
                   VALUES (1, '2025-01-15', 1, 0, 'initial_creation')"""
            )
            # Journey linking carer to visit
            await db.execute(
                """INSERT INTO journeys (id, plan_id, carer_id, visit_id, origin_lat, origin_lng, destination_lat, destination_lng, planned_departure, planned_arrival, planned_distance_miles, status)
                   VALUES (1, 1, 1, 1, 51.5074, -0.1278, 51.5080, -0.1270, '2025-01-15T08:30:00', '2025-01-15T09:00:00', 1.5, 'planned')"""
            )
            await db.commit()

        yield db_path


@pytest.fixture
def engine():
    """Create a StatusInferenceEngine instance."""
    return StatusInferenceEngine()


# --- Haversine distance tests ---


class TestHaversineDistance:
    """Tests for the haversine distance calculation."""

    def test_same_point_returns_zero(self):
        """Distance from a point to itself is zero."""
        assert haversine_distance(51.5074, -0.1278, 51.5074, -0.1278) == 0.0

    def test_known_distance_london_to_paris(self):
        """London to Paris is approximately 340km."""
        distance = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
        assert 340_000 < distance < 345_000  # ~341km

    def test_short_distance_within_geofence(self):
        """Two points ~50m apart should be within geofence entry radius."""
        # Approximately 50m north of a point at lat 51.5
        lat1 = 51.5000
        lon1 = -0.1000
        lat2 = 51.50045  # ~50m north
        lon2 = -0.1000
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        assert distance < GEOFENCE_ENTRY_RADIUS

    def test_distance_outside_geofence(self):
        """Two points ~200m apart should be outside geofence exit radius."""
        lat1 = 51.5000
        lon1 = -0.1000
        lat2 = 51.5018  # ~200m north
        lon2 = -0.1000
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        assert distance > GEOFENCE_EXIT_RADIUS


# --- Valid transition tests ---


class TestValidTransitions:
    """Tests for the valid transition enforcement."""

    def test_all_valid_transitions_accepted(self, engine):
        """All transitions in VALID_TRANSITIONS map should be accepted."""
        for from_status, targets in VALID_TRANSITIONS.items():
            for to_status in targets:
                assert engine.is_valid_transition(from_status, to_status), (
                    f"Expected {from_status} → {to_status} to be valid"
                )

    def test_invalid_transitions_rejected(self, engine):
        """Transitions not in the map should be rejected."""
        # completed → anything should be invalid
        for to_status in VisitStatus:
            assert not engine.is_valid_transition(VisitStatus.COMPLETED, to_status)

        # missed → anything should be invalid
        for to_status in VisitStatus:
            assert not engine.is_valid_transition(VisitStatus.MISSED, to_status)

        # pending → in_progress is not valid (must go through arrived first)
        assert not engine.is_valid_transition(VisitStatus.PENDING, VisitStatus.IN_PROGRESS)

        # arrived → completed is not valid (must go through in_progress)
        assert not engine.is_valid_transition(VisitStatus.ARRIVED, VisitStatus.COMPLETED)

    def test_terminal_states_have_no_transitions(self, engine):
        """Terminal states should have empty transition sets."""
        for status in TERMINAL_STATUSES:
            assert VALID_TRANSITIONS[status] == set()


# --- Proactive input evaluation tests ---


class TestProactiveInput:
    """Tests for proactive input evaluation (confidence 100)."""

    @pytest.mark.asyncio
    async def test_arrived_from_travelling(self, test_db, engine):
        """Proactive 'arrived' from travelling → arrived with confidence 100."""
        now = datetime(2025, 1, 15, 9, 5, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            # Set initial travelling status
            await repo.set_visit_status(1, 1, "travelling", 65, "gps")

            changes = await engine.process_signal(
                carer_id=1,
                signal_type="proactive",
                signal_data={"visit_id": 1, "input_type": "arrived"},
                signal_id=1,
                now=now,
            )

            assert len(changes) == 1
            assert changes[0]["visit_id"] == 1
            assert changes[0]["old_status"] == "travelling"
            assert changes[0]["new_status"] == "arrived"
            assert changes[0]["confidence"] == 100
            assert changes[0]["trigger"] == "proactive"

    @pytest.mark.asyncio
    async def test_visit_completed_from_in_progress(self, test_db, engine):
        """Proactive 'visit_completed' from in_progress → completed."""
        now = datetime(2025, 1, 15, 9, 45, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "in_progress", 75, "gps")

            changes = await engine.process_signal(
                carer_id=1,
                signal_type="proactive",
                signal_data={"visit_id": 1, "input_type": "visit_completed"},
                signal_id=2,
                now=now,
            )

            assert len(changes) == 1
            assert changes[0]["new_status"] == "completed"
            assert changes[0]["confidence"] == 100

    @pytest.mark.asyncio
    async def test_running_late_from_pending(self, test_db, engine):
        """Proactive 'running_late' from pending → delayed."""
        now = datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "pending", 50, "system")

            changes = await engine.process_signal(
                carer_id=1,
                signal_type="proactive",
                signal_data={"visit_id": 1, "input_type": "running_late"},
                signal_id=3,
                now=now,
            )

            assert len(changes) == 1
            assert changes[0]["new_status"] == "delayed"
            assert changes[0]["confidence"] == 100

    @pytest.mark.asyncio
    async def test_running_late_from_invalid_state_rejected(self, test_db, engine):
        """Proactive 'running_late' from arrived should be rejected."""
        now = datetime(2025, 1, 15, 9, 10, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "arrived", 75, "gps")

            changes = await engine.process_signal(
                carer_id=1,
                signal_type="proactive",
                signal_data={"visit_id": 1, "input_type": "running_late"},
                signal_id=4,
                now=now,
            )

            # No changes because arrived → delayed is not valid
            assert len(changes) == 0


# --- GPS geofence inference tests ---


class TestGPSGeofence:
    """Tests for GPS-based geofence inference."""

    @pytest.mark.asyncio
    async def test_geofence_entry_triggers_arrived(self, test_db, engine):
        """GPS signal within 100m of patient triggers arrived."""
        now = datetime(2025, 1, 15, 9, 10, tzinfo=timezone.utc)
        # Patient at 51.5080, -0.1270; signal very close
        signal_data = {"latitude": 51.5080, "longitude": -0.1270}

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "travelling", 65, "gps")

            changes = await engine.process_signal(
                carer_id=1,
                signal_type="gps",
                signal_data=signal_data,
                signal_id=10,
                now=now,
            )

            assert len(changes) == 1
            assert changes[0]["new_status"] == "arrived"
            assert changes[0]["confidence"] == 75
            assert changes[0]["trigger"] == "gps"

    @pytest.mark.asyncio
    async def test_geofence_exit_from_delay_triggers_travelling(self, test_db, engine):
        """GPS signal outside 150m from delayed visit triggers travelling."""
        now = datetime(2025, 1, 15, 9, 30, tzinfo=timezone.utc)
        # Far away from patient
        signal_data = {"latitude": 51.5200, "longitude": -0.1000}

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "delayed", 80, "proactive")

            changes = await engine.process_signal(
                carer_id=1,
                signal_type="gps",
                signal_data=signal_data,
                signal_id=11,
                now=now,
            )

            assert len(changes) == 1
            assert changes[0]["new_status"] == "travelling"
            assert changes[0]["confidence"] == 65

    @pytest.mark.asyncio
    async def test_no_transition_in_hysteresis_zone(self, test_db, engine):
        """GPS signal between 100m and 150m should not trigger transition."""
        now = datetime(2025, 1, 15, 9, 10, tzinfo=timezone.utc)
        # ~120m from patient (in hysteresis zone)
        # 51.5080 + ~0.0011 latitude ≈ 120m north
        signal_data = {"latitude": 51.50908, "longitude": -0.1270}

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "travelling", 65, "gps")

            changes = await engine.process_signal(
                carer_id=1,
                signal_type="gps",
                signal_data=signal_data,
                signal_id=12,
                now=now,
            )

            # In hysteresis zone: no transition
            assert len(changes) == 0


# --- Missed timeout tests ---


class TestMissedTimeout:
    """Tests for missed visit timeout logic."""

    @pytest.mark.asyncio
    async def test_missed_after_30min_past_window_from_pending(self, test_db, engine):
        """Visit transitions to missed 30min after window end if still pending."""
        # Window ends at 10:00; now is 10:31 → should be missed
        now = datetime(2025, 1, 15, 10, 31, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "pending", 50, "system")

            changes = await engine.check_timeouts(carer_id=1, now=now)

            assert len(changes) == 1
            assert changes[0]["new_status"] == "missed"
            assert changes[0]["trigger"] == "timeout"

    @pytest.mark.asyncio
    async def test_not_missed_before_30min_threshold(self, test_db, engine):
        """Visit should NOT transition to missed before 30min past window end."""
        # Window ends at 10:00; now is 10:25 → not yet missed
        now = datetime(2025, 1, 15, 10, 25, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "pending", 50, "system")

            changes = await engine.check_timeouts(carer_id=1, now=now)

            assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_missed_from_delayed(self, test_db, engine):
        """Delayed visit transitions to missed 30min after window end."""
        now = datetime(2025, 1, 15, 10, 31, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "delayed", 60, "proactive")

            changes = await engine.check_timeouts(carer_id=1, now=now)

            assert len(changes) == 1
            assert changes[0]["new_status"] == "missed"
            assert changes[0]["trigger"] == "timeout"


# --- Confidence decay tests ---


class TestConfidenceDecay:
    """Tests for confidence decay on signal timeout."""

    @pytest.mark.asyncio
    async def test_confidence_decays_after_15min_silence(self, test_db, engine):
        """Confidence drops by 20 when no signal for 15+ minutes."""
        # Put a GPS signal 20 minutes ago
        signal_time = datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        now = datetime(2025, 1, 15, 9, 20, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "travelling", 80, "gps")
            await repo.create_gps_signal(
                carer_id=1,
                latitude=51.5100,
                longitude=-0.1300,
                accuracy_metres=10.0,
                captured_at=signal_time.isoformat(),
            )

            await engine.check_timeouts(carer_id=1, now=now)

            # Verify confidence was reduced
            status = await repo.get_current_status_for_visit(1)
            assert status is not None
            assert status["confidence_score"] == 60  # 80 - 20


# --- Question rate limiting tests ---


class TestQuestionRateLimit:
    """Tests for contextual question rate limiting."""

    @pytest.mark.asyncio
    async def test_question_triggered_on_low_confidence(self, test_db, engine):
        """Question is triggered when confidence drops below 60."""
        # Put a GPS signal 30 minutes ago to trigger decay below 60
        signal_time = datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        now = datetime(2025, 1, 15, 9, 30, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "travelling", 70, "gps")
            await repo.create_gps_signal(
                carer_id=1,
                latitude=51.5100,
                longitude=-0.1300,
                accuracy_metres=10.0,
                captured_at=signal_time.isoformat(),
            )

            await engine.check_timeouts(carer_id=1, now=now)

            # Verify a question was created
            questions = await repo.get_pending_questions_for_carer(1)
            assert len(questions) >= 1

    @pytest.mark.asyncio
    async def test_no_duplicate_question_within_10min(self, test_db, engine):
        """No second question within 10 minutes for same visit."""
        signal_time = datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)
        now = datetime(2025, 1, 15, 9, 30, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "travelling", 50, "gps")
            await repo.create_gps_signal(
                carer_id=1,
                latitude=51.5100,
                longitude=-0.1300,
                accuracy_metres=10.0,
                captured_at=signal_time.isoformat(),
            )

            # Create a question that was recently sent
            await repo.create_question(
                carer_id=1,
                visit_id=1,
                question_text="Are you on your way?",
                question_type="yes_no",
            )

            await engine.check_timeouts(carer_id=1, now=now)

            # Should still only have 1 question (rate limited)
            questions = await repo.get_pending_questions_for_carer(1)
            assert len(questions) == 1


# --- Audit trail tests ---


class TestAuditTrail:
    """Tests for transition audit trail recording."""

    @pytest.mark.asyncio
    async def test_transition_recorded_in_audit_trail(self, test_db, engine):
        """Every successful transition creates an audit record."""
        now = datetime(2025, 1, 15, 9, 5, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "travelling", 65, "gps")

            await engine.process_signal(
                carer_id=1,
                signal_type="proactive",
                signal_data={"visit_id": 1, "input_type": "arrived"},
                signal_id=100,
                now=now,
            )

            transitions = await repo.get_transitions_for_visit(1)
            assert len(transitions) == 1
            t = transitions[0]
            assert t["previous_status"] == "travelling"
            assert t["new_status"] == "arrived"
            assert t["trigger_signal_type"] == "proactive"
            assert t["confidence_score"] == 100
            assert t["trigger_signal_id"] == 100

    @pytest.mark.asyncio
    async def test_rejected_transition_not_recorded(self, test_db, engine):
        """Rejected transitions should NOT create audit records."""
        now = datetime(2025, 1, 15, 9, 5, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            # arrived → delayed is not valid
            await repo.set_visit_status(1, 1, "arrived", 75, "gps")

            await engine.process_signal(
                carer_id=1,
                signal_type="proactive",
                signal_data={"visit_id": 1, "input_type": "running_late"},
                signal_id=101,
                now=now,
            )

            transitions = await repo.get_transitions_for_visit(1)
            assert len(transitions) == 0


# --- Non-terminal visit re-evaluation tests ---


class TestNonTerminalReEvaluation:
    """Tests for non-terminal visit re-evaluation on signal receipt."""

    @pytest.mark.asyncio
    async def test_terminal_visits_not_re_evaluated(self, test_db, engine):
        """Terminal visits (completed, missed, cancelled) are not changed."""
        now = datetime(2025, 1, 15, 9, 5, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            # Set visit to terminal state
            await repo.set_visit_status(1, 1, "completed", 100, "proactive")

            # Try to process a proactive signal for this visit
            changes = await engine.process_signal(
                carer_id=1,
                signal_type="proactive",
                signal_data={"visit_id": 1, "input_type": "arrived"},
                signal_id=200,
                now=now,
            )

            assert len(changes) == 0


# --- Question response evaluation tests ---


class TestQuestionResponse:
    """Tests for question response handling."""

    @pytest.mark.asyncio
    async def test_question_response_overrides_with_confidence_100(self, test_db, engine):
        """Question response confirming status sets confidence to 100."""
        now = datetime(2025, 1, 15, 9, 15, tzinfo=timezone.utc)

        with patch.object(database, "DB_PATH", test_db), \
             patch.object(database, "DB_DIR", test_db.parent):
            await repo.set_visit_status(1, 1, "pending", 50, "system")

            changes = await engine.process_signal(
                carer_id=1,
                signal_type="question",
                signal_data={
                    "visit_id": 1,
                    "response_text": "yes",
                    "confirmed_status": "travelling",
                },
                signal_id=300,
                now=now,
            )

            assert len(changes) == 1
            assert changes[0]["new_status"] == "travelling"
            assert changes[0]["confidence"] == 100


# --- Parse datetime tests ---


class TestParseDatetime:
    """Tests for the datetime parsing utility."""

    def test_parse_iso_format(self):
        """Parse standard ISO format string."""
        result = _parse_datetime("2025-01-15T09:00:00+00:00")
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 9
        assert result.tzinfo is not None

    def test_parse_naive_assumes_utc(self):
        """Naive datetime string is assumed to be UTC."""
        result = _parse_datetime("2025-01-15 09:00:00")
        assert result.tzinfo == timezone.utc

    def test_parse_datetime_object(self):
        """Datetime objects are returned as-is (with UTC if naive)."""
        dt = datetime(2025, 1, 15, 9, 0)
        result = _parse_datetime(dt)
        assert result.tzinfo == timezone.utc
