"""Pydantic models for the Carer Mobile App domain."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


# Signal models


class GPSSignal(BaseModel):
    """A single GPS location report from a carer's device."""

    latitude: float
    longitude: float
    accuracy_metres: float
    low_accuracy: bool = False
    captured_at: datetime  # UTC from device


class GPSBatch(BaseModel):
    """A batch of GPS signals for efficient transmission."""

    signals: list[GPSSignal] = Field(max_length=50)  # Max 50 signals per batch


class QuestionResponse(BaseModel):
    """A carer's response to a contextual question."""

    question_id: int
    response_text: str
    responded_at: datetime  # UTC from device


class ProactiveInput(BaseModel):
    """A voluntary status report initiated by the carer."""

    visit_id: int
    input_type: Literal[
        "arrived",
        "visit_started",
        "visit_completed",
        "running_late",
        "issue_encountered",
        "cannot_complete",
    ]
    note: Optional[str] = Field(None, max_length=500)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_unavailable: bool = False
    captured_at: datetime  # UTC from device


# Visit status models


class VisitStatus(str, Enum):
    """Valid visit status values for the lifecycle state machine."""

    PENDING = "pending"
    TRAVELLING = "travelling"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    MISSED = "missed"
    CANCELLED = "cancelled"


VALID_TRANSITIONS: dict[VisitStatus, set[VisitStatus]] = {
    VisitStatus.PENDING: {
        VisitStatus.TRAVELLING,
        VisitStatus.DELAYED,
        VisitStatus.MISSED,
        VisitStatus.CANCELLED,
    },
    VisitStatus.TRAVELLING: {
        VisitStatus.ARRIVED,
        VisitStatus.DELAYED,
        VisitStatus.CANCELLED,
    },
    VisitStatus.ARRIVED: {VisitStatus.IN_PROGRESS, VisitStatus.CANCELLED},
    VisitStatus.IN_PROGRESS: {VisitStatus.COMPLETED, VisitStatus.CANCELLED},
    VisitStatus.DELAYED: {VisitStatus.TRAVELLING, VisitStatus.MISSED, VisitStatus.CANCELLED},
    VisitStatus.COMPLETED: set(),
    VisitStatus.MISSED: set(),
    VisitStatus.CANCELLED: set(),
}


class VisitStatusResponse(BaseModel):
    """Current visit status with confidence score."""

    visit_id: int
    status: VisitStatus
    confidence_score: int = Field(ge=0, le=100)
    last_updated: datetime


# Auth models


class LoginRequest(BaseModel):
    """Carer login credentials."""

    identifier: str
    password: str


class TokenResponse(BaseModel):
    """JWT token pair returned on successful authentication."""

    access_token: str
    refresh_token: str
    expires_in: int  # seconds


class DeviceTokenRequest(BaseModel):
    """Push notification device token registration."""

    device_token: str
    platform: Literal["ios", "android"]


# Schedule models


class MobileVisitSummary(BaseModel):
    """Summary visit information for the schedule list view."""

    id: int
    patient_name: str
    patient_address: str
    patient_lat: float
    patient_lng: float
    window_start: str
    window_end: str
    duration_minutes: int
    required_skills: list[str]
    status: VisitStatus
    confidence_score: int = Field(ge=0, le=100)


class MobileVisitDetail(MobileVisitSummary):
    """Full visit details including patient preferences."""

    patient_preferences: list[str]


# Question models


class ContextualQuestionPayload(BaseModel):
    """Question payload sent to the carer's mobile app."""

    id: int
    visit_id: int
    question_text: str
    question_type: Literal["yes_no", "single_choice", "free_text"]
    options: Optional[list[str]] = None
