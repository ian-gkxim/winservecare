"""Tests for the mobile repository data access layer."""

from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db import mobile_repository
from backend.app.db import journey_repository


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

        # Insert test data for FK constraints
        async with database.get_db() as db:
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills,
                   max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (1, 'Test Carer', 51.5, -0.1, '["medication"]',
                   8.0, 6.0, 30)"""
            )
            await db.execute(
                """INSERT INTO patients (id, name, address, lat, lng,
                   preferences, priority)
                   VALUES (1, 'Test Patient', '123 Test St', 51.51, -0.09,
                   '[]', 'medium')"""
            )
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes,
                   window_start, window_end, required_skills)
                   VALUES (1, 1, 30, '09:00', '10:00', '["medication"]')"""
            )
            await db.commit()

        yield


# --- Carer Auth tests ---


@pytest.mark.asyncio
async def test_create_and_get_auth(test_db):
    """Test creating and retrieving a carer auth record."""
    auth = await mobile_repository.create_auth(
        carer_id=1,
        password_hash="hashed_pw_123",
        device_token="fcm_token_abc",
        device_platform="android",
    )
    assert auth["carer_id"] == 1
    assert auth["password_hash"] == "hashed_pw_123"
    assert auth["device_token"] == "fcm_token_abc"
    assert auth["device_platform"] == "android"
    assert auth["failed_login_attempts"] == 0

    fetched = await mobile_repository.get_auth_by_carer_id(1)
    assert fetched is not None
    assert fetched["id"] == auth["id"]


@pytest.mark.asyncio
async def test_get_auth_nonexistent(test_db):
    """Test that get_auth_by_carer_id returns None for non-existent carer."""
    result = await mobile_repository.get_auth_by_carer_id(999)
    assert result is None


@pytest.mark.asyncio
async def test_increment_and_reset_failed_logins(test_db):
    """Test failed login counter increment and reset."""
    await mobile_repository.create_auth(carer_id=1, password_hash="pw")

    count = await mobile_repository.increment_failed_logins(1)
    assert count == 1

    count = await mobile_repository.increment_failed_logins(1)
    assert count == 2

    await mobile_repository.reset_failed_logins(1)
    auth = await mobile_repository.get_auth_by_carer_id(1)
    assert auth["failed_login_attempts"] == 0
    assert auth["lockout_until"] is None


@pytest.mark.asyncio
async def test_set_lockout(test_db):
    """Test setting a lockout timestamp."""
    await mobile_repository.create_auth(carer_id=1, password_hash="pw")
    await mobile_repository.set_lockout(1, "2024-01-01T12:01:00")

    auth = await mobile_repository.get_auth_by_carer_id(1)
    assert auth["lockout_until"] == "2024-01-01T12:01:00"


@pytest.mark.asyncio
async def test_update_refresh_token(test_db):
    """Test updating a refresh token."""
    await mobile_repository.create_auth(carer_id=1, password_hash="pw")
    await mobile_repository.update_refresh_token(
        1, "new_token_xyz", "2024-01-08T12:00:00"
    )

    auth = await mobile_repository.get_auth_by_carer_id(1)
    assert auth["refresh_token"] == "new_token_xyz"
    assert auth["refresh_token_expires_at"] == "2024-01-08T12:00:00"


@pytest.mark.asyncio
async def test_update_device_token(test_db):
    """Test updating the device token."""
    await mobile_repository.create_auth(carer_id=1, password_hash="pw")
    await mobile_repository.update_device_token(1, "new_device_token", "ios")

    auth = await mobile_repository.get_auth_by_carer_id(1)
    assert auth["device_token"] == "new_device_token"
    assert auth["device_platform"] == "ios"


# --- GPS Signals tests ---


@pytest.mark.asyncio
async def test_create_gps_signal(test_db):
    """Test creating a single GPS signal."""
    signal = await mobile_repository.create_gps_signal(
        carer_id=1,
        latitude=51.5074,
        longitude=-0.1278,
        accuracy_metres=10.5,
        captured_at="2024-01-01T09:00:00",
        low_accuracy=False,
        visit_id=1,
        geofence_state="inside",
    )
    assert signal["carer_id"] == 1
    assert signal["latitude"] == 51.5074
    assert signal["geofence_state"] == "inside"
    assert signal["low_accuracy"] == 0


@pytest.mark.asyncio
async def test_create_gps_signals_batch(test_db):
    """Test batch creation of GPS signals."""
    signals_data = [
        {"latitude": 51.50, "longitude": -0.12, "accuracy_metres": 8.0,
         "captured_at": "2024-01-01T09:00:00"},
        {"latitude": 51.51, "longitude": -0.13, "accuracy_metres": 12.0,
         "captured_at": "2024-01-01T09:01:00"},
        {"latitude": 51.52, "longitude": -0.14, "accuracy_metres": 55.0,
         "captured_at": "2024-01-01T09:02:00", "low_accuracy": True},
    ]
    results = await mobile_repository.create_gps_signals_batch(1, signals_data)
    assert len(results) == 3
    assert results[0]["latitude"] == 51.50
    assert results[2]["low_accuracy"] == 1


@pytest.mark.asyncio
async def test_get_recent_signals_for_carer(test_db):
    """Test retrieving recent GPS signals."""
    for i in range(5):
        await mobile_repository.create_gps_signal(
            carer_id=1, latitude=51.5 + i * 0.01, longitude=-0.1,
            accuracy_metres=10.0, captured_at=f"2024-01-01T09:0{i}:00",
        )

    signals = await mobile_repository.get_recent_signals_for_carer(1, limit=3)
    assert len(signals) == 3
    # Should be ordered by captured_at DESC
    assert signals[0]["captured_at"] == "2024-01-01T09:04:00"


# --- Contextual Questions tests ---


@pytest.mark.asyncio
async def test_create_and_get_pending_questions(test_db):
    """Test creating questions and retrieving pending ones."""
    q1 = await mobile_repository.create_question(
        carer_id=1, visit_id=1,
        question_text="Have you arrived?",
        question_type="yes_no",
    )
    assert q1["status"] == "sent"
    assert q1["question_type"] == "yes_no"

    q2 = await mobile_repository.create_question(
        carer_id=1, visit_id=1,
        question_text="Which task did you start?",
        question_type="single_choice",
        options=["Medication", "Personal Care", "Meal Prep"],
    )
    assert q2["options"] is not None

    pending = await mobile_repository.get_pending_questions_for_carer(1)
    assert len(pending) == 2


@pytest.mark.asyncio
async def test_update_question_response(test_db):
    """Test recording a question response."""
    q = await mobile_repository.create_question(
        carer_id=1, visit_id=1,
        question_text="Are you at the patient?",
        question_type="yes_no",
    )
    updated = await mobile_repository.update_question_response(
        q["id"], "yes", "2024-01-01T09:10:00"
    )
    assert updated["status"] == "answered"
    assert updated["response_text"] == "yes"

    pending = await mobile_repository.get_pending_questions_for_carer(1)
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_update_question_timeout(test_db):
    """Test marking a question as timed out."""
    q = await mobile_repository.create_question(
        carer_id=1, visit_id=1,
        question_text="Still there?",
        question_type="yes_no",
    )
    updated = await mobile_repository.update_question_timeout(
        q["id"], "2024-01-01T09:15:00"
    )
    assert updated["status"] == "timed_out"
    assert updated["timed_out_at"] == "2024-01-01T09:15:00"


@pytest.mark.asyncio
async def test_update_question_response_not_found(test_db):
    """Test that updating a non-existent question returns None."""
    result = await mobile_repository.update_question_response(
        999, "yes", "2024-01-01T09:10:00"
    )
    assert result is None


@pytest.mark.asyncio
async def test_get_recent_questions_for_visit(test_db):
    """Test rate-limit query for recent questions per visit."""
    await mobile_repository.create_question(
        carer_id=1, visit_id=1,
        question_text="Q1", question_type="yes_no",
    )
    recent = await mobile_repository.get_recent_questions_for_visit(1, minutes=10)
    assert len(recent) >= 1


# --- Proactive Inputs tests ---


@pytest.mark.asyncio
async def test_create_proactive_input(test_db):
    """Test creating a proactive input."""
    inp = await mobile_repository.create_proactive_input(
        carer_id=1, visit_id=1, input_type="arrived",
        captured_at="2024-01-01T09:05:00",
        latitude=51.51, longitude=-0.09,
    )
    assert inp["input_type"] == "arrived"
    assert inp["location_unavailable"] == 0


@pytest.mark.asyncio
async def test_create_proactive_input_location_unavailable(test_db):
    """Test creating a proactive input without location."""
    inp = await mobile_repository.create_proactive_input(
        carer_id=1, visit_id=1, input_type="running_late",
        captured_at="2024-01-01T08:50:00",
        note="Traffic on M25",
        location_unavailable=True,
    )
    assert inp["location_unavailable"] == 1
    assert inp["latitude"] is None
    assert inp["note"] == "Traffic on M25"


@pytest.mark.asyncio
async def test_get_inputs_for_visit(test_db):
    """Test retrieving proactive inputs for a visit."""
    await mobile_repository.create_proactive_input(
        carer_id=1, visit_id=1, input_type="arrived",
        captured_at="2024-01-01T09:05:00",
    )
    await mobile_repository.create_proactive_input(
        carer_id=1, visit_id=1, input_type="visit_started",
        captured_at="2024-01-01T09:06:00",
    )
    inputs = await mobile_repository.get_inputs_for_visit(1)
    assert len(inputs) == 2
    assert inputs[0]["input_type"] == "arrived"
    assert inputs[1]["input_type"] == "visit_started"


# --- Visit Status tests ---


@pytest.mark.asyncio
async def test_set_and_get_visit_status(test_db):
    """Test setting visit status and retrieving current status."""
    status = await mobile_repository.set_visit_status(
        visit_id=1, carer_id=1, status="pending",
        confidence_score=80, inferred_by="system",
    )
    assert status["status"] == "pending"
    assert status["is_current"] == 1

    current = await mobile_repository.get_current_status_for_visit(1)
    assert current is not None
    assert current["status"] == "pending"


@pytest.mark.asyncio
async def test_set_visit_status_marks_previous_not_current(test_db):
    """Test that setting a new status marks the previous as non-current."""
    await mobile_repository.set_visit_status(
        visit_id=1, carer_id=1, status="pending",
        confidence_score=80, inferred_by="system",
    )
    await mobile_repository.set_visit_status(
        visit_id=1, carer_id=1, status="travelling",
        confidence_score=70, inferred_by="gps",
    )

    current = await mobile_repository.get_current_status_for_visit(1)
    assert current["status"] == "travelling"

    statuses = await mobile_repository.get_current_statuses_for_carer(1)
    assert len(statuses) == 1
    assert statuses[0]["status"] == "travelling"


@pytest.mark.asyncio
async def test_get_current_status_nonexistent(test_db):
    """Test that getting status for a visit with no status returns None."""
    result = await mobile_repository.get_current_status_for_visit(1)
    assert result is None


# --- Visit Status Transitions tests ---


@pytest.mark.asyncio
async def test_create_and_get_transitions(test_db):
    """Test creating and retrieving status transitions."""
    t1 = await mobile_repository.create_transition(
        visit_id=1, previous_status="pending", new_status="travelling",
        trigger_signal_type="gps", confidence_score=70,
    )
    assert t1["previous_status"] == "pending"
    assert t1["new_status"] == "travelling"

    t2 = await mobile_repository.create_transition(
        visit_id=1, previous_status="travelling", new_status="arrived",
        trigger_signal_type="gps", confidence_score=85,
        trigger_signal_id=42,
    )
    assert t2["trigger_signal_id"] == 42

    transitions = await mobile_repository.get_transitions_for_visit(1)
    assert len(transitions) == 2
    assert transitions[0]["new_status"] == "travelling"
    assert transitions[1]["new_status"] == "arrived"


# --- Push Notifications tests ---


@pytest.mark.asyncio
async def test_create_and_get_notifications(test_db):
    """Test creating and retrieving push notifications."""
    notif = await mobile_repository.create_notification(
        carer_id=1,
        notification_type="contextual_question",
        payload={"question_id": 1, "text": "Have you arrived?"},
    )
    assert notif["notification_type"] == "contextual_question"
    assert notif["status"] == "pending"
    assert notif["retry_count"] == 0

    recent = await mobile_repository.get_recent_notifications_for_carer(1)
    assert len(recent) == 1


@pytest.mark.asyncio
async def test_update_notification_status(test_db):
    """Test updating notification delivery status."""
    notif = await mobile_repository.create_notification(
        carer_id=1, notification_type="general",
        payload='{"msg": "test"}',
    )
    updated = await mobile_repository.update_notification_status(
        notif["id"], status="delivered",
        sent_at="2024-01-01T09:00:00",
        delivered_at="2024-01-01T09:00:02",
    )
    assert updated["status"] == "delivered"
    assert updated["sent_at"] == "2024-01-01T09:00:00"
    assert updated["delivered_at"] == "2024-01-01T09:00:02"


@pytest.mark.asyncio
async def test_update_notification_status_not_found(test_db):
    """Test that updating a non-existent notification returns None."""
    result = await mobile_repository.update_notification_status(999, "delivered")
    assert result is None


@pytest.mark.asyncio
async def test_update_notification_increment_retry(test_db):
    """Test incrementing retry count on notification."""
    notif = await mobile_repository.create_notification(
        carer_id=1, notification_type="general", payload="{}",
    )
    updated = await mobile_repository.update_notification_status(
        notif["id"], status="failed", increment_retry=True,
    )
    assert updated["retry_count"] == 1


@pytest.mark.asyncio
async def test_count_notifications_in_window(test_db):
    """Test counting notifications in a time window for rate limiting."""
    for _ in range(5):
        await mobile_repository.create_notification(
            carer_id=1, notification_type="general", payload="{}",
        )
    count = await mobile_repository.count_notifications_in_window(
        1, window_minutes=60
    )
    assert count == 5


# --- Schedule tests ---


@pytest.mark.asyncio
async def test_get_carer_schedule_for_today_no_plan(test_db):
    """Test that schedule returns empty list when no journey plan exists."""
    schedule = await mobile_repository.get_carer_schedule_for_today(
        1, "2024-01-01"
    )
    assert schedule == []


@pytest.mark.asyncio
async def test_get_carer_schedule_for_today_with_plan(test_db):
    """Test retrieving the carer's schedule for today with a journey plan."""
    # Create a journey plan for today
    plan = await journey_repository.create_journey_plan(
        operating_day="2024-01-01",
        creation_reason="initial_creation",
        plan_version=1,
    )

    # Create a journey linking the carer to the visit
    await journey_repository.create_journey(
        plan_id=plan["id"],
        carer_id=1,
        visit_id=1,
        origin_lat=51.5,
        origin_lng=-0.1,
        origin_label="Home",
        destination_lat=51.51,
        destination_lng=-0.09,
        destination_label="Patient 1",
        planned_departure="2024-01-01T08:45:00",
        planned_arrival="2024-01-01T09:00:00",
        planned_distance_miles=2.5,
    )

    schedule = await mobile_repository.get_carer_schedule_for_today(
        1, "2024-01-01"
    )
    assert len(schedule) == 1
    assert schedule[0]["visit_id"] == 1
    assert schedule[0]["patient_name"] == "Test Patient"
    assert schedule[0]["patient_address"] == "123 Test St"
    assert schedule[0]["window_start"] == "09:00"
    assert schedule[0]["window_end"] == "10:00"
    assert schedule[0]["duration_minutes"] == 30
    assert schedule[0]["required_skills"] == ["medication"]
    assert schedule[0]["status"] == "pending"
    assert schedule[0]["confidence_score"] == 0
