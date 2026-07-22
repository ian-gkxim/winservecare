"""Pydantic models for Journey Lifecycle Management entities."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JourneyStatus(str, Enum):
    """Lifecycle state of a Journey."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    AMENDED = "amended"
    OVERDUE = "overdue"


class PlanCreationReason(str, Enum):
    """Reason for creating a new Plan_Version."""

    INITIAL_CREATION = "initial_creation"
    MANUAL_AMENDMENT = "manual_amendment"
    RE_OPTIMISATION = "re_optimisation"


class MatchStatus(str, Enum):
    """Match status between planned and actual journeys."""

    MATCHED = "matched"
    UNMATCHED = "unmatched"
    UNSTARTED = "unstarted"
    UNPLANNED = "unplanned"


class JourneyCreate(BaseModel):
    """Payload for creating a single Journey within a plan."""

    carer_id: int
    visit_id: Optional[int] = None
    origin_lat: float
    origin_lng: float
    origin_label: Optional[str] = None
    destination_lat: float
    destination_lng: float
    destination_label: Optional[str] = None
    planned_departure: datetime
    planned_arrival: datetime
    planned_distance_miles: float


class JourneyUpdate(BaseModel):
    """Payload for modifying an existing Journey."""

    carer_id: Optional[int] = None
    planned_departure: Optional[datetime] = None
    planned_arrival: Optional[datetime] = None
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None


class JourneyModel(BaseModel):
    """Full Journey representation returned from API."""

    id: int
    plan_id: int
    carer_id: int
    visit_id: Optional[int] = None
    origin_lat: float
    origin_lng: float
    origin_label: Optional[str] = None
    destination_lat: float
    destination_lng: float
    destination_label: Optional[str] = None
    planned_departure: str
    planned_arrival: str
    planned_distance_miles: float
    status: JourneyStatus
    cancelled_at: Optional[str] = None
    created_at: str
    updated_at: str


class JourneyPlanModel(BaseModel):
    """Full Journey_Plan representation including nested Journeys."""

    id: int
    operating_day: str
    plan_version: int
    creation_reason: PlanCreationReason
    is_archived: bool
    archived_at: Optional[str] = None
    created_at: str
    journeys: list[JourneyModel] = []


class ActualJourneyCreate(BaseModel):
    """Payload for receiving actual journey data from the field."""

    carer_id: int
    operating_day: date
    actual_departure: datetime
    actual_arrival: datetime
    actual_distance_miles: float = Field(ge=0)
    route_coordinates: list[list[float]] = Field(default_factory=list, max_length=1000)


class ActualJourneyModel(BaseModel):
    """Full Actual_Journey representation returned from API."""

    id: int
    journey_id: Optional[int] = None
    carer_id: int
    operating_day: str
    actual_departure: str
    actual_arrival: str
    actual_distance_miles: float
    route_coordinates: list[list[float]]
    match_status: MatchStatus
    created_at: str


class VarianceModel(BaseModel):
    """Calculated variance between planned and actual journey data."""

    departure_variance_minutes: Optional[int] = None  # positive = late
    arrival_variance_minutes: Optional[int] = None  # positive = late
    distance_variance_miles: Optional[float] = None  # positive = longer


class ComparisonEntry(BaseModel):
    """A single entry in a plan-vs-actual comparison."""

    planned_journey: Optional[JourneyModel] = None
    actual_journey: Optional[ActualJourneyModel] = None
    variance: Optional[VarianceModel] = None
    match_status: MatchStatus


class ComparisonResult(BaseModel):
    """Complete comparison result for an Operating_Day."""

    operating_day: str
    plan_version: int
    entries_by_carer: dict[int, list[ComparisonEntry]]  # carer_id -> entries
    message: Optional[str] = None


class DaySummary(BaseModel):
    """Summary record for a single Operating_Day in a date range query."""

    operating_day: str
    plan_version_count: int
    total_planned_journeys: int
    total_completed_journeys: int
    avg_departure_variance_minutes: Optional[float] = None
    avg_distance_variance_miles: Optional[float] = None


class JourneyFilters(BaseModel):
    """Filter criteria for querying journeys."""

    operating_day: Optional[date] = None
    carer_id: Optional[int] = None
    status: Optional[JourneyStatus] = None


class PaginatedResult(BaseModel):
    """Paginated query result wrapper."""

    total_count: int
    page: int
    page_size: int
    journeys: list[JourneyModel]


class DeleteConfirmation(BaseModel):
    """Confirmation response for plan deletion."""

    plan_id: int
    journeys_removed: int


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str  # Machine-readable error code
    message: str  # Human-readable description
    details: dict = {}  # Additional context


class FeedbackRating(str, Enum):
    """Route quality feedback rating."""

    THUMBS_UP = "thumbs_up"
    NEUTRAL = "neutral"
    THUMBS_DOWN = "thumbs_down"


class JourneyFeedbackCreate(BaseModel):
    """Payload for submitting route feedback."""

    journey_id: int
    carer_id: int
    rating: FeedbackRating
    comment: Optional[str] = Field(None, max_length=300)
    submitted_at: datetime


class JourneyFeedbackModel(BaseModel):
    """Full feedback record returned from API."""

    id: int
    journey_id: int
    carer_id: int
    rating: FeedbackRating
    comment: Optional[str] = None
    submitted_at: str
    created_at: str
