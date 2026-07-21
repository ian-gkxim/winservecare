"""Pydantic models for Exception (optimisation issue) entities."""

from pydantic import BaseModel
from typing import Optional


class ExceptionModel(BaseModel):
    """Full exception representation returned from API."""

    id: int
    timestamp: str
    description: str
    constraint_names: list[str]
    affected_entity_type: str
    affected_entity_id: int
    is_resolved: bool
    resolved_at: Optional[str] = None
