"""Pydantic models for Patient entities."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Priority(str, Enum):
    """Patient priority level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PatientModel(BaseModel):
    """Full patient representation returned from API."""

    id: int
    name: str
    address: str
    lat: float
    lng: float
    preferences: list[str]
    priority: Priority
    continuity_score: float = Field(ge=0, le=100)
    usual_carer_id: Optional[int] = None
    preferred_carer_id: Optional[int] = None


class PatientUpdate(BaseModel):
    """Partial update payload for patient records."""

    name: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    preferences: Optional[list[str]] = None
    priority: Optional[Priority] = None
    usual_carer_id: Optional[int] = None
    preferred_carer_id: Optional[int] = None
