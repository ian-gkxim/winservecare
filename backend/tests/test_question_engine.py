"""Tests for the Question Engine service and mobile questions endpoints."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db import mobile_repository
from backend.app.services.question_engine import (
    CONFIDENCE_THRESHOLD,
    RATE_LIMIT_MINUTES,
    create_contextual_question,
    generate_question_text,
    get_question_for_confidence,
    should_ask_question,
    should_send_question,
    trigger_question,
    trigger_question_for_low_confidence,
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

        # Insert test data for FK constraints
        async with database.get_db() as db:
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills,
                   max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (1, 'Test Carer', 51.5, -0.1, '["medication"]',
                   8.0, 6.0, 30)"""
            )
            await db.execute(
                """INSERT INTO carers (id, name, home_lat, home_lng, skills,
                   max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (2, 'Other Carer', 51.6, -0.2, '["medication"]',
                   8.0, 6.0, 30)"""
            )
            await db.execute(
                """INSERT INTO patients (id, name, address, lat, lng,
                   preferences, priority)
                   VALUES (1, 'Mrs Smith', '123 Test St', 51.51, -0.09,
                   '[]', 'medium')"""
            )
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes,
                   window_start, window_end, required_skills)
                   VALUES (1, 1, 30, '09:00', '10:00', '["medication"]')"""
            )
            await db.execute(
                """INSERT INTO visits (id, patient_id, duration_minutes,
                   window_start, window_end, required_skills)
                   VALUES (2, 1, 45, '11:00', '12:00', '["medication"]')"""
            )
            await db.commit()

        yield


# --- generate_question_text tests ---


class TestGenerateQuestionText:
    """Tests for question text generation based on visit context."""

    def test_pending_status_with_name(self):
        text = generate_question_text("pending", "Mrs Smith")
        assert "Mrs Smith" in text
        assert "arrived" in text.lower()

    def test_travelling_status(self):
        text = generate_question_text("travelling", "Mr Jones")
        assert "Mr Jones" in text
        assert "arrived" in text.lower()

    def test_arrived_status(self):
        text = generate_question_text("arrived", "Mrs Smith")
        assert "Mrs Smith" in text
        assert "started" in text.lower()

    def test_in_progress_status(self):
        text = generate_question_text("in_progress", "Mrs Smith")
        assert "Mrs Smith" in text
        assert "complete" in text.lower()

    def test_delayed_status(self):
        text = generate_question_text("delayed", "Mrs Smith")
        assert "Mrs Smith" in text
        assert "way" in text.lower()

    def test_none_status_defaults_to_arrival_question(self):
        text = generate_question_text(None, "Mrs Smith")
        assert "Mrs Smith" in text
        assert "arrived" in text.lower()

    def test_no_patient_name_uses_default(self):
        text = generate_question_text("pending")
        assert "the patient" in text

    def test_unknown_status_gives_generic_question(self):
        text = generate_question_text("completed", "Mrs Smith")
        assert "Mrs Smith" in text
        assert "confirm" in text.lower()

    def test_conflict_status_asks_location_confirmation(self):
        """For conflicting signals, should ask location confirmation."""
        text = generate_question_text("conflict", "Mrs Smith")
        assert "Mrs Smith" in text
        assert "confirm" in text.lower()
        assert "address" in text.lower()

    def test_no_signal_asks_if_still_on_shift(self):
        """For no-signal timeout, should ask if still on shift."""
        text = generate_question_text("no_signal", "Mrs Smith")
        assert "still on your shift" in text.lower()


# --- should_send_question tests ---


class TestShouldSendQuestion:
    """Tests for rate-limit checking."""

    @pytest.mark.asyncio
    async def test_allows_question_when_no_recent(self, test_db):
        """Should allow question if no questions sent in last 10 mins."""
        result = await should_send_question(visit_id=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_blocks_question_when_recent_exists(self, test_db):
        """Should block question if one was sent in last 10 minutes."""
        await mobile_repository.create_question(
            carer_id=1,
            visit_id=1,
            question_text="Test question?",
            question_type="yes_no",
        )
        result = await should_send_question(visit_id=1)
        assert result is False


# --- trigger_question tests ---


class TestTriggerQuestion:
    """Tests for the main trigger_question function."""

    @pytest.mark.asyncio
    async def test_creates_question_when_allowed(self, test_db):
        """Should create a question when rate limit allows."""
        question = await trigger_question(
            carer_id=1,
            visit_id=1,
            confidence_score=40,
            patient_name="Mrs Smith",
            visit_status="pending",
        )
        assert question is not None
        assert question["carer_id"] == 1
        assert question["visit_id"] == 1
        assert question["question_type"] == "yes_no"
        assert "Mrs Smith" in question["question_text"]
        assert question["status"] == "sent"

    @pytest.mark.asyncio
    async def test_returns_none_when_rate_limited(self, test_db):
        """Should return None when a question was recently sent."""
        # Send first question
        await trigger_question(
            carer_id=1,
            visit_id=1,
            confidence_score=40,
            patient_name="Mrs Smith",
        )
        # Try to send another - should be rate-limited
        result = await trigger_question(
            carer_id=1,
            visit_id=1,
            confidence_score=30,
            patient_name="Mrs Smith",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_allows_question_for_different_visit(self, test_db):
        """Rate limit is per-visit, so different visit should be allowed."""
        # Send question for visit 1
        q1 = await trigger_question(
            carer_id=1,
            visit_id=1,
            confidence_score=40,
            patient_name="Mrs Smith",
        )
        assert q1 is not None

        # Send question for visit 2 - should work
        q2 = await trigger_question(
            carer_id=1,
            visit_id=2,
            confidence_score=40,
            patient_name="Mrs Smith",
        )
        assert q2 is not None

    @pytest.mark.asyncio
    async def test_looks_up_visit_status_if_not_provided(self, test_db):
        """Should use visit status from DB if not explicitly provided."""
        # Set a visit status
        await mobile_repository.set_visit_status(
            visit_id=1,
            carer_id=1,
            status="arrived",
            confidence_score=55,
            inferred_by="gps",
        )

        question = await trigger_question(
            carer_id=1,
            visit_id=1,
            confidence_score=55,
            patient_name="Mrs Smith",
            visit_status=None,
        )
        assert question is not None
        # Should generate "arrived" context question
        assert "started" in question["question_text"].lower()


# --- trigger_question_for_low_confidence tests ---


class TestTriggerQuestionForLowConfidence:
    """Tests for the confidence-threshold-based trigger."""

    @pytest.mark.asyncio
    async def test_triggers_when_below_threshold(self, test_db):
        """Should trigger question when confidence < 60."""
        question = await trigger_question_for_low_confidence(
            carer_id=1,
            visit_id=1,
            confidence_score=59,
            patient_name="Mrs Smith",
        )
        assert question is not None

    @pytest.mark.asyncio
    async def test_does_not_trigger_at_threshold(self, test_db):
        """Should NOT trigger when confidence == 60 (at threshold)."""
        question = await trigger_question_for_low_confidence(
            carer_id=1,
            visit_id=1,
            confidence_score=60,
            patient_name="Mrs Smith",
        )
        assert question is None

    @pytest.mark.asyncio
    async def test_does_not_trigger_above_threshold(self, test_db):
        """Should NOT trigger when confidence > 60."""
        question = await trigger_question_for_low_confidence(
            carer_id=1,
            visit_id=1,
            confidence_score=85,
            patient_name="Mrs Smith",
        )
        assert question is None

    @pytest.mark.asyncio
    async def test_rate_limited_even_at_low_confidence(self, test_db):
        """Rate limit still applies even when confidence is very low."""
        q1 = await trigger_question_for_low_confidence(
            carer_id=1,
            visit_id=1,
            confidence_score=20,
            patient_name="Mrs Smith",
        )
        assert q1 is not None

        q2 = await trigger_question_for_low_confidence(
            carer_id=1,
            visit_id=1,
            confidence_score=10,
            patient_name="Mrs Smith",
        )
        assert q2 is None


# --- API endpoint tests ---


class TestPendingQuestionsEndpoint:
    """Tests for GET /api/mobile/questions/pending."""

    @pytest.mark.asyncio
    async def test_returns_pending_questions(self, test_db):
        """Should return all sent questions for the carer."""
        # Create some questions
        await mobile_repository.create_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        await mobile_repository.create_question(
            carer_id=1,
            visit_id=2,
            question_text="Is your visit complete?",
            question_type="yes_no",
        )

        questions = await mobile_repository.get_pending_questions_for_carer(1)
        assert len(questions) == 2
        assert questions[0]["question_text"] == "Have you arrived?"
        assert questions[1]["question_text"] == "Is your visit complete?"

    @pytest.mark.asyncio
    async def test_excludes_answered_questions(self, test_db):
        """Should not return questions that have already been answered."""
        q = await mobile_repository.create_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        # Answer it
        await mobile_repository.update_question_response(
            q["id"], "yes", datetime.now(timezone.utc).isoformat()
        )

        questions = await mobile_repository.get_pending_questions_for_carer(1)
        assert len(questions) == 0

    @pytest.mark.asyncio
    async def test_excludes_timed_out_questions(self, test_db):
        """Should not return questions that have timed out."""
        q = await mobile_repository.create_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        # Time it out
        await mobile_repository.update_question_timeout(
            q["id"], datetime.now(timezone.utc).isoformat()
        )

        questions = await mobile_repository.get_pending_questions_for_carer(1)
        assert len(questions) == 0

    @pytest.mark.asyncio
    async def test_does_not_return_other_carers_questions(self, test_db):
        """Should only return questions for the specific carer."""
        await mobile_repository.create_question(
            carer_id=2,
            visit_id=1,
            question_text="Other carer question",
            question_type="yes_no",
        )

        questions = await mobile_repository.get_pending_questions_for_carer(1)
        assert len(questions) == 0


class TestTimeoutEndpoint:
    """Tests for POST /api/mobile/questions/{id}/timeout."""

    @pytest.mark.asyncio
    async def test_marks_question_as_timed_out(self, test_db):
        """Should mark a sent question as timed_out."""
        q = await mobile_repository.create_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        timed_out_at = datetime.now(timezone.utc).isoformat()
        updated = await mobile_repository.update_question_timeout(
            q["id"], timed_out_at
        )
        assert updated is not None
        assert updated["status"] == "timed_out"
        assert updated["timed_out_at"] == timed_out_at

    @pytest.mark.asyncio
    async def test_timeout_nonexistent_question(self, test_db):
        """Should return None for non-existent question."""
        result = await mobile_repository.update_question_timeout(
            999, datetime.now(timezone.utc).isoformat()
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_already_answered_question(self, test_db):
        """Answered questions can still be timed out at DB level (route validates)."""
        q = await mobile_repository.create_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        # Answer it first
        await mobile_repository.update_question_response(
            q["id"], "yes", datetime.now(timezone.utc).isoformat()
        )
        # The route would reject this, but at the DB level it still works
        # (the route guards status == 'sent')
        result = await mobile_repository.update_question_timeout(
            q["id"], datetime.now(timezone.utc).isoformat()
        )
        # DB layer doesn't check status, but the update still happens
        assert result is not None



# --- should_ask_question tests ---


class TestShouldAskQuestion:
    """Tests for should_ask_question which combines confidence and rate-limit checks."""

    @pytest.mark.asyncio
    async def test_returns_false_when_confidence_at_threshold(self, test_db):
        """Should return False when confidence >= 60."""
        result = await should_ask_question(carer_id=1, visit_id=1, confidence_score=60)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_confidence_above_threshold(self, test_db):
        """Should return False when confidence > 60."""
        result = await should_ask_question(carer_id=1, visit_id=1, confidence_score=85)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_below_threshold_and_no_recent(self, test_db):
        """Should return True when confidence < 60 and no recent questions."""
        result = await should_ask_question(carer_id=1, visit_id=1, confidence_score=40)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_below_threshold_but_rate_limited(self, test_db):
        """Should return False when confidence < 60 but question was sent recently."""
        await mobile_repository.create_question(
            carer_id=1,
            visit_id=1,
            question_text="Recent question",
            question_type="yes_no",
        )
        result = await should_ask_question(carer_id=1, visit_id=1, confidence_score=30)
        assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_is_per_visit(self, test_db):
        """Rate limit applies per visit, not globally."""
        await mobile_repository.create_question(
            carer_id=1,
            visit_id=1,
            question_text="Question for visit 1",
            question_type="yes_no",
        )
        # Visit 2 should still be allowed
        result = await should_ask_question(carer_id=1, visit_id=2, confidence_score=30)
        assert result is True


# --- get_question_for_confidence tests ---


class TestGetQuestionForConfidence:
    """Tests for get_question_for_confidence which generates context-based text."""

    def test_conflict_status_generates_location_question(self):
        """For conflict status, should ask about location confirmation."""
        text = get_question_for_confidence("conflict", "Mrs Smith")
        assert "confirm" in text.lower()
        assert "address" in text.lower()
        assert "Mrs Smith" in text

    def test_pending_status_asks_about_arrival(self):
        """For pending status, should ask about arrival."""
        text = get_question_for_confidence("pending", "Mrs Smith")
        assert "arrived" in text.lower()
        assert "Mrs Smith" in text

    def test_in_progress_asks_about_completion(self):
        """For in_progress, should ask if visit is complete."""
        text = get_question_for_confidence("in_progress", "Mrs Smith")
        assert "complete" in text.lower()

    def test_none_patient_name_uses_default(self):
        """Should use 'the patient' if no name provided."""
        text = get_question_for_confidence("pending")
        assert "the patient" in text

    def test_no_signal_asks_about_shift(self):
        """For no-signal timeout, should ask about shift status."""
        text = get_question_for_confidence("no_signal", "Mrs Smith")
        assert "still on your shift" in text.lower()


# --- create_contextual_question tests ---


class TestCreateContextualQuestion:
    """Tests for create_contextual_question which creates question + notification."""

    @pytest.mark.asyncio
    async def test_creates_question_record(self, test_db):
        """Should create a question record in the database."""
        question = await create_contextual_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        assert question is not None
        assert question["carer_id"] == 1
        assert question["visit_id"] == 1
        assert question["question_text"] == "Have you arrived?"
        assert question["question_type"] == "yes_no"
        assert question["status"] == "sent"

    @pytest.mark.asyncio
    async def test_creates_push_notification(self, test_db):
        """Should also create a push notification for the question."""
        question = await create_contextual_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        # Verify the notification was created
        notifications = await mobile_repository.get_recent_notifications_for_carer(1)
        assert len(notifications) == 1
        assert notifications[0]["notification_type"] == "contextual_question"
        assert notifications[0]["carer_id"] == 1

    @pytest.mark.asyncio
    async def test_creates_question_with_options(self, test_db):
        """Should support single_choice with options."""
        options = ["Yes", "No", "Not sure"]
        question = await create_contextual_question(
            carer_id=1,
            visit_id=1,
            question_text="How is the visit going?",
            question_type="single_choice",
            options=options,
        )
        assert question is not None
        assert question["question_type"] == "single_choice"

    @pytest.mark.asyncio
    async def test_notification_payload_contains_question_details(self, test_db):
        """Notification payload should include question ID, text, type."""
        import json

        question = await create_contextual_question(
            carer_id=1,
            visit_id=1,
            question_text="Have you arrived?",
            question_type="yes_no",
        )
        notifications = await mobile_repository.get_recent_notifications_for_carer(1)
        payload = json.loads(notifications[0]["payload"])
        assert payload["question_id"] == question["id"]
        assert payload["question_text"] == "Have you arrived?"
        assert payload["question_type"] == "yes_no"
        assert payload["visit_id"] == 1
