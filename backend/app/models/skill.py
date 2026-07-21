"""Pydantic models for Skill entities."""

from pydantic import BaseModel, Field


class SkillModel(BaseModel):
    """Full skill representation returned from API."""

    id: int
    name: str


class SkillCreate(BaseModel):
    """Payload for creating a new skill."""

    name: str = Field(min_length=1, max_length=100)
