"""Question Engine for the Carer Mobile App.

Determines appropriate contextual questions based on carer context
(visit state, confidence level, time since last question).
Enforces rate limiting: max 1 question per visit per 10 minutes.
Manages question lifecycle: sent → answered / timed_out / suppressed.

Trigger conditions (from the Status Inference Engine):
  - Confidence score falls below 60
  - Conflicting signals are detected
  - No signal received for 15+ minutes
"""

from datetime import datetime

from backend.app.db.mobile_repository import (
    create_notification,
    create_question,
    get_current_status_for_visit,
    get_recent_questions_for_visit,
)


# Rate limit: max 1 question per visit per 10 minutes
RATE_LIMIT_MINUTES = 10

# Confidence threshold below which a question is triggered
CONFIDENCE_THRESHOLD = 60


def generate_question_text(
    visit_status: str | None,
    patient_name: str | None = None,
) -> str:
    """Generate appropriate question text based on visit context.

    Question generation logic:
      - For confidence < 60 on a "travelling" visit: "Have you arrived at [patient]'s?"
      - For confidence < 60 on "in_progress" visit: "Is your visit with [patient] complete?"
      - For conflicting signals: "Please confirm: are you currently at [patient]'s address?"
      - For no-signal timeout: "Are you still on your shift?"

    Args:
        visit_status: The current visit status (e.g., 'pending', 'travelling').
        patient_name: The patient's name for personalised questions.

    Returns:
        A question string to display to the carer.
    """
    name = patient_name or "the patient"

    if visit_status == "no_signal":
        return "Are you still on your shift?"
    elif visit_status == "conflict":
        return f"Please confirm: are you currently at {name}'s address?"
    elif visit_status in (None, "pending"):
        return f"Have you arrived at {name}'s?"
    elif visit_status == "travelling":
        return f"Have you arrived at {name}'s?"
    elif visit_status == "arrived":
        return f"Have you started your visit with {name}?"
    elif visit_status == "in_progress":
        return f"Is your visit with {name} complete?"
    elif visit_status == "delayed":
        return f"Are you still on your way to {name}?"
    else:
        return f"Can you confirm your current status for the visit with {name}?"


def get_question_for_confidence(
    visit_status: str | None,
    patient_name: str | None = None,
) -> str:
    """Generate appropriate question text based on visit context and confidence.

    Dispatches to generate_question_text which handles all context types
    including conflict and no-signal scenarios.

    Args:
        visit_status: The current visit status or special context
                      ('conflict', 'no_signal').
        patient_name: The patient's name for personalised questions.

    Returns:
        A context-appropriate question string.
    """
    return generate_question_text(visit_status, patient_name)


async def should_ask_question(
    carer_id: int, visit_id: int, confidence_score: int
) -> bool:
    """Determine if a question should be triggered based on carer context.

    Returns False if confidence >= 60 (no question needed).
    Returns False if a question was sent for this visit within the last 10 minutes.
    Returns True otherwise.

    Args:
        carer_id: The carer's identifier.
        visit_id: The visit identifier.
        confidence_score: The current confidence score (0-100).

    Returns:
        True if a question should be asked, False otherwise.
    """
    if confidence_score >= CONFIDENCE_THRESHOLD:
        return False

    recent = await get_recent_questions_for_visit(visit_id, RATE_LIMIT_MINUTES)
    return len(recent) == 0


async def should_send_question(visit_id: int) -> bool:
    """Check whether a question can be sent for a visit (rate-limit check).

    Enforces max 1 question per visit per 10 minutes.

    Args:
        visit_id: The visit identifier.

    Returns:
        True if a question can be sent, False if rate-limited.
    """
    recent = await get_recent_questions_for_visit(visit_id, RATE_LIMIT_MINUTES)
    return len(recent) == 0


async def create_contextual_question(
    carer_id: int,
    visit_id: int,
    question_text: str,
    question_type: str,
    options: list[str] | None = None,
) -> dict:
    """Create a contextual question and trigger a push notification.

    Creates the question record in the database with status='sent' and
    sends a push notification to the carer's device.

    Args:
        carer_id: The carer's identifier.
        visit_id: The visit identifier.
        question_text: The question text to display.
        question_type: One of 'yes_no', 'single_choice', 'free_text'.
        options: Optional list of options for single_choice type.

    Returns:
        The newly created question record as a dict.
    """
    # Create the question record (status defaults to 'sent')
    question = await create_question(
        carer_id=carer_id,
        visit_id=visit_id,
        question_text=question_text,
        question_type=question_type,
        options=options,
    )

    # Trigger a push notification for the contextual question
    await create_notification(
        carer_id=carer_id,
        notification_type="contextual_question",
        payload={
            "question_id": question["id"],
            "visit_id": visit_id,
            "question_text": question_text,
            "question_type": question_type,
            "options": options,
        },
    )

    return question


async def trigger_question(
    carer_id: int,
    visit_id: int,
    confidence_score: int,
    patient_name: str | None = None,
    visit_status: str | None = None,
) -> dict | None:
    """Trigger a contextual question for a carer if rate limits allow.

    This is the main entry point called by the Status Inference Engine
    when confidence falls below the threshold (60).

    Args:
        carer_id: The carer's identifier.
        visit_id: The visit identifier.
        confidence_score: The current confidence score (should be < 60).
        patient_name: Optional patient name for personalised question text.
        visit_status: The current visit status for context-appropriate text.

    Returns:
        The created question dict if sent, or None if rate-limited.
    """
    # Check rate limit
    if not await should_send_question(visit_id):
        return None

    # If visit_status not provided, look it up
    if visit_status is None:
        current = await get_current_status_for_visit(visit_id)
        if current:
            visit_status = current["status"]

    # Generate appropriate question text
    question_text = get_question_for_confidence(visit_status, patient_name)

    # Create the question and send push notification
    question = await create_contextual_question(
        carer_id=carer_id,
        visit_id=visit_id,
        question_text=question_text,
        question_type="yes_no",
    )

    return question


async def trigger_question_for_low_confidence(
    carer_id: int,
    visit_id: int,
    confidence_score: int,
    patient_name: str | None = None,
) -> dict | None:
    """Trigger a question when confidence score falls below threshold.

    Only triggers if confidence < CONFIDENCE_THRESHOLD (60) AND
    rate limit allows (max 1 per visit per 10 min).

    Args:
        carer_id: The carer's identifier.
        visit_id: The visit identifier.
        confidence_score: The current confidence score.
        patient_name: Optional patient name for personalised question text.

    Returns:
        The created question dict if triggered, or None if not needed/rate-limited.
    """
    if confidence_score >= CONFIDENCE_THRESHOLD:
        return None

    return await trigger_question(
        carer_id=carer_id,
        visit_id=visit_id,
        confidence_score=confidence_score,
        patient_name=patient_name,
    )
