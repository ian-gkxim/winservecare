"""Journey Lifecycle Management API endpoints."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.app.models.journey import (
    ActualJourneyCreate,
    ActualJourneyModel,
    ComparisonResult,
    DaySummary,
    DeleteConfirmation,
    JourneyCreate,
    JourneyFilters,
    JourneyModel,
    JourneyPlanModel,
    JourneyStatus,
    JourneyUpdate,
    PaginatedResult,
    PlanCreationReason,
)
from backend.app.services.journey_service import JourneyService

router = APIRouter(tags=["journeys"])

service = JourneyService()


# --- Journey Plan CRUD routes (Task 9.1) ---


from pydantic import BaseModel
from typing import Optional


class JourneyPlanCreateRequest(BaseModel):
    """Request body for creating a journey plan."""

    operating_day: date
    journeys: list[JourneyCreate]
    reason: PlanCreationReason = PlanCreationReason.INITIAL_CREATION


@router.post("/api/journey-plans", response_model=JourneyPlanModel, status_code=201)
async def create_journey_plan(data: JourneyPlanCreateRequest) -> JourneyPlanModel:
    """Create a new journey plan for a specified operating day."""
    try:
        return await service.create_plan(
            operating_day=data.operating_day,
            journeys=data.journeys,
            reason=data.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/api/journey-plans", response_model=list[JourneyPlanModel])
async def list_journey_plans(
    operating_day: Optional[str] = Query(None, description="Filter by operating day (YYYY-MM-DD)"),
    include_archived: bool = Query(False, description="Include archived plans"),
) -> list[JourneyPlanModel]:
    """List journey plans with optional filters (without nested journeys for list view)."""
    from backend.app.db import journey_repository as repo

    plans = await repo.list_journey_plans(
        operating_day=operating_day,
        include_archived=include_archived,
    )

    return [
        JourneyPlanModel(
            id=plan["id"],
            operating_day=plan["operating_day"],
            plan_version=plan["plan_version"],
            creation_reason=PlanCreationReason(plan["creation_reason"]),
            is_archived=bool(plan["is_archived"]),
            archived_at=plan.get("archived_at"),
            created_at=plan["created_at"],
            journeys=[],  # List view omits nested journeys for performance
        )
        for plan in plans
    ]


@router.get("/api/journey-plans/{plan_id}", response_model=JourneyPlanModel)
async def get_journey_plan(plan_id: int) -> JourneyPlanModel:
    """Get a specific journey plan with its journeys."""
    from backend.app.db import journey_repository as repo
    from backend.app.services.journey_service import _row_to_journey_model

    plan = await repo.get_journey_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Journey plan not found")

    journeys = await repo.get_journeys_by_plan(plan_id)
    journey_models = [_row_to_journey_model(j) for j in journeys]

    return JourneyPlanModel(
        id=plan["id"],
        operating_day=plan["operating_day"],
        plan_version=plan["plan_version"],
        creation_reason=PlanCreationReason(plan["creation_reason"]),
        is_archived=bool(plan["is_archived"]),
        archived_at=plan.get("archived_at"),
        created_at=plan["created_at"],
        journeys=journey_models,
    )


@router.delete("/api/journey-plans/{plan_id}", response_model=DeleteConfirmation)
async def delete_journey_plan(plan_id: int) -> DeleteConfirmation:
    """Delete (archive) a journey plan."""
    return await service.delete_plan(plan_id)


# --- Journey modification and cancellation routes (Task 9.2) ---


@router.put(
    "/api/journey-plans/{plan_id}/journeys/{journey_id}",
    response_model=JourneyPlanModel,
)
async def modify_journey(
    plan_id: int, journey_id: int, update: JourneyUpdate
) -> JourneyPlanModel:
    """Modify a journey within a plan, creating a new plan version."""
    return await service.modify_journey(plan_id, journey_id, update)


@router.post("/api/journeys/{journey_id}/cancel", response_model=JourneyModel)
async def cancel_journey(journey_id: int) -> JourneyModel:
    """Cancel a journey, creating a new plan version."""
    return await service.cancel_journey(journey_id)


# --- Actual journey, comparison, history, and query routes (Task 9.3) ---


@router.post("/api/actual-journeys", response_model=ActualJourneyModel, status_code=201)
async def receive_actual_journey(data: ActualJourneyCreate) -> ActualJourneyModel:
    """Receive actual journey data from the field."""
    return await service.receive_actual(data)


@router.get(
    "/api/journey-comparison/{operating_day}", response_model=ComparisonResult
)
async def get_journey_comparison(
    operating_day: str,
    plan_version: Optional[int] = Query(None, description="Specific plan version to compare"),
) -> ComparisonResult:
    """Compare planned journeys with actuals for an operating day."""
    try:
        parsed_date = date.fromisoformat(operating_day)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid operating_day format: '{operating_day}'. Expected YYYY-MM-DD.",
        )

    return await service.get_comparison(parsed_date, plan_version)


@router.get(
    "/api/journey-history/{operating_day}",
    response_model=list[JourneyPlanModel],
)
async def get_journey_history(operating_day: str) -> list[JourneyPlanModel]:
    """Get all plan versions for an operating day in chronological order."""
    try:
        parsed_date = date.fromisoformat(operating_day)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid operating_day format: '{operating_day}'. Expected YYYY-MM-DD.",
        )

    return await service.get_history(parsed_date)


@router.get("/api/journey-history", response_model=list[DaySummary])
async def get_journey_history_range(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
) -> list[DaySummary]:
    """Get summary stats for each day in a date range."""
    try:
        start_date = date.fromisoformat(start)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid start date format: '{start}'. Expected YYYY-MM-DD.",
        )

    try:
        end_date = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid end date format: '{end}'. Expected YYYY-MM-DD.",
        )

    return await service.get_date_range_summary(start_date, end_date)


@router.get("/api/journeys", response_model=PaginatedResult)
async def query_journeys(
    operating_day: Optional[str] = Query(None, description="Filter by operating day (YYYY-MM-DD)"),
    carer_id: Optional[int] = Query(None, description="Filter by carer ID"),
    status: Optional[str] = Query(None, description="Filter by journey status"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
) -> PaginatedResult:
    """Query journeys with filters and pagination."""
    # Parse operating_day if provided
    parsed_operating_day: Optional[date] = None
    if operating_day is not None:
        try:
            parsed_operating_day = date.fromisoformat(operating_day)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid operating_day format: '{operating_day}'. Expected YYYY-MM-DD.",
            )

    # Parse status if provided
    parsed_status: Optional[JourneyStatus] = None
    if status is not None:
        try:
            parsed_status = JourneyStatus(status)
        except ValueError:
            valid_statuses = [s.value for s in JourneyStatus]
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status filter: '{status}'. Must be one of: {sorted(valid_statuses)}.",
            )

    filters = JourneyFilters(
        operating_day=parsed_operating_day,
        carer_id=carer_id,
        status=parsed_status,
    )

    return await service.query_journeys(filters, page, page_size)
