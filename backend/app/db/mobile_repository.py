"""Data access layer for Carer Mobile App entities.

Provides async CRUD operations for: carer_auth, gps_signals,
contextual_questions, proactive_inputs, visit_status,
visit_status_transitions, and push_notifications.
"""

import json
from datetime import datetime

from backend.app.db.database import get_db


# --- Carer Auth operations ---


async def get_auth_by_carer_id(carer_id: int) -> dict | None:
    """Retrieve authentication record for a carer.

    Args:
        carer_id: The carer's identifier.

    Returns:
        The auth row as a dict, or None if not found.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM carer_auth WHERE carer_id = ?", (carer_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def create_auth(
    carer_id: int,
    password_hash: str,
    device_token: str | None = None,
    device_platform: str | None = None,
) -> dict:
    """Create a new carer authentication record.

    Args:
        carer_id: The carer's identifier.
        password_hash: The bcrypt-hashed password.
        device_token: Optional FCM/APNs device token.
        device_platform: Optional platform ('ios' or 'android').

    Returns:
        The newly created auth row as a dict.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO carer_auth (carer_id, password_hash, device_token, device_platform)
               VALUES (?, ?, ?, ?)""",
            (carer_id, password_hash, device_token, device_platform),
        )
        await db.commit()

        new_cursor = await db.execute(
            "SELECT * FROM carer_auth WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def update_refresh_token(
    carer_id: int, refresh_token: str, expires_at: str
) -> None:
    """Update the refresh token for a carer.

    Args:
        carer_id: The carer's identifier.
        refresh_token: The new refresh token.
        expires_at: ISO 8601 expiry timestamp.
    """
    async with get_db() as db:
        await db.execute(
            """UPDATE carer_auth
               SET refresh_token = ?, refresh_token_expires_at = ?,
                   updated_at = ?
               WHERE carer_id = ?""",
            (refresh_token, expires_at, datetime.now().isoformat(), carer_id),
        )
        await db.commit()


async def update_device_token(
    carer_id: int, device_token: str, device_platform: str
) -> None:
    """Update the push notification device token for a carer.

    Args:
        carer_id: The carer's identifier.
        device_token: The FCM/APNs device token.
        device_platform: 'ios' or 'android'.
    """
    async with get_db() as db:
        await db.execute(
            """UPDATE carer_auth
               SET device_token = ?, device_platform = ?, updated_at = ?
               WHERE carer_id = ?""",
            (device_token, device_platform, datetime.now().isoformat(), carer_id),
        )
        await db.commit()


async def increment_failed_logins(carer_id: int) -> int:
    """Increment the failed login attempt counter for a carer.

    Args:
        carer_id: The carer's identifier.

    Returns:
        The new failed_login_attempts count.
    """
    async with get_db() as db:
        await db.execute(
            """UPDATE carer_auth
               SET failed_login_attempts = failed_login_attempts + 1,
                   updated_at = ?
               WHERE carer_id = ?""",
            (datetime.now().isoformat(), carer_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT failed_login_attempts FROM carer_auth WHERE carer_id = ?",
            (carer_id,),
        )
        row = await cursor.fetchone()
        return row["failed_login_attempts"] if row else 0


async def reset_failed_logins(carer_id: int) -> None:
    """Reset the failed login counter to zero for a carer.

    Args:
        carer_id: The carer's identifier.
    """
    async with get_db() as db:
        await db.execute(
            """UPDATE carer_auth
               SET failed_login_attempts = 0, lockout_until = NULL,
                   updated_at = ?
               WHERE carer_id = ?""",
            (datetime.now().isoformat(), carer_id),
        )
        await db.commit()


async def set_lockout(carer_id: int, lockout_until: str) -> None:
    """Set a lockout timestamp for a carer after repeated failed logins.

    Args:
        carer_id: The carer's identifier.
        lockout_until: ISO 8601 timestamp when the lockout expires.
    """
    async with get_db() as db:
        await db.execute(
            """UPDATE carer_auth
               SET lockout_until = ?, updated_at = ?
               WHERE carer_id = ?""",
            (lockout_until, datetime.now().isoformat(), carer_id),
        )
        await db.commit()


# --- GPS Signals operations ---


async def create_gps_signal(
    carer_id: int,
    latitude: float,
    longitude: float,
    accuracy_metres: float,
    captured_at: str,
    low_accuracy: bool = False,
    visit_id: int | None = None,
    geofence_state: str | None = None,
) -> dict:
    """Create a single GPS signal record.

    Args:
        carer_id: The carer's identifier.
        latitude: GPS latitude.
        longitude: GPS longitude.
        accuracy_metres: GPS accuracy in metres.
        captured_at: UTC timestamp from the device.
        low_accuracy: True if accuracy > 50m.
        visit_id: Associated visit ID if within a geofence.
        geofence_state: 'inside', 'near', or 'outside'.

    Returns:
        The newly created GPS signal row as a dict.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO gps_signals
               (carer_id, latitude, longitude, accuracy_metres, low_accuracy,
                captured_at, visit_id, geofence_state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                carer_id,
                latitude,
                longitude,
                accuracy_metres,
                int(low_accuracy),
                captured_at,
                visit_id,
                geofence_state,
            ),
        )
        await db.commit()

        new_cursor = await db.execute(
            "SELECT * FROM gps_signals WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def create_gps_signals_batch(
    carer_id: int, signals: list[dict]
) -> list[dict]:
    """Create multiple GPS signal records in a single transaction.

    Args:
        carer_id: The carer's identifier.
        signals: List of dicts with keys: latitude, longitude, accuracy_metres,
                 captured_at, low_accuracy (optional), visit_id (optional),
                 geofence_state (optional).

    Returns:
        List of newly created GPS signal rows as dicts.
    """
    async with get_db() as db:
        created_ids = []
        for signal in signals:
            cursor = await db.execute(
                """INSERT INTO gps_signals
                   (carer_id, latitude, longitude, accuracy_metres, low_accuracy,
                    captured_at, visit_id, geofence_state)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    carer_id,
                    signal["latitude"],
                    signal["longitude"],
                    signal["accuracy_metres"],
                    int(signal.get("low_accuracy", False)),
                    signal["captured_at"],
                    signal.get("visit_id"),
                    signal.get("geofence_state"),
                ),
            )
            created_ids.append(cursor.lastrowid)
        await db.commit()

        # Fetch all created rows
        placeholders = ",".join("?" for _ in created_ids)
        cursor = await db.execute(
            f"SELECT * FROM gps_signals WHERE id IN ({placeholders}) ORDER BY id",
            created_ids,
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_recent_signals_for_carer(
    carer_id: int, limit: int = 50
) -> list[dict]:
    """Retrieve the most recent GPS signals for a carer.

    Args:
        carer_id: The carer's identifier.
        limit: Maximum number of signals to return (default 50).

    Returns:
        List of GPS signal rows as dicts, ordered by captured_at descending.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM gps_signals
               WHERE carer_id = ?
               ORDER BY captured_at DESC
               LIMIT ?""",
            (carer_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# --- Contextual Questions operations ---


async def create_question(
    carer_id: int,
    visit_id: int,
    question_text: str,
    question_type: str,
    options: list[str] | None = None,
) -> dict:
    """Create a contextual question record.

    Args:
        carer_id: The carer's identifier.
        visit_id: The associated visit identifier.
        question_text: The question text to display.
        question_type: One of 'yes_no', 'single_choice', 'free_text'.
        options: JSON-serialisable list of options for single_choice type.

    Returns:
        The newly created question row as a dict.
    """
    async with get_db() as db:
        options_json = json.dumps(options) if options else None
        cursor = await db.execute(
            """INSERT INTO contextual_questions
               (carer_id, visit_id, question_text, question_type, options)
               VALUES (?, ?, ?, ?, ?)""",
            (carer_id, visit_id, question_text, question_type, options_json),
        )
        await db.commit()

        new_cursor = await db.execute(
            "SELECT * FROM contextual_questions WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def get_pending_questions_for_carer(carer_id: int) -> list[dict]:
    """Retrieve all pending (sent) questions for a carer.

    Args:
        carer_id: The carer's identifier.

    Returns:
        List of question rows with status='sent', ordered by sent_at ascending.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM contextual_questions
               WHERE carer_id = ? AND status = 'sent'
               ORDER BY sent_at ASC""",
            (carer_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_question_response(
    question_id: int, response_text: str, responded_at: str
) -> dict | None:
    """Record a carer's response to a contextual question.

    Args:
        question_id: The question identifier.
        response_text: The carer's response.
        responded_at: UTC timestamp of the response.

    Returns:
        The updated question row as a dict, or None if not found.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM contextual_questions WHERE id = ?", (question_id,)
        )
        if not await cursor.fetchone():
            return None

        await db.execute(
            """UPDATE contextual_questions
               SET status = 'answered', response_text = ?, responded_at = ?
               WHERE id = ?""",
            (response_text, responded_at, question_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM contextual_questions WHERE id = ?", (question_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def update_question_timeout(
    question_id: int, timed_out_at: str
) -> dict | None:
    """Mark a contextual question as timed out.

    Args:
        question_id: The question identifier.
        timed_out_at: UTC timestamp when the question timed out.

    Returns:
        The updated question row as a dict, or None if not found.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM contextual_questions WHERE id = ?", (question_id,)
        )
        if not await cursor.fetchone():
            return None

        await db.execute(
            """UPDATE contextual_questions
               SET status = 'timed_out', timed_out_at = ?
               WHERE id = ?""",
            (timed_out_at, question_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM contextual_questions WHERE id = ?", (question_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def get_recent_questions_for_visit(
    visit_id: int, minutes: int = 10
) -> list[dict]:
    """Retrieve questions sent for a visit within the last N minutes.

    Used for rate-limiting: max 1 question per visit per 10 minutes.

    Args:
        visit_id: The visit identifier.
        minutes: Lookback window in minutes (default 10).

    Returns:
        List of question rows sent within the window.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM contextual_questions
               WHERE visit_id = ?
                 AND sent_at >= datetime('now', ?)
               ORDER BY sent_at DESC""",
            (visit_id, f"-{minutes} minutes"),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# --- Proactive Inputs operations ---


async def create_proactive_input(
    carer_id: int,
    visit_id: int,
    input_type: str,
    captured_at: str,
    note: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    location_unavailable: bool = False,
) -> dict:
    """Create a proactive input record.

    Args:
        carer_id: The carer's identifier.
        visit_id: The associated visit identifier.
        input_type: One of 'arrived', 'visit_started', 'visit_completed',
                    'running_late', 'issue_encountered', 'cannot_complete'.
        captured_at: UTC timestamp from the device.
        note: Optional free-text note (max 500 chars).
        latitude: GPS latitude, or None if unavailable.
        longitude: GPS longitude, or None if unavailable.
        location_unavailable: True if GPS was unavailable at capture time.

    Returns:
        The newly created proactive input row as a dict.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO proactive_inputs
               (carer_id, visit_id, input_type, note, latitude, longitude,
                location_unavailable, captured_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                carer_id,
                visit_id,
                input_type,
                note,
                latitude,
                longitude,
                int(location_unavailable),
                captured_at,
            ),
        )
        await db.commit()

        new_cursor = await db.execute(
            "SELECT * FROM proactive_inputs WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def get_inputs_for_visit(visit_id: int) -> list[dict]:
    """Retrieve all proactive inputs for a specific visit.

    Args:
        visit_id: The visit identifier.

    Returns:
        List of proactive input rows, ordered by captured_at ascending.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM proactive_inputs
               WHERE visit_id = ?
               ORDER BY captured_at ASC""",
            (visit_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# --- Visit Status operations ---


async def get_current_status_for_visit(visit_id: int) -> dict | None:
    """Retrieve the current (active) status for a visit.

    Args:
        visit_id: The visit identifier.

    Returns:
        The current visit status row as a dict, or None if no status exists.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM visit_status
               WHERE visit_id = ? AND is_current = 1""",
            (visit_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def get_current_statuses_for_carer(carer_id: int) -> list[dict]:
    """Retrieve all current visit statuses for a carer.

    Args:
        carer_id: The carer's identifier.

    Returns:
        List of current visit status rows for the carer.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM visit_status
               WHERE carer_id = ? AND is_current = 1
               ORDER BY created_at DESC""",
            (carer_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def set_visit_status(
    visit_id: int,
    carer_id: int,
    status: str,
    confidence_score: int,
    inferred_by: str,
) -> dict:
    """Set a new visit status, marking any previous current status as not current.

    This operation is atomic: it marks the previous status as non-current
    and inserts the new status as current within a single transaction.

    Args:
        visit_id: The visit identifier.
        carer_id: The carer's identifier.
        status: The new status value.
        confidence_score: Confidence score (0-100).
        inferred_by: Signal type that triggered the change
                     ('gps', 'question', 'proactive', 'timeout', 'system').

    Returns:
        The newly created visit status row as a dict.
    """
    async with get_db() as db:
        # Mark previous current status as not current
        await db.execute(
            """UPDATE visit_status
               SET is_current = 0
               WHERE visit_id = ? AND is_current = 1""",
            (visit_id,),
        )

        # Insert the new current status
        cursor = await db.execute(
            """INSERT INTO visit_status
               (visit_id, carer_id, status, confidence_score, inferred_by, is_current)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (visit_id, carer_id, status, confidence_score, inferred_by),
        )
        await db.commit()

        new_cursor = await db.execute(
            "SELECT * FROM visit_status WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


# --- Visit Status Transitions operations ---


async def create_transition(
    visit_id: int,
    previous_status: str,
    new_status: str,
    trigger_signal_type: str,
    confidence_score: int,
    trigger_signal_id: int | None = None,
) -> dict:
    """Create a visit status transition audit record.

    Args:
        visit_id: The visit identifier.
        previous_status: The status before the transition.
        new_status: The status after the transition.
        trigger_signal_type: Signal type that caused the transition
                            ('gps', 'question', 'proactive', 'timeout', 'system').
        confidence_score: Confidence score at the time of transition.
        trigger_signal_id: Optional ID of the triggering signal in its table.

    Returns:
        The newly created transition row as a dict.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO visit_status_transitions
               (visit_id, previous_status, new_status, trigger_signal_type,
                confidence_score, trigger_signal_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                visit_id,
                previous_status,
                new_status,
                trigger_signal_type,
                confidence_score,
                trigger_signal_id,
            ),
        )
        await db.commit()

        new_cursor = await db.execute(
            "SELECT * FROM visit_status_transitions WHERE id = ?",
            (cursor.lastrowid,),
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def get_transitions_for_visit(visit_id: int) -> list[dict]:
    """Retrieve all status transitions for a visit (audit trail).

    Args:
        visit_id: The visit identifier.

    Returns:
        List of transition rows, ordered by created_at ascending.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM visit_status_transitions
               WHERE visit_id = ?
               ORDER BY created_at ASC""",
            (visit_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# --- Push Notifications operations ---


async def create_notification(
    carer_id: int,
    notification_type: str,
    payload: dict | str,
) -> dict:
    """Create a push notification record.

    Args:
        carer_id: The carer's identifier.
        notification_type: One of 'schedule_change', 'contextual_question',
                          'general'.
        payload: Notification payload (dict will be JSON-serialised).

    Returns:
        The newly created notification row as a dict.
    """
    payload_json = json.dumps(payload) if isinstance(payload, dict) else payload
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO push_notifications
               (carer_id, notification_type, payload)
               VALUES (?, ?, ?)""",
            (carer_id, notification_type, payload_json),
        )
        await db.commit()

        new_cursor = await db.execute(
            "SELECT * FROM push_notifications WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def update_notification_status(
    notification_id: int,
    status: str,
    sent_at: str | None = None,
    delivered_at: str | None = None,
    increment_retry: bool = False,
) -> dict | None:
    """Update the delivery status of a push notification.

    Args:
        notification_id: The notification identifier.
        status: New status ('pending', 'delivered', 'failed', 'undelivered').
        sent_at: ISO 8601 timestamp when sent (optional).
        delivered_at: ISO 8601 timestamp when delivered (optional).
        increment_retry: Whether to increment the retry_count.

    Returns:
        The updated notification row as a dict, or None if not found.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM push_notifications WHERE id = ?", (notification_id,)
        )
        if not await cursor.fetchone():
            return None

        updates = ["status = ?"]
        params: list = [status]

        if sent_at is not None:
            updates.append("sent_at = ?")
            params.append(sent_at)

        if delivered_at is not None:
            updates.append("delivered_at = ?")
            params.append(delivered_at)

        if increment_retry:
            updates.append("retry_count = retry_count + 1")

        params.append(notification_id)
        set_clause = ", ".join(updates)
        await db.execute(
            f"UPDATE push_notifications SET {set_clause} WHERE id = ?",
            params,
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM push_notifications WHERE id = ?", (notification_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def get_recent_notifications_for_carer(
    carer_id: int, limit: int = 20
) -> list[dict]:
    """Retrieve recent push notifications for a carer.

    Args:
        carer_id: The carer's identifier.
        limit: Maximum number of notifications to return (default 20).

    Returns:
        List of notification rows, ordered by created_at descending.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM push_notifications
               WHERE carer_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (carer_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def count_notifications_in_window(
    carer_id: int, window_minutes: int = 60
) -> int:
    """Count push notifications sent to a carer within a time window.

    Used for rate limiting: max 10 notifications per hour per carer.

    Args:
        carer_id: The carer's identifier.
        window_minutes: Lookback window in minutes (default 60).

    Returns:
        Number of notifications created within the window.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT COUNT(*) as cnt FROM push_notifications
               WHERE carer_id = ?
                 AND created_at >= datetime('now', ?)""",
            (carer_id, f"-{window_minutes} minutes"),
        )
        row = await cursor.fetchone()
        return row["cnt"]


# --- Schedule operations ---


async def get_carer_schedule_for_today(carer_id: int, today: str) -> list[dict]:
    """Retrieve the carer's visit schedule for a given day.

    Joins visits with patients to provide full schedule information including
    patient name, address, coordinates, and visit details. Also includes
    the current visit status and confidence score if available.

    Args:
        carer_id: The carer's identifier.
        today: The date in YYYY-MM-DD format (used to identify the plan).

    Returns:
        List of visit schedule dicts ordered by window_start ascending.
        Each dict contains: visit_id, patient_name, patient_address,
        patient_lat, patient_lng, window_start, window_end,
        duration_minutes, required_skills, status, confidence_score.
    """
    async with get_db() as db:
        # Get visits assigned to this carer via journeys for today's plan
        # Fall back to all non-cancelled visits if no journey plan exists
        cursor = await db.execute(
            """SELECT DISTINCT v.id as visit_id,
                      p.name as patient_name,
                      p.address as patient_address,
                      p.lat as patient_lat,
                      p.lng as patient_lng,
                      v.window_start,
                      v.window_end,
                      v.duration_minutes,
                      v.required_skills,
                      vs.status,
                      vs.confidence_score
               FROM journeys j
               INNER JOIN journey_plans jp ON j.plan_id = jp.id
               INNER JOIN visits v ON j.visit_id = v.id
               INNER JOIN patients p ON v.patient_id = p.id
               LEFT JOIN visit_status vs ON vs.visit_id = v.id AND vs.is_current = 1
               WHERE j.carer_id = ?
                 AND jp.operating_day = ?
                 AND jp.is_archived = 0
                 AND v.is_cancelled = 0
                 AND j.visit_id IS NOT NULL
               ORDER BY v.window_start ASC""",
            (carer_id, today),
        )
        rows = await cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "visit_id": row["visit_id"],
                "patient_name": row["patient_name"],
                "patient_address": row["patient_address"],
                "patient_lat": row["patient_lat"],
                "patient_lng": row["patient_lng"],
                "window_start": row["window_start"],
                "window_end": row["window_end"],
                "duration_minutes": row["duration_minutes"],
                "required_skills": json.loads(row["required_skills"]),
                "status": row["status"] or "pending",
                "confidence_score": row["confidence_score"] or 0,
            })
        return results
