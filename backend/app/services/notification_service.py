"""Notification Service for the Carer Mobile App.

Wraps FCM/APNs delivery behind an interface with:
- Retry logic: 3 attempts, 30s intervals, mark undelivered after exhaustion
- Rate limit: max 10 notifications/hour/carer (sliding window)
- Delivery status tracking in push_notifications table

Requirements: 9.1, 9.2, 9.4, 9.6
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from backend.app.db import mobile_repository

logger = logging.getLogger(__name__)

# Configuration
MAX_RETRIES = 3
RETRY_INTERVAL_SECONDS = 30
MAX_NOTIFICATIONS_PER_HOUR = 10
RATE_LIMIT_WINDOW_MINUTES = 60


class PushDeliveryResult:
    """Result of a push delivery attempt."""

    def __init__(self, success: bool, error: str | None = None):
        self.success = success
        self.error = error


class PushDeliveryProvider(ABC):
    """Abstract interface for push notification delivery (FCM/APNs)."""

    @abstractmethod
    async def deliver(
        self, device_token: str, platform: str, payload: dict
    ) -> PushDeliveryResult:
        """Deliver a push notification to a device.

        Args:
            device_token: The FCM/APNs device token.
            platform: 'ios' or 'android'.
            payload: The notification payload.

        Returns:
            PushDeliveryResult indicating success or failure.
        """
        ...


class StubPushDeliveryProvider(PushDeliveryProvider):
    """Stub provider for development/testing — always succeeds."""

    async def deliver(
        self, device_token: str, platform: str, payload: dict
    ) -> PushDeliveryResult:
        """Simulate successful push delivery."""
        logger.info(
            "Stub push delivery to %s (%s): %s",
            device_token,
            platform,
            json.dumps(payload)[:200],
        )
        return PushDeliveryResult(success=True)


class NotificationService:
    """Service for sending push notifications to carers.

    Handles rate limiting, retry logic, and delivery status tracking.
    """

    def __init__(self, provider: PushDeliveryProvider | None = None):
        """Initialise the notification service.

        Args:
            provider: Push delivery provider. Defaults to StubPushDeliveryProvider.
        """
        self.provider = provider or StubPushDeliveryProvider()

    async def send_notification(
        self,
        carer_id: int,
        notification_type: str,
        payload: dict,
    ) -> dict | None:
        """Send a push notification to a carer.

        Checks rate limit, creates a record, attempts delivery with retries.

        Args:
            carer_id: The carer's identifier.
            notification_type: One of 'schedule_change', 'contextual_question', 'general'.
            payload: The notification payload dict.

        Returns:
            The notification record dict, or None if rate limited.
        """
        # Check rate limit
        if await self._is_rate_limited(carer_id):
            logger.warning(
                "Rate limit exceeded for carer %d (%d notifications/hour). "
                "Notification skipped.",
                carer_id,
                MAX_NOTIFICATIONS_PER_HOUR,
            )
            return None

        # Create notification record in pending state
        notification = await mobile_repository.create_notification(
            carer_id=carer_id,
            notification_type=notification_type,
            payload=payload,
        )

        # Attempt delivery with retries
        await self._deliver_with_retries(carer_id, notification)

        return notification

    async def send_schedule_change_notification(
        self,
        carer_id: int,
        change_description: str,
    ) -> dict | None:
        """Send a schedule change notification to a carer.

        Convenience method for schedule_change notification type.

        Args:
            carer_id: The carer's identifier.
            change_description: Human-readable description of the change.

        Returns:
            The notification record dict, or None if rate limited.
        """
        payload = {
            "type": "schedule_change",
            "message": change_description,
        }
        return await self.send_notification(
            carer_id=carer_id,
            notification_type="schedule_change",
            payload=payload,
        )

    async def send_question_notification(
        self,
        carer_id: int,
        question_payload: dict,
    ) -> dict | None:
        """Send a contextual question notification to a carer.

        Convenience method for contextual_question notification type.

        Args:
            carer_id: The carer's identifier.
            question_payload: The question payload (id, text, type, options, visit_id).

        Returns:
            The notification record dict, or None if rate limited.
        """
        payload = {
            "type": "contextual_question",
            **question_payload,
        }
        return await self.send_notification(
            carer_id=carer_id,
            notification_type="contextual_question",
            payload=payload,
        )

    async def _is_rate_limited(self, carer_id: int) -> bool:
        """Check if the carer has exceeded the notification rate limit.

        Args:
            carer_id: The carer's identifier.

        Returns:
            True if rate limit exceeded (>= 10 notifications in last 60 min).
        """
        count = await mobile_repository.count_notifications_in_window(
            carer_id, window_minutes=RATE_LIMIT_WINDOW_MINUTES
        )
        return count >= MAX_NOTIFICATIONS_PER_HOUR

    async def _deliver_with_retries(
        self, carer_id: int, notification: dict
    ) -> None:
        """Attempt push delivery with retry logic.

        Tries up to 3 times with 30s intervals. Marks as undelivered after
        all attempts fail.

        Args:
            carer_id: The carer's identifier.
            notification: The notification record from the database.
        """
        # Get device token for the carer
        auth = await mobile_repository.get_auth_by_carer_id(carer_id)
        if not auth or not auth.get("device_token"):
            logger.warning(
                "No device token for carer %d. Marking notification %d as undelivered.",
                carer_id,
                notification["id"],
            )
            await mobile_repository.update_notification_status(
                notification["id"], status="undelivered"
            )
            return

        device_token = auth["device_token"]
        platform = auth.get("device_platform", "android")
        payload = (
            json.loads(notification["payload"])
            if isinstance(notification["payload"], str)
            else notification["payload"]
        )

        for attempt in range(MAX_RETRIES):
            sent_at = datetime.now(timezone.utc).isoformat()
            result = await self.provider.deliver(device_token, platform, payload)

            if result.success:
                delivered_at = datetime.now(timezone.utc).isoformat()
                await mobile_repository.update_notification_status(
                    notification["id"],
                    status="delivered",
                    sent_at=sent_at,
                    delivered_at=delivered_at,
                )
                logger.info(
                    "Notification %d delivered to carer %d on attempt %d.",
                    notification["id"],
                    carer_id,
                    attempt + 1,
                )
                return

            # Delivery failed — increment retry count
            await mobile_repository.update_notification_status(
                notification["id"],
                status="failed",
                sent_at=sent_at,
                increment_retry=True,
            )
            logger.warning(
                "Notification %d delivery failed for carer %d (attempt %d/%d): %s",
                notification["id"],
                carer_id,
                attempt + 1,
                MAX_RETRIES,
                result.error or "unknown error",
            )

            # Wait before retry (except after last attempt)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_INTERVAL_SECONDS)

        # All retries exhausted — mark as undelivered
        await mobile_repository.update_notification_status(
            notification["id"], status="undelivered"
        )
        logger.error(
            "Notification %d marked as undelivered for carer %d after %d attempts.",
            notification["id"],
            carer_id,
            MAX_RETRIES,
        )
