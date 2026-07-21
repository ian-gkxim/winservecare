"""Pydantic models for Constraint entities."""

from pydantic import BaseModel


class ConstraintModel(BaseModel):
    """Full constraint representation returned from API."""

    id: int
    name: str
    description: str
    is_enabled: bool


class ConstraintUpdate(BaseModel):
    """Payload for enabling/disabling a constraint."""

    is_enabled: bool
