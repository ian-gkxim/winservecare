"""Tests for the Notification Service.

Tests cover:
- Rate limiting (max 10 notifications/hour/carer)
- Retry logic (3 attempts, 30s intervals, mark undelivered)
- Delivery status tracking in push_notifications table
- Convenience methods for schedule changes and questions
- Edge cases: no device token, provider failures
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db import mobile_repository
from backend.app.services.notification_service import (
    MAX_NOTIFICATIONS_PER_HOUR,
    MAX_RETRIES,
    NotificationService,
    PushDeliveryProvider,
    PushDeliveryResult,
    StubPushDeliveryProvider,
)


# --- Test fixtures ---


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and seed data."""
    db_path = tmp_path / "test.db"
    schema_path = (
        Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    )
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), patch.object(
        database, "DB_DIR", tmp_path
    ):
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
            # Create auth record with device token
            await db.execute(
                """INSERT INTO carer_auth (carer_id, password_hash, device_token, device_platform)
                   VALUES (1, 'hashed_pw', 'fcm_test_token_abc', 'android')"""
            )
            await db.commit()

        yield


class FailingProvider(PushDeliveryProvider):
    """Provider that always fails delivery."""

    async def deliver(
        self, device_token: str, platform: str, payload: dict
    ) -> PushDeliveryResult:
        return PushDeliveryResult(success=False, error="Connection refused")


class CountingProvider(PushDeliveryProvider):
    """Provider that tracks delivery attempts and can be configured to fail N times."""

    def __init__(self, fail_count: int = 0):
        self.attempts = 0
        self.fail_count = fail_count

    async def deliver(
        self, device_token: str, platform: str, payload: dict
    ) -> PushDeliveryResult:
        self.attempts += 1
        if self.attempts <= self.fail_count:
            return PushDeliveryResult(
                success=False, error=f"Failure #{self.attempts}"
            )
        return PushDeliveryResult(success=True)


# --- Tests ---


@pytest.mark.asyncio
async def test_send_notification_success(test_db):
    """Test that a notification is delivered and marked as delivered."""
    provider = StubPushDeliveryProvider()
    service = NotificationService(provider=provider)

    result = await service.send_notification(
        carer_id=1,
        notification_type="general",
        payload={"message": "Hello"},
    )

    assert result is not None
    assert result["carer_id"] == 1
    assert result["notification_type"] == "general"

    # Verify the notification was marked as delivered in the DB
    notifications = await mobile_repository.get_recent_notifications_for_carer(1)
    assert len(notifications) == 1
    assert notifications[0]["status"] == "delivered"
    assert notifications[0]["sent_at"] is not None
    assert notifications[0]["delivered_at"] is not None


@pytest.mark.asyncio
async def test_send_notification_no_device_token(test_db):
    """Test that notification is marked undelivered when no device token exists."""
    # Create a carer without device token
    async with database.get_db() as db:
        await db.execute(
            """INSERT INTO carers (id, name, home_lat, home_lng, skills,
               max_working_hours, max_continuous_hours, min_break_minutes)
               VALUES (2, 'No Token Carer', 51.5, -0.1, '["medication"]',
               8.0, 6.0, 30)"""
        )
        await db.execute(
            """INSERT INTO carer_auth (carer_id, password_hash)
               VALUES (2, 'hashed_pw')"""
        )
        await db.commit()

    service = NotificationService(provider=StubPushDeliveryProvider())
    result = await service.send_notification(
        carer_id=2,
        notification_type="general",
        payload={"message": "Hello"},
    )

    assert result is not None
    notifications = await mobile_repository.get_recent_notifications_for_carer(2)
    assert len(notifications) == 1
    assert notifications[0]["status"] == "undelivered"


@pytest.mark.asyncio
async def test_retry_logic_all_failures(test_db):
    """Test that after 3 failed attempts, notification is marked undelivered."""
    provider = FailingProvider()
    service = NotificationService(provider=provider)

    # Patch asyncio.sleep to avoid real delays
    with patch("backend.app.services.notification_service.asyncio.sleep", new_callable=AsyncMock):
        result = await service.send_notification(
            carer_id=1,
            notification_type="general",
            payload={"message": "Will fail"},
        )

    assert result is not None
    notifications = await mobile_repository.get_recent_notifications_for_carer(1)
    assert len(notifications) == 1
    assert notifications[0]["status"] == "undelivered"
    assert notifications[0]["retry_count"] == MAX_RETRIES


@pytest.mark.asyncio
async def test_retry_logic_succeeds_on_second_attempt(test_db):
    """Test that delivery succeeds on the second attempt after one failure."""
    provider = CountingProvider(fail_count=1)
    service = NotificationService(provider=provider)

    with patch("backend.app.services.notification_service.asyncio.sleep", new_callable=AsyncMock):
        result = await service.send_notification(
            carer_id=1,
            notification_type="general",
            payload={"message": "Retry me"},
        )

    assert result is not None
    assert provider.attempts == 2

    notifications = await mobile_repository.get_recent_notifications_for_carer(1)
    assert len(notifications) == 1
    assert notifications[0]["status"] == "delivered"
    # retry_count should be 1 (one failed attempt before success)
    assert notifications[0]["retry_count"] == 1


@pytest.mark.asyncio
async def test_retry_logic_succeeds_on_third_attempt(test_db):
    """Test that delivery succeeds on the third attempt after two failures."""
    provider = CountingProvider(fail_count=2)
    service = NotificationService(provider=provider)

    with patch("backend.app.services.notification_service.asyncio.sleep", new_callable=AsyncMock):
        result = await service.send_notification(
            carer_id=1,
            notification_type="general",
            payload={"message": "Retry again"},
        )

    assert result is not None
    assert provider.attempts == 3

    notifications = await mobile_repository.get_recent_notifications_for_carer(1)
    assert len(notifications) == 1
    assert notifications[0]["status"] == "delivered"
    assert notifications[0]["retry_count"] == 2


@pytest.mark.asyncio
async def test_rate_limit_blocks_at_threshold(test_db):
    """Test that the 11th notification is rate limited (10/hour max)."""
    service = NotificationService(provider=StubPushDeliveryProvider())

    # Send 10 notifications (should all succeed)
    for i in range(MAX_NOTIFICATIONS_PER_HOUR):
        result = await service.send_notification(
            carer_id=1,
            notification_type="general",
            payload={"message": f"Notification {i+1}"},
        )
        assert result is not None

    # 11th notification should be rate limited
    result = await service.send_notification(
        carer_id=1,
        notification_type="general",
        payload={"message": "This should be blocked"},
    )
    assert result is None

    # Verify only 10 notifications exist in DB
    notifications = await mobile_repository.get_recent_notifications_for_carer(1, limit=20)
    assert len(notifications) == MAX_NOTIFICATIONS_PER_HOUR


@pytest.mark.asyncio
async def test_rate_limit_per_carer(test_db):
    """Test that rate limit is per-carer (different carers have separate limits)."""
    # Create second carer
    async with database.get_db() as db:
        await db.execute(
            """INSERT INTO carers (id, name, home_lat, home_lng, skills,
               max_working_hours, max_continuous_hours, min_break_minutes)
               VALUES (2, 'Carer Two', 51.5, -0.1, '["medication"]',
               8.0, 6.0, 30)"""
        )
        await db.execute(
            """INSERT INTO carer_auth (carer_id, password_hash, device_token, device_platform)
               VALUES (2, 'hashed_pw', 'token_carer_2', 'ios')"""
        )
        await db.commit()

    service = NotificationService(provider=StubPushDeliveryProvider())

    # Fill up carer 1's rate limit
    for i in range(MAX_NOTIFICATIONS_PER_HOUR):
        await service.send_notification(
            carer_id=1,
            notification_type="general",
            payload={"message": f"C1 notif {i}"},
        )

    # Carer 2 should still be able to send
    result = await service.send_notification(
        carer_id=2,
        notification_type="general",
        payload={"message": "Carer 2 notification"},
    )
    assert result is not None


@pytest.mark.asyncio
async def test_send_schedule_change_notification(test_db):
    """Test the convenience method for schedule change notifications."""
    service = NotificationService(provider=StubPushDeliveryProvider())

    result = await service.send_schedule_change_notification(
        carer_id=1,
        change_description="Visit at 10:00 has been rescheduled to 11:00",
    )

    assert result is not None
    assert result["notification_type"] == "schedule_change"

    notifications = await mobile_repository.get_recent_notifications_for_carer(1)
    assert len(notifications) == 1
    assert notifications[0]["status"] == "delivered"


@pytest.mark.asyncio
async def test_send_question_notification(test_db):
    """Test the convenience method for question notifications."""
    service = NotificationService(provider=StubPushDeliveryProvider())

    question_payload = {
        "question_id": 42,
        "visit_id": 1,
        "question_text": "Have you arrived at the patient?",
        "question_type": "yes_no",
    }
    result = await service.send_question_notification(
        carer_id=1,
        question_payload=question_payload,
    )

    assert result is not None
    assert result["notification_type"] == "contextual_question"

    notifications = await mobile_repository.get_recent_notifications_for_carer(1)
    assert len(notifications) == 1
    assert notifications[0]["status"] == "delivered"


@pytest.mark.asyncio
async def test_retry_calls_sleep_with_correct_interval(test_db):
    """Test that retry logic waits 30 seconds between attempts."""
    provider = FailingProvider()
    service = NotificationService(provider=provider)

    mock_sleep = AsyncMock()
    with patch("backend.app.services.notification_service.asyncio.sleep", mock_sleep):
        await service.send_notification(
            carer_id=1,
            notification_type="general",
            payload={"message": "Testing sleep"},
        )

    # Should sleep between retries (not after the last one)
    assert mock_sleep.call_count == MAX_RETRIES - 1
    for call in mock_sleep.call_args_list:
        assert call[0][0] == 30  # 30 second intervals


@pytest.mark.asyncio
async def test_no_auth_record_marks_undelivered(test_db):
    """Test notification marked undelivered when carer has no auth record."""
    # Create carer without any auth record
    async with database.get_db() as db:
        await db.execute(
            """INSERT INTO carers (id, name, home_lat, home_lng, skills,
               max_working_hours, max_continuous_hours, min_break_minutes)
               VALUES (3, 'No Auth Carer', 51.5, -0.1, '["medication"]',
               8.0, 6.0, 30)"""
        )
        await db.commit()

    service = NotificationService(provider=StubPushDeliveryProvider())
    result = await service.send_notification(
        carer_id=3,
        notification_type="general",
        payload={"message": "No auth"},
    )

    assert result is not None
    notifications = await mobile_repository.get_recent_notifications_for_carer(3)
    assert len(notifications) == 1
    assert notifications[0]["status"] == "undelivered"
