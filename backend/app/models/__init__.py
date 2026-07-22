"""Pydantic data models for the AI Care Operations Optimiser."""

from backend.app.models.carer import CarerModel, CarerUpdate
from backend.app.models.config import ConfigModel, ConfigUpdate
from backend.app.models.constraint import ConstraintModel, ConstraintUpdate
from backend.app.models.contract import (
    CareContractCreate,
    CareContractModel,
    DayOfWeek,
    GenerateVisitsRequest,
    GenerateVisitsResponse,
    VisitFrequency,
    VisitSlotCreate,
    VisitSlotModel,
)
from backend.app.models.exception import ExceptionModel
from backend.app.models.job import (
    ActiveJobInfo,
    JobCreateRequest,
    JobCreateResponse,
    JobNotificationEvent,
    JobProgress,
    JobSummary,
)
from backend.app.models.journey import (
    ActualJourneyCreate,
    ActualJourneyModel,
    ComparisonEntry,
    ComparisonResult,
    DaySummary,
    DeleteConfirmation,
    ErrorResponse,
    FeedbackRating,
    JourneyCreate,
    JourneyFeedbackCreate,
    JourneyFeedbackModel,
    JourneyFilters,
    JourneyModel,
    JourneyPlanModel,
    JourneyStatus,
    JourneyUpdate,
    MatchStatus,
    PaginatedResult,
    PlanCreationReason,
    VarianceModel,
)
from backend.app.models.optimisation import (
    InfeasibilityReason,
    KPIMetrics,
    OptimisationResult,
    RecommendationModel,
    RouteModel,
    RouteStop,
    TravelTimeMatrix,
)
from backend.app.models.patient import PatientModel, PatientUpdate, Priority
from backend.app.models.scenario import ScenarioCreate, ScenarioModel
from backend.app.models.skill import SkillCreate, SkillModel
from backend.app.models.visit import VisitModel

__all__ = [
    # Carer
    "CarerModel",
    "CarerUpdate",
    # Config
    "ConfigModel",
    "ConfigUpdate",
    # Constraint
    "ConstraintModel",
    "ConstraintUpdate",
    # Contract
    "CareContractCreate",
    "CareContractModel",
    "DayOfWeek",
    "GenerateVisitsRequest",
    "GenerateVisitsResponse",
    "VisitFrequency",
    "VisitSlotCreate",
    "VisitSlotModel",
    # Exception
    "ExceptionModel",
    # Job
    "ActiveJobInfo",
    "JobCreateRequest",
    "JobCreateResponse",
    "JobNotificationEvent",
    "JobProgress",
    "JobSummary",
    # Journey
    "ActualJourneyCreate",
    "ActualJourneyModel",
    "ComparisonEntry",
    "ComparisonResult",
    "DaySummary",
    "DeleteConfirmation",
    "ErrorResponse",
    "FeedbackRating",
    "JourneyCreate",
    "JourneyFeedbackCreate",
    "JourneyFeedbackModel",
    "JourneyFilters",
    "JourneyModel",
    "JourneyPlanModel",
    "JourneyStatus",
    "JourneyUpdate",
    "MatchStatus",
    "PaginatedResult",
    "PlanCreationReason",
    "VarianceModel",
    # Optimisation
    "InfeasibilityReason",
    "KPIMetrics",
    "OptimisationResult",
    "RecommendationModel",
    "RouteModel",
    "RouteStop",
    "TravelTimeMatrix",
    # Patient
    "PatientModel",
    "PatientUpdate",
    "Priority",
    # Scenario
    "ScenarioCreate",
    "ScenarioModel",
    # Skill
    "SkillCreate",
    "SkillModel",
    # Visit
    "VisitModel",
]
