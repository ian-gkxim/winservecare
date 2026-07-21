"""Mobile schedule and visit status API endpoints.

Provides authenticated carers with access to their daily schedule
and current visit status information.
"""

import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from backend.app.db import mobile_repository
from backend.app.db.database import get_db
from backend.app.models.mobile import (
    MobileVisitDetail,
    MobileVisitSummary,
    VisitStatus,
    VisitStatusResponse,
)

router = APIRouter(prefix="/api/mobile", tags=["mobile-schedule"])


# --- Temporary auth dependency ---
# This will be replaced by the proper get_current_carer from auth_service
# once task 2.1 is complete. For now, extract carer_id from a header.

from fastapi import Header


async def get_current_carer(x_carer_id: int = Header(...)) -> int:
    """Temporary auth dependency that extracts carer_id from X-Carer-Id header.

    This will be replaced by JWT-based authentication once auth_service is implemented.
    """
    return x_carer_id


# --- Schedule endpoints ---


@router.get("/schedule", response_model=list[MobileVisitSummary])
async def get_schedule(
    carer_id: int = Depends(get_current_carer),
) -> list[MobileVisitSummary]:
    """Get today's visits for the authenticated carer.

    Returns visits sorted chronologically by window_start.
    Returns an empty list if no visits are scheduled for today.
    """
    today = date.today().isoformat()
    visits = await mobile_repository.get_carer_schedule_for_today(carer_id, today)

    return [
        MobileVisitSummary(
            id=v["visit_id"],
            patient_name=v["patient_name"],
            patient_address=v["patient_address"],
            patient_lat=v["patient_lat"],
            patient_lng=v["patient_lng"],
            window_start=v["window_start"],
            window_end=v["window_end"],
            duration_minutes=v["duration_minutes"],
            required_skills=v["required_skills"],
            status=VisitStatus(v["status"]),
            confidence_score=v["confidence_score"],
        )
        for v in visits
    ]


@router.get("/schedule/{visit_id}", response_model=MobileVisitDetail)
async def get_visit_detail(
    visit_id: int,
    carer_id: int = Depends(get_current_carer),
) -> MobileVisitDetail:
    """Get full details for a specific visit including patient preferences.

    Returns 404 if the visit is not found or not assigned to this carer.
    """
    today = date.today().isoformat()
    visits = await mobile_repository.get_carer_schedule_for_today(carer_id, today)

    # Find the specific visit in the carer's schedule
    visit = next((v for v in visits if v["visit_id"] == visit_id), None)
    if visit is None:
        raise HTTPException(
            status_code=404,
            detail=f"Visit {visit_id} not found or not assigned to this carer",
        )

    # Fetch patient preferences from the database
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT p.preferences
               FROM visits v
               INNER JOIN patients p ON v.patient_id = p.id
               WHERE v.id = ?""",
            (visit_id,),
        )
        row = await cursor.fetchone()
        preferences = json.loads(row["preferences"]) if row else []

    return MobileVisitDetail(
        id=visit["visit_id"],
        patient_name=visit["patient_name"],
        patient_address=visit["patient_address"],
        patient_lat=visit["patient_lat"],
        patient_lng=visit["patient_lng"],
        window_start=visit["window_start"],
        window_end=visit["window_end"],
        duration_minutes=visit["duration_minutes"],
        required_skills=visit["required_skills"],
        status=VisitStatus(visit["status"]),
        confidence_score=visit["confidence_score"],
        patient_preferences=preferences,
    )


@router.get("/visits/{visit_id}/status", response_model=VisitStatusResponse)
async def get_visit_status(
    visit_id: int,
    carer_id: int = Depends(get_current_carer),
) -> VisitStatusResponse:
    """Get the current status and confidence score for a visit.

    Returns a default status (pending, confidence 0) if no status record exists.
    """
    status_record = await mobile_repository.get_current_status_for_visit(visit_id)

    if status_record is None:
        return VisitStatusResponse(
            visit_id=visit_id,
            status=VisitStatus.PENDING,
            confidence_score=0,
            last_updated=datetime.now(timezone.utc),
        )

    return VisitStatusResponse(
        visit_id=visit_id,
        status=VisitStatus(status_record["status"]),
        confidence_score=status_record["confidence_score"],
        last_updated=datetime.fromisoformat(status_record["created_at"]),
    )
