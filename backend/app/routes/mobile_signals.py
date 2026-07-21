"""Mobile signal ingestion API endpoints for the Carer Mobile App.

Provides endpoints for GPS batch signals, contextual question responses,
and proactive inputs. All endpoints are protected and require JWT auth.
Implements idempotent handling via deduplication by (carer_id, captured_at, signal_type).
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.app.db.database import get_db
from backend.app.db.mobile_repository import (
    create_gps_signals_batch,
    create_proactive_input,
    update_question_response,
)
from backend.app.models.mobile import (
    GPSBatch,
    ProactiveInput,
    QuestionResponse,
)
from backend.app.routes.mobile_auth import get_current_carer

router = APIRouter(prefix="/api/mobile/signals", tags=["mobile-signals"])


async def _is_duplicate_gps(carer_id: int, captured_at: str) -> bool:
    """Check if a GPS signal with the same carer_id and captured_at already exists.

    Args:
        carer_id: The carer's identifier.
        captured_at: The ISO 8601 timestamp from the device.

    Returns:
        True if a duplicate exists, False otherwise.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM gps_signals WHERE carer_id = ? AND captured_at = ?",
            (carer_id, captured_at),
        )
        return await cursor.fetchone() is not None


async def _is_duplicate_proactive(
    carer_id: int, captured_at: str, input_type: str
) -> bool:
    """Check if a proactive input with the same carer_id, captured_at, and type exists.

    Args:
        carer_id: The carer's identifier.
        captured_at: The ISO 8601 timestamp from the device.
        input_type: The proactive input type.

    Returns:
        True if a duplicate exists, False otherwise.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id FROM proactive_inputs
               WHERE carer_id = ? AND captured_at = ? AND input_type = ?""",
            (carer_id, captured_at, input_type),
        )
        return await cursor.fetchone() is not None


@router.post("/gps", status_code=201)
async def submit_gps_signals(
    batch: GPSBatch,
    carer_id: int = Depends(get_current_carer),
) -> dict:
    """Submit a batch of GPS signals.

    Accepts up to 50 GPS signals per batch. For each signal, sets low_accuracy=True
    if accuracy_metres > 50. Deduplicates by (carer_id, captured_at).

    Returns:
        201 with count of signals stored.
    """
    signals_to_store = []

    for signal in batch.signals:
        captured_at_str = signal.captured_at.isoformat()

        # Idempotent: skip duplicates
        if await _is_duplicate_gps(carer_id, captured_at_str):
            continue

        # Set low_accuracy flag based on accuracy threshold
        low_accuracy = signal.accuracy_metres > 50

        signals_to_store.append({
            "latitude": signal.latitude,
            "longitude": signal.longitude,
            "accuracy_metres": signal.accuracy_metres,
            "low_accuracy": low_accuracy,
            "captured_at": captured_at_str,
        })

    stored = []
    if signals_to_store:
        stored = await create_gps_signals_batch(carer_id, signals_to_store)

    return {"count": len(stored)}


@router.post("/question", status_code=200)
async def submit_question_response(
    response: QuestionResponse,
    carer_id: int = Depends(get_current_carer),
) -> dict:
    """Submit a response to a contextual question.

    Validates that the question_id exists and belongs to this carer.

    Returns:
        200 with updated question status.
    """
    # Validate the question exists and belongs to this carer
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, carer_id, status FROM contextual_questions WHERE id = ?",
            (response.question_id,),
        )
        question = await cursor.fetchone()

    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    if question["carer_id"] != carer_id:
        raise HTTPException(
            status_code=403, detail="Question does not belong to this carer"
        )

    if question["status"] != "sent":
        raise HTTPException(
            status_code=409, detail="Question has already been answered or timed out"
        )

    responded_at_str = response.responded_at.isoformat()

    updated = await update_question_response(
        response.question_id, response.response_text, responded_at_str
    )

    if updated is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "question_id": updated["id"],
        "status": updated["status"],
    }


@router.post("/proactive", status_code=201)
async def submit_proactive_input(
    input_data: ProactiveInput,
    carer_id: int = Depends(get_current_carer),
) -> dict:
    """Submit a proactive input signal.

    Validates visit_id exists, sets location_unavailable flag if coordinates are None,
    and enforces note length (max 500 chars via Pydantic, double-checked here).

    Returns:
        201 with created input record.
    """
    # Validate visit_id exists
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM visits WHERE id = ?", (input_data.visit_id,)
        )
        visit = await cursor.fetchone()

    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")

    # Double-check note length (Pydantic enforces max_length=500, but be defensive)
    if input_data.note is not None and len(input_data.note) > 500:
        raise HTTPException(
            status_code=422, detail="Note must not exceed 500 characters"
        )

    # Set location_unavailable flag if latitude/longitude are None
    location_unavailable = input_data.location_unavailable
    if input_data.latitude is None or input_data.longitude is None:
        location_unavailable = True

    captured_at_str = input_data.captured_at.isoformat()

    # Idempotent: skip if duplicate
    if await _is_duplicate_proactive(
        carer_id, captured_at_str, input_data.input_type
    ):
        # Return the existing record info
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT * FROM proactive_inputs
                   WHERE carer_id = ? AND captured_at = ? AND input_type = ?""",
                (carer_id, captured_at_str, input_data.input_type),
            )
            existing = await cursor.fetchone()
        if existing:
            return {
                "id": existing["id"],
                "visit_id": existing["visit_id"],
                "input_type": existing["input_type"],
                "captured_at": existing["captured_at"],
                "location_unavailable": bool(existing["location_unavailable"]),
            }

    created = await create_proactive_input(
        carer_id=carer_id,
        visit_id=input_data.visit_id,
        input_type=input_data.input_type,
        captured_at=captured_at_str,
        note=input_data.note,
        latitude=input_data.latitude,
        longitude=input_data.longitude,
        location_unavailable=location_unavailable,
    )

    return {
        "id": created["id"],
        "visit_id": created["visit_id"],
        "input_type": created["input_type"],
        "captured_at": created["captured_at"],
        "location_unavailable": bool(created["location_unavailable"]),
    }
