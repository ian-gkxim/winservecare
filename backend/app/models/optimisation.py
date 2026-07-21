"""Pydantic models for optimisation engine inputs and outputs."""

from pydantic import BaseModel, Field


class TravelTimeMatrix(BaseModel):
    """Matrix of travel durations and distances between location pairs."""

    locations: list[tuple[float, float]]  # (lat, lng) ordered list
    durations: list[list[int]]  # seconds between location[i] and location[j]
    distances: list[list[int]]  # metres between location[i] and location[j]


class RouteStop(BaseModel):
    """A single stop within a carer's route."""

    visit_id: int
    patient_id: int
    arrival_time: str
    start_time: str
    end_time: str
    travel_time_from_prev: int  # minutes
    mileage_from_prev: float


class RouteModel(BaseModel):
    """A complete route for a single carer."""

    carer_id: int
    stops: list[RouteStop]
    total_travel_minutes: int
    total_mileage: float
    total_cost: float


class InfeasibilityReason(BaseModel):
    """Explanation for why a visit could not be assigned."""

    visit_id: int
    carer_ids: list[int]
    constraint_name: str
    reason: str


class KPIMetrics(BaseModel):
    """Key performance indicators for an optimisation result."""

    total_visits: int
    carers_available: int
    travel_hours: float
    mileage: float
    overtime: float
    continuity_score: float


class RecommendationModel(BaseModel):
    """A recommendation or warning generated from optimisation analysis."""

    type: str  # "recommendation" | "warning"
    title: str
    description: str = Field(max_length=200)
    impact: float


class OptimisationResult(BaseModel):
    """Complete output from an optimisation run."""

    routes: list[RouteModel]
    objective_score: float
    kpis: KPIMetrics
    recommendations: list[RecommendationModel]
    unassigned_visits: list[int]
    infeasibility_reasons: list[InfeasibilityReason]
