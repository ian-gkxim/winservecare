"""Pydantic models for Scenario entities."""

from pydantic import BaseModel, Field

from backend.app.models.optimisation import RouteModel


class ScenarioCreate(BaseModel):
    """Payload for saving an optimisation result as a named scenario."""

    name: str = Field(min_length=1, max_length=100)
    total_travel_hours: float = 0.0
    total_mileage: float = 0.0
    total_overtime_hours: float = 0.0
    continuity_score: float = 0.0
    objective_score: float = 0.0
    assignments: list[dict] = Field(default_factory=list)
    routes: list[dict] = Field(default_factory=list)


class ScenarioModel(BaseModel):
    """Full scenario representation returned from API."""

    id: int
    name: str
    total_travel_hours: float
    total_mileage: float
    total_overtime_hours: float
    continuity_score: float
    objective_score: float
    assignments: list[dict]
    routes: list[RouteModel]
    created_at: str
