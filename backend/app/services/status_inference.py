"""Status Inference Engine for the Carer Mobile App.

Combines GPS signals, contextual question responses, and proactive inputs
to maintain real-time visit status with confidence scoring, geofence-based
proximity detection, and a defined state machine.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

from backend.app.db import mobile_repository as repo
from backend.app.models.mobile import (
    VisitStatus,
    VALID_TRANSITIONS,
)

logger = logging.getLogger(__name__)

# Geofence thresholds (metres)
GEOFENCE_ENTRY_RADIUS = 100
GEOFENCE_EXIT_RADIUS = 150

# Time thresholds
IN_PROGRESS_THRESHOLD_MINUTES = 5
CONFIDENCE_DECAY_INTERVAL_MINUTES = 15
CONFIDENCE_DECAY_AMOUNT = 20
MISSED_THRESHOLD_MINUTES = 30
CONFLICT_WINDOW_MINUTES = 10
QUESTION_RATE_LIMIT_MINUTES = 10
LOW_CONFIDENCE_THRESHOLD = 60

# Duration tolerance for completion inference
DURATION_TOLERANCE = 0.5  # ±50%

# Terminal statuses that should not be re-evaluated
TERMINAL_STATUSES = {VisitStatus.COMPLETED, VisitStatus.MISSED, VisitStatus.CANCELLED}


@dataclass
class InferenceResult:
    """Result of a status inference evaluation."""

    new_status: VisitStatus
    confidence: int  # 0-100
    trigger: str  # 'gps', 'question', 'proactive', 'timeout', 'system'
    signal_id: Optional[int] = None


@dataclass
class VisitContext:
    """Contextual data for a visit being evaluated."""

    visit_id: int
    carer_id: int
    current_status: VisitStatus
    confidence_score: int
    patient_lat: float
    patient_lng: float
    window_start: str
    window_end: str
    duration_minutes: int
    last_signal_at: Optional[datetime] = None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points (metres).

    Uses the haversine formula for accuracy at short distances.

    Args:
        lat1, lon1: Coordinates of point 1 in decimal degrees.
        lat2, lon2: Coordinates of point 2 in decimal degrees.

    Returns:
        Distance in metres.
    """
    R = 6_371_000  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class StatusInferenceEngine:
    """Core inference engine combining signals to determine visit status.

    Signal priority (highest to lowest):
    1. Explicit confirmation (proactive input or question response) → confidence 100
    2. GPS-based inference with time correlation → confidence 60-85
    3. Time-based inference (no signals) → confidence decreasing over time

    Geofence parameters:
    - Entry: carer within 100m of patient address
    - Exit: carer beyond 150m of patient address (hysteresis)
    - In-progress threshold: 5 minutes continuous inside geofence
    - Completion threshold: departure after visit duration ±50%

    Confidence decay:
    - No signal for 15 minutes → -20 points
    - Below 60 → trigger contextual question (max 1 per 10 min per visit)

    Conflict resolution:
    - Conflicting signals within 10 min → uncertain status, trigger question
    """

    async def process_signal(
        self,
        carer_id: int,
        signal_type: str,
        signal_data: dict,
        signal_id: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> list[dict]:
        """Process an incoming signal and re-evaluate all non-terminal visits.

        Args:
            carer_id: The carer's identifier.
            signal_type: One of 'gps', 'question', 'proactive'.
            signal_data: Signal payload data.
            signal_id: ID of the signal record in its table.
            now: Current time (for testing; defaults to utcnow).

        Returns:
            List of status change dicts with visit_id, old_status, new_status,
            confidence, and trigger.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Get all non-terminal visits for this carer
        visits = await self._get_non_terminal_visits(carer_id, now)
        changes: list[dict] = []

        for visit_ctx in visits:
            result = await self._evaluate_visit(
                visit_ctx, signal_type, signal_data, signal_id, now
            )
            if result is not None:
                success = await self._apply_transition(
                    visit_ctx, result, now
                )
                if success:
                    changes.append({
                        "visit_id": visit_ctx.visit_id,
                        "old_status": visit_ctx.current_status.value,
                        "new_status": result.new_status.value,
                        "confidence": result.confidence,
                        "trigger": result.trigger,
                    })

        return changes

    async def check_timeouts(
        self,
        carer_id: int,
        now: Optional[datetime] = None,
    ) -> list[dict]:
        """Check for timeout-based transitions (missed visits, confidence decay).

        Should be called periodically (e.g., every minute) for each active carer.

        Args:
            carer_id: The carer's identifier.
            now: Current time (for testing; defaults to utcnow).

        Returns:
            List of status change dicts.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        visits = await self._get_non_terminal_visits(carer_id, now)
        changes: list[dict] = []

        for visit_ctx in visits:
            # Check missed transition: 30min past window end
            result = self._check_missed_timeout(visit_ctx, now)
            if result is not None:
                success = await self._apply_transition(visit_ctx, result, now)
                if success:
                    changes.append({
                        "visit_id": visit_ctx.visit_id,
                        "old_status": visit_ctx.current_status.value,
                        "new_status": result.new_status.value,
                        "confidence": result.confidence,
                        "trigger": result.trigger,
                    })
                continue

            # Check confidence decay: no signal for 15min
            await self._check_confidence_decay(visit_ctx, now)

        return changes

    async def _get_non_terminal_visits(self, carer_id: int, now: Optional[datetime] = None) -> list[VisitContext]:
        """Retrieve all non-terminal visits for a carer with context.

        Returns:
            List of VisitContext objects for visits not in terminal states.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        statuses = await repo.get_current_statuses_for_carer(carer_id)
        schedule = await repo.get_carer_schedule_for_today(carer_id, today)

        # Build a lookup from schedule
        schedule_lookup: dict[int, dict] = {}
        for visit in schedule:
            schedule_lookup[visit["visit_id"]] = visit

        contexts: list[VisitContext] = []

        # Include visits from schedule that have a status record
        for status_row in statuses:
            visit_status = VisitStatus(status_row["status"])
            if visit_status in TERMINAL_STATUSES:
                continue

            visit_id = status_row["visit_id"]
            sched = schedule_lookup.get(visit_id)
            if sched is None:
                continue

            contexts.append(VisitContext(
                visit_id=visit_id,
                carer_id=carer_id,
                current_status=visit_status,
                confidence_score=status_row["confidence_score"],
                patient_lat=sched["patient_lat"],
                patient_lng=sched["patient_lng"],
                window_start=sched["window_start"],
                window_end=sched["window_end"],
                duration_minutes=sched["duration_minutes"],
            ))

        # Also include scheduled visits without a status record (implicitly pending)
        for visit in schedule:
            vid = visit["visit_id"]
            if vid not in {s["visit_id"] for s in statuses}:
                contexts.append(VisitContext(
                    visit_id=vid,
                    carer_id=carer_id,
                    current_status=VisitStatus.PENDING,
                    confidence_score=50,
                    patient_lat=visit["patient_lat"],
                    patient_lng=visit["patient_lng"],
                    window_start=visit["window_start"],
                    window_end=visit["window_end"],
                    duration_minutes=visit["duration_minutes"],
                ))

        return contexts

    async def _evaluate_visit(
        self,
        visit: VisitContext,
        signal_type: str,
        signal_data: dict,
        signal_id: Optional[int],
        now: datetime,
    ) -> Optional[InferenceResult]:
        """Evaluate a single visit against an incoming signal.

        Priority order:
        1. Explicit confirmation (proactive/question) → confidence 100
        2. GPS geofence inference → confidence 60-85
        3. Conflict detection → uncertain + question

        Returns:
            InferenceResult if a transition is warranted, None otherwise.
        """
        # Priority 1: Explicit confirmation from proactive input
        if signal_type == "proactive":
            return self._evaluate_proactive(visit, signal_data, signal_id)

        # Priority 1: Explicit confirmation from question response
        if signal_type == "question":
            return self._evaluate_question_response(visit, signal_data, signal_id)

        # Priority 2: GPS-based inference
        if signal_type == "gps":
            # Check for conflicts first
            conflict = await self._check_conflicts(visit, signal_data, now)
            if conflict is not None:
                return conflict
            return await self._evaluate_gps(visit, signal_data, signal_id, now)

        return None

    def _evaluate_proactive(
        self,
        visit: VisitContext,
        signal_data: dict,
        signal_id: Optional[int],
    ) -> Optional[InferenceResult]:
        """Evaluate a proactive input signal for a visit.

        Maps proactive input_type to target visit status:
        - arrived → arrived
        - visit_started → in_progress
        - visit_completed → completed
        - running_late → delayed
        - cannot_complete → cancelled

        Returns:
            InferenceResult with confidence 100 if the signal targets this visit,
            None otherwise.
        """
        # Only process if this proactive input is for this specific visit
        if signal_data.get("visit_id") != visit.visit_id:
            return None

        input_type = signal_data.get("input_type", "")
        status_map = {
            "arrived": VisitStatus.ARRIVED,
            "visit_started": VisitStatus.IN_PROGRESS,
            "visit_completed": VisitStatus.COMPLETED,
            "running_late": VisitStatus.DELAYED,
            "cannot_complete": VisitStatus.CANCELLED,
        }

        target_status = status_map.get(input_type)
        if target_status is None:
            return None

        # Validate the transition is allowed
        if target_status not in VALID_TRANSITIONS.get(visit.current_status, set()):
            logger.warning(
                "Invalid transition rejected: visit=%d, from=%s, to=%s, trigger=proactive",
                visit.visit_id,
                visit.current_status.value,
                target_status.value,
            )
            return None

        return InferenceResult(
            new_status=target_status,
            confidence=100,
            trigger="proactive",
            signal_id=signal_id,
        )

    def _evaluate_question_response(
        self,
        visit: VisitContext,
        signal_data: dict,
        signal_id: Optional[int],
    ) -> Optional[InferenceResult]:
        """Evaluate a contextual question response for a visit.

        If the response explicitly confirms a status, override with confidence 100.

        Returns:
            InferenceResult with confidence 100, or None if not applicable.
        """
        # Only process if this question is for this specific visit
        if signal_data.get("visit_id") != visit.visit_id:
            return None

        # Map common response patterns to statuses
        response_text = signal_data.get("response_text", "").lower().strip()
        confirmed_status = signal_data.get("confirmed_status")

        if confirmed_status:
            target_status = VisitStatus(confirmed_status)
        elif response_text in ("yes", "arrived", "i have arrived"):
            target_status = VisitStatus.ARRIVED
        elif response_text in ("started", "in progress", "yes started"):
            target_status = VisitStatus.IN_PROGRESS
        elif response_text in ("completed", "done", "finished"):
            target_status = VisitStatus.COMPLETED
        elif response_text in ("delayed", "running late", "late"):
            target_status = VisitStatus.DELAYED
        else:
            # Response doesn't map to a clear status change
            return None

        # Validate the transition is allowed
        if target_status not in VALID_TRANSITIONS.get(visit.current_status, set()):
            logger.warning(
                "Invalid transition rejected: visit=%d, from=%s, to=%s, trigger=question",
                visit.visit_id,
                visit.current_status.value,
                target_status.value,
            )
            return None

        return InferenceResult(
            new_status=target_status,
            confidence=100,
            trigger="question",
            signal_id=signal_id,
        )

    async def _evaluate_gps(
        self,
        visit: VisitContext,
        signal_data: dict,
        signal_id: Optional[int],
        now: datetime,
    ) -> Optional[InferenceResult]:
        """Evaluate GPS signals for geofence-based status inference.

        Geofence logic:
        - Entry at 100m → arrived (confidence 75 after 5min presence)
        - Exit at 150m after expected duration → completed (confidence 70)
        - Movement away from current position during delay → travelling

        Returns:
            InferenceResult if a transition is warranted, None otherwise.
        """
        lat = signal_data.get("latitude")
        lng = signal_data.get("longitude")
        if lat is None or lng is None:
            return None

        distance = haversine_distance(lat, lng, visit.patient_lat, visit.patient_lng)

        # Determine geofence state
        inside_geofence = distance <= GEOFENCE_ENTRY_RADIUS
        outside_geofence = distance > GEOFENCE_EXIT_RADIUS

        if inside_geofence:
            return await self._handle_geofence_entry(
                visit, signal_data, signal_id, now
            )
        elif outside_geofence:
            return await self._handle_geofence_exit(
                visit, signal_data, signal_id, now
            )

        return None

    async def _handle_geofence_entry(
        self,
        visit: VisitContext,
        signal_data: dict,
        signal_id: Optional[int],
        now: datetime,
    ) -> Optional[InferenceResult]:
        """Handle carer entering the geofence of a patient address.

        - pending/travelling → arrived (confidence 75) on first entry
        - arrived → in_progress after 5min continuous presence (confidence 75)
        """
        if visit.current_status in (VisitStatus.PENDING, VisitStatus.TRAVELLING):
            target = VisitStatus.ARRIVED
            if target in VALID_TRANSITIONS.get(visit.current_status, set()):
                return InferenceResult(
                    new_status=target,
                    confidence=75,
                    trigger="gps",
                    signal_id=signal_id,
                )

        if visit.current_status == VisitStatus.ARRIVED:
            # Check if carer has been inside geofence for 5+ minutes
            presence_duration = await self._get_geofence_presence_duration(
                visit, now
            )
            if presence_duration >= timedelta(minutes=IN_PROGRESS_THRESHOLD_MINUTES):
                target = VisitStatus.IN_PROGRESS
                if target in VALID_TRANSITIONS.get(visit.current_status, set()):
                    return InferenceResult(
                        new_status=target,
                        confidence=75,
                        trigger="gps",
                        signal_id=signal_id,
                    )

        return None

    async def _handle_geofence_exit(
        self,
        visit: VisitContext,
        signal_data: dict,
        signal_id: Optional[int],
        now: datetime,
    ) -> Optional[InferenceResult]:
        """Handle carer exiting the geofence of a patient address.

        - in_progress → completed if presence duration was within ±50% of expected
        - delayed → travelling (resume travel detected)
        """
        if visit.current_status == VisitStatus.IN_PROGRESS:
            # Check if presence duration is consistent with expected visit duration
            presence_duration = await self._get_total_presence_duration(visit, now)
            expected = timedelta(minutes=visit.duration_minutes)
            min_duration = expected * (1 - DURATION_TOLERANCE)
            max_duration = expected * (1 + DURATION_TOLERANCE)

            if min_duration <= presence_duration <= max_duration:
                target = VisitStatus.COMPLETED
                if target in VALID_TRANSITIONS.get(visit.current_status, set()):
                    return InferenceResult(
                        new_status=target,
                        confidence=70,
                        trigger="gps",
                        signal_id=signal_id,
                    )

        if visit.current_status == VisitStatus.DELAYED:
            target = VisitStatus.TRAVELLING
            if target in VALID_TRANSITIONS.get(visit.current_status, set()):
                return InferenceResult(
                    new_status=target,
                    confidence=65,
                    trigger="gps",
                    signal_id=signal_id,
                )

        return None

    async def _get_geofence_presence_duration(
        self,
        visit: VisitContext,
        now: datetime,
    ) -> timedelta:
        """Calculate how long the carer has been continuously inside the geofence.

        Looks at recent GPS signals and finds the earliest continuous signal
        within the geofence entry radius.

        Returns:
            Duration of continuous presence inside the geofence.
        """
        signals = await repo.get_recent_signals_for_carer(visit.carer_id, limit=50)

        # Signals are returned in descending order by captured_at
        earliest_inside = now
        for signal in signals:
            lat = signal["latitude"]
            lng = signal["longitude"]
            distance = haversine_distance(
                lat, lng, visit.patient_lat, visit.patient_lng
            )
            if distance <= GEOFENCE_ENTRY_RADIUS:
                signal_time = _parse_datetime(signal["captured_at"])
                earliest_inside = signal_time
            else:
                # Found a signal outside the geofence, stop looking
                break

        return now - earliest_inside

    async def _get_total_presence_duration(
        self,
        visit: VisitContext,
        now: datetime,
    ) -> timedelta:
        """Calculate the total time the carer spent inside the geofence.

        Sums all periods where GPS signals show the carer within the
        geofence entry radius for this visit.

        Returns:
            Total presence duration.
        """
        signals = await repo.get_recent_signals_for_carer(visit.carer_id, limit=100)

        # Signals are ordered by captured_at DESC; reverse for chronological
        signals_chrono = list(reversed(signals))
        total = timedelta()
        entry_time: Optional[datetime] = None

        for signal in signals_chrono:
            lat = signal["latitude"]
            lng = signal["longitude"]
            distance = haversine_distance(
                lat, lng, visit.patient_lat, visit.patient_lng
            )
            signal_time = _parse_datetime(signal["captured_at"])

            if distance <= GEOFENCE_ENTRY_RADIUS:
                if entry_time is None:
                    entry_time = signal_time
            else:
                if entry_time is not None:
                    total += signal_time - entry_time
                    entry_time = None

        # If still inside at the last signal, count up to now
        if entry_time is not None:
            total += now - entry_time

        return total

    async def _check_conflicts(
        self,
        visit: VisitContext,
        signal_data: dict,
        now: datetime,
    ) -> Optional[InferenceResult]:
        """Check if the incoming signal conflicts with recent signals.

        Conflicting signals within a 10-minute window trigger uncertain status
        and a contextual question.

        Returns:
            InferenceResult marking uncertain if conflict detected, None otherwise.
        """
        # Get recent GPS signals for this carer
        signals = await repo.get_recent_signals_for_carer(visit.carer_id, limit=20)
        if not signals:
            return None

        lat = signal_data.get("latitude")
        lng = signal_data.get("longitude")
        if lat is None or lng is None:
            return None

        current_distance = haversine_distance(
            lat, lng, visit.patient_lat, visit.patient_lng
        )
        current_inside = current_distance <= GEOFENCE_ENTRY_RADIUS

        # Check recent signals within the conflict window
        conflict_window = now - timedelta(minutes=CONFLICT_WINDOW_MINUTES)
        for signal in signals:
            signal_time = _parse_datetime(signal["captured_at"])
            if signal_time < conflict_window:
                break

            prev_distance = haversine_distance(
                signal["latitude"],
                signal["longitude"],
                visit.patient_lat,
                visit.patient_lng,
            )
            prev_inside = prev_distance <= GEOFENCE_ENTRY_RADIUS

            # Conflict: one says inside, the other says outside
            if current_inside != prev_inside:
                # Only flag conflict if the visit is in a non-pending state
                if visit.current_status not in (
                    VisitStatus.PENDING,
                    VisitStatus.MISSED,
                    VisitStatus.CANCELLED,
                ):
                    await self._trigger_question_if_allowed(visit, now)
                    # Don't transition on conflict - just trigger question
                    return None

        return None

    def _check_missed_timeout(
        self,
        visit: VisitContext,
        now: datetime,
    ) -> Optional[InferenceResult]:
        """Check if a visit should be transitioned to missed.

        A visit is missed if it remains in pending or delayed status and
        30 minutes have elapsed after the scheduled window end.

        Returns:
            InferenceResult for missed transition, or None.
        """
        if visit.current_status not in (VisitStatus.PENDING, VisitStatus.DELAYED):
            return None

        window_end = _parse_window_time(visit.window_end, now)
        missed_threshold = window_end + timedelta(minutes=MISSED_THRESHOLD_MINUTES)

        if now >= missed_threshold:
            target = VisitStatus.MISSED
            if target in VALID_TRANSITIONS.get(visit.current_status, set()):
                return InferenceResult(
                    new_status=target,
                    confidence=100,
                    trigger="timeout",
                )

        return None

    async def _check_confidence_decay(
        self,
        visit: VisitContext,
        now: datetime,
    ) -> None:
        """Apply confidence decay if no signal received for 15+ minutes.

        Reduces confidence by 20 points per 15-minute silence period.
        Triggers a contextual question if confidence drops below 60.
        """
        # Get the most recent signal for this carer
        signals = await repo.get_recent_signals_for_carer(visit.carer_id, limit=1)
        if not signals:
            return

        last_signal_time = _parse_datetime(signals[0]["captured_at"])
        silence_duration = now - last_signal_time

        if silence_duration >= timedelta(minutes=CONFIDENCE_DECAY_INTERVAL_MINUTES):
            # Calculate decay: -20 for each 15min period of silence
            periods = int(
                silence_duration.total_seconds()
                / (CONFIDENCE_DECAY_INTERVAL_MINUTES * 60)
            )
            decay = periods * CONFIDENCE_DECAY_AMOUNT
            new_confidence = max(0, visit.confidence_score - decay)

            if new_confidence != visit.confidence_score:
                # Update the confidence score without changing status
                await repo.set_visit_status(
                    visit_id=visit.visit_id,
                    carer_id=visit.carer_id,
                    status=visit.current_status.value,
                    confidence_score=new_confidence,
                    inferred_by="timeout",
                )

                # Trigger question if confidence is below threshold
                if new_confidence < LOW_CONFIDENCE_THRESHOLD:
                    await self._trigger_question_if_allowed(visit, now)

    async def _trigger_question_if_allowed(
        self,
        visit: VisitContext,
        now: datetime,
    ) -> bool:
        """Trigger a contextual question if rate limit allows.

        Rate limit: max 1 question per visit per 10 minutes.

        Args:
            visit: The visit context.
            now: Current time.

        Returns:
            True if a question was triggered, False if rate-limited.
        """
        recent_questions = await repo.get_recent_questions_for_visit(
            visit.visit_id, minutes=QUESTION_RATE_LIMIT_MINUTES
        )
        if recent_questions:
            return False

        # Determine appropriate question text based on visit state
        question_text = self._generate_question_text(visit)

        await repo.create_question(
            carer_id=visit.carer_id,
            visit_id=visit.visit_id,
            question_text=question_text,
            question_type="yes_no",
        )
        return True

    def _generate_question_text(self, visit: VisitContext) -> str:
        """Generate an appropriate question based on visit context.

        Returns:
            Question text string.
        """
        status_questions = {
            VisitStatus.PENDING: "Are you on your way to your next visit?",
            VisitStatus.TRAVELLING: "Have you arrived at the patient's address?",
            VisitStatus.ARRIVED: "Have you started the visit?",
            VisitStatus.IN_PROGRESS: "Is the visit still in progress?",
            VisitStatus.DELAYED: "Are you still running late?",
        }
        return status_questions.get(
            visit.current_status,
            "Can you confirm your current visit status?",
        )

    async def _apply_transition(
        self,
        visit: VisitContext,
        result: InferenceResult,
        now: datetime,
    ) -> bool:
        """Apply a status transition, enforcing valid transitions and recording audit.

        Args:
            visit: The current visit context.
            result: The inferred transition result.
            now: Current time.

        Returns:
            True if the transition was applied, False if rejected.
        """
        # Validate transition
        allowed = VALID_TRANSITIONS.get(visit.current_status, set())
        if result.new_status not in allowed:
            logger.warning(
                "Invalid transition rejected: visit=%d, from=%s, to=%s, trigger=%s",
                visit.visit_id,
                visit.current_status.value,
                result.new_status.value,
                result.trigger,
            )
            return False

        # Clamp confidence to valid range
        confidence = max(0, min(100, result.confidence))

        # Set new visit status
        await repo.set_visit_status(
            visit_id=visit.visit_id,
            carer_id=visit.carer_id,
            status=result.new_status.value,
            confidence_score=confidence,
            inferred_by=result.trigger,
        )

        # Record audit trail
        await repo.create_transition(
            visit_id=visit.visit_id,
            previous_status=visit.current_status.value,
            new_status=result.new_status.value,
            trigger_signal_type=result.trigger,
            confidence_score=confidence,
            trigger_signal_id=result.signal_id,
        )

        return True

    def is_valid_transition(
        self, from_status: VisitStatus, to_status: VisitStatus
    ) -> bool:
        """Check if a transition between two statuses is valid.

        Args:
            from_status: The current status.
            to_status: The proposed target status.

        Returns:
            True if the transition is valid, False otherwise.
        """
        return to_status in VALID_TRANSITIONS.get(from_status, set())


def _parse_datetime(dt_str: str) -> datetime:
    """Parse an ISO 8601 datetime string to a timezone-aware datetime.

    Handles both timezone-aware and naive strings (assumes UTC for naive).

    Args:
        dt_str: ISO 8601 datetime string.

    Returns:
        Timezone-aware datetime in UTC.
    """
    if isinstance(dt_str, datetime):
        if dt_str.tzinfo is None:
            return dt_str.replace(tzinfo=timezone.utc)
        return dt_str

    # Try parsing with timezone info
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError:
        # Fallback for formats without timezone
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_window_time(time_str: str, reference_date: datetime) -> datetime:
    """Parse a time window string (HH:MM or full datetime) to a datetime.

    If the string is in HH:MM format, combines it with the reference date.
    If it's a full ISO datetime, parses it directly.

    Args:
        time_str: Time string in HH:MM format or ISO 8601 datetime.
        reference_date: Reference datetime to use for date part when parsing HH:MM.

    Returns:
        Timezone-aware datetime in UTC.
    """
    if isinstance(time_str, datetime):
        if time_str.tzinfo is None:
            return time_str.replace(tzinfo=timezone.utc)
        return time_str

    # Check if it's HH:MM format (short string, contains single colon)
    if len(time_str) <= 5 and ":" in time_str and "T" not in time_str:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        return reference_date.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

    # Otherwise parse as full datetime
    return _parse_datetime(time_str)
