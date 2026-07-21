"""Pydantic models for Carer entities."""

from pydantic import BaseModel, Field
from typing import Optional


class CarerModel(BaseModel):
    """Full carer representation returned from API."""

    id: int
    name: str
    home_lat: float
    home_lng: float
    skills: list[str]
    max_working_hours: float = Field(ge=1, le=24)
    max_continuous_hours: float = Field(default=6.0)
    min_break_minutes: int = Field(default=30)


class CarerUpdate(BaseModel):
    """Partial update payload for carer records."""

    name: Optional[str] = None
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None
    skills: Optional[list[str]] = None
    max_working_hours: Optional[float] = Field(default=None, ge=1, le=24)
    max_continuous_hours: Optional[float] = None
    min_break_minutes: Optional[int] = None
