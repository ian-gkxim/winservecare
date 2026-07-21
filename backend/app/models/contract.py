"""Pydantic models for Care Contract entities."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import date


class VisitFrequency(str, Enum):
    """Recurrence pattern for a care contract."""

    DAILY = "daily"
    WEEKDAYS_ONLY = "weekdays_only"
    SPECIFIC_DAYS = "specific_days"
    ALTERNATE_DAYS = "alternate_days"
    WEEKLY = "weekly"


class DayOfWeek(str, Enum):
    """Day of week enum for specific_days frequency."""

    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


class VisitSlotModel(BaseModel):
    """Full visit slot representation returned from API."""

    id: int
    contract_id: int
    slot_index: int
    label: str = Field(min_length=1, max_length=100)
    earliest_start: str  # HH:MM
    latest_start: str  # HH:MM
    duration_minutes: int = Field(ge=15, le=120)
    required_skills: list[str] = []


class VisitSlotCreate(BaseModel):
    """Visit slot creation payload."""

    label: str = Field(min_length=1, max_length=100)
    earliest_start: str  # HH:MM, validated 06:00-22:00
    latest_start: str  # HH:MM, must be > earliest_start
    duration_minutes: int = Field(ge=15, le=120)
    required_skills: list[str] = []


class CareContractModel(BaseModel):
    """Full care contract representation returned from API."""

    id: int
    patient_id: int
    visit_frequency: VisitFrequency
    days_of_week: Optional[list[DayOfWeek]] = None
    visits_per_day: int = Field(ge=1, le=4)
    start_date: date
    end_date: Optional[date] = None
    excluded_dates: list[date] = []
    visit_slots: list[VisitSlotModel] = []


class CareContractCreate(BaseModel):
    """Care contract creation/update payload."""

    visit_frequency: VisitFrequency
    days_of_week: Optional[list[DayOfWeek]] = None
    visits_per_day: int = Field(ge=1, le=4)
    start_date: date
    end_date: Optional[date] = None
    excluded_dates: list[date] = []
    visit_slots: list[VisitSlotCreate] = []


class GenerateVisitsRequest(BaseModel):
    """Request payload for visit generation."""

    target_date: date


class GenerateVisitsResponse(BaseModel):
    """Response payload from visit generation."""

    visits: list  # list of VisitModel
    scheduled_count: int
    total_contracts_evaluated: int
    eligible_contracts: int
