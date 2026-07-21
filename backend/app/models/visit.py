"""Pydantic models for Visit entities."""

from pydantic import BaseModel, Field
from typing import Optional


class VisitModel(BaseModel):
    """Full visit representation returned from API."""

    id: int
    patient_id: int
    duration_minutes: int = Field(ge=15, le=120)
    window_start: str  # HH:MM
    window_end: str  # HH:MM
    required_skills: list[str]
    preferred_time: Optional[str] = None
    is_cancelled: bool = False
    target_date: Optional[str] = None  # YYYY-MM-DD
    contract_id: Optional[int] = None
