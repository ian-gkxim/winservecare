"""Mobile questions API endpoints for the Carer Mobile App.

Provides endpoints for retrieving pending questions and reporting timeouts.
All endpoints are protected and require JWT auth.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from backend.app.db.mobile_repository import (
    get_pending_questions_for_carer,
    update_question_timeout,
)
from backend.app.db.database import get_db
from backend.app.routes.mobile_auth import get_current_carer

router = APIRouter(prefix="/api/mobile/questions", tags=["mobile-questions"])


@router.get("/pending")
async def get_pending_questions(
    carer_id: int = Depends(get_current_carer),
) -> list[dict]:
    """Get all pending (sent) questions for the authenticated carer.

    Returns questions with status='sent' ordered by sent_at ascending.

    Returns:
        List of pending question objects.
    """
    questions = await get_pending_questions_for_carer(carer_id)
    return [
        {
            "id": q["id"],
            "visit_id": q["visit_id"],
            "question_text": q["question_text"],
            "question_type": q["question_type"],
            "options": q.get("options"),
            "sent_at": q["sent_at"],
        }
        for q in questions
    ]


@router.post("/{question_id}/timeout", status_code=200)
async def timeout_question(
    question_id: int,
    carer_id: int = Depends(get_current_carer),
) -> dict:
    """Mark a question as timed out.

    Validates that the question exists, belongs to the authenticated carer,
    and is currently in 'sent' status before marking it as timed_out.

    Args:
        question_id: The question identifier from the URL path.

    Returns:
        Updated question status.

    Raises:
        404: Question not found.
        403: Question does not belong to this carer.
        409: Question is not in 'sent' status.
    """
    # Validate the question exists and belongs to this carer
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, carer_id, status FROM contextual_questions WHERE id = ?",
            (question_id,),
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
            status_code=409,
            detail="Question has already been answered or timed out",
        )

    timed_out_at = datetime.now(timezone.utc).isoformat()
    updated = await update_question_timeout(question_id, timed_out_at)

    if updated is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "question_id": updated["id"],
        "status": updated["status"],
        "timed_out_at": updated["timed_out_at"],
    }
