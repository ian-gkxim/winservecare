"""Unit tests for background re-optimisation triggered by visit cancellation."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.models.carer import CarerModel
from backend.app.models.constraint import ConstraintModel
from backend.app.models.optimisation import (
    KPIMetrics,
    OptimisationResult,
    RouteModel,
    RouteStop,
    TravelTimeMatrix,
)
from backend.app.models.patient import PatientModel
from backend.app.models.visit import VisitModel
from backend.app.routes.visits import _trigger_reoptimisation


@pytest.fixture
def sample_carers():
    return [
        CarerModel(
            id=1, name="Alice", home_lat=51.5, home_lng=-0.1,
            skills=["personal_care"], max_working_hours=8.0,
            max_continuous_hours=4.0, min_break_minutes=30,
        ),
    ]


@pytest.fixture
def sample_patients():
    return [
        PatientModel(
            id=1, name="Bob", address="123 St", lat=51.51, lng=-0.09,
            preferences=[], priority="medium", continuity_score=80.0,
            usual_carer_id=1, preferred_carer_id=1,
        ),
    ]


@pytest.fixture
def sample_visits():
    return [
        VisitModel(
            id=1, patient_id=1, duration_minutes=30,
            window_start="09:00", window_end="12:00",
            required_skills=["personal_care"], preferred_time="09:30",
            is_cancelled=False,
        ),
        VisitModel(
            id=2, patient_id=1, duration_minutes=30,
            window_start="14:00", window_end="16:00",
            required_skills=[], preferred_time="14:00",
            is_cancelled=True,
        ),
    ]


@pytest.fixture
def sample_constraints():
    return [
        ConstraintModel(id=1, name="skill_matching", description="Match skills", is_enabled=True),
    ]


@pytest.fixture
def sample_result():
    route = RouteModel(
        carer_id=1,
        stops=[
            RouteStop(
                visit_id=1, patient_id=1,
                arrival_time="09:20", start_time="09:30", end_time="10:00",
                travel_time_from_prev=10, mileage_from_prev=3.5,
            ),
        ],
        total_travel_minutes=10,
        total_mileage=3.5,
        total_cost=5.0,
    )
    return OptimisationResult(
        routes=[route],
        objective_score=42.0,
        kpis=KPIMetrics(
            total_visits=1, carers_available=1,
            travel_hours=0.2, mileage=3.5, overtime=0.0, continuity_score=100.0,
        ),
        recommendations=[],
        unassigned_visits=[],
        infeasibility_reasons=[],
    )


@pytest.mark.asyncio
@patch("backend.app.routes.visits.create_scenario")
@patch("backend.app.routes.visits.OptimisationEngine")
@patch("backend.app.routes.visits.GoogleMapsClient")
@patch("backend.app.routes.visits.get_constraints")
@patch("backend.app.routes.visits.get_visits")
@patch("backend.app.routes.visits.get_patients")
@patch("backend.app.routes.visits.get_carers")
async def test_trigger_reoptimisation_runs_solver_and_saves_scenario(
    mock_get_carers,
    mock_get_patients,
    mock_get_visits,
    mock_get_constraints,
    mock_maps_class,
    mock_engine_class,
    mock_create_scenario,
    sample_carers,
    sample_patients,
    sample_visits,
    sample_constraints,
    sample_result,
):
    """Re-optimisation fetches data, runs solver, and saves a scenario."""
    mock_get_carers.return_value = sample_carers
    mock_get_patients.return_value = sample_patients
    mock_get_visits.return_value = sample_visits
    mock_get_constraints.return_value = sample_constraints

    # Mock maps client
    mock_maps_instance = AsyncMock()
    mock_maps_instance.get_distance_matrix.return_value = TravelTimeMatrix(
        locations=[(51.5, -0.1), (51.51, -0.09)],
        durations=[[0, 600], [600, 0]],
        distances=[[0, 5000], [5000, 0]],
    )
    mock_maps_class.return_value = mock_maps_instance

    # Mock engine
    mock_engine_instance = AsyncMock()
    mock_engine_instance.run.return_value = sample_result
    mock_engine_class.return_value = mock_engine_instance

    mock_create_scenario.return_value = MagicMock()

    await _trigger_reoptimisation()

    # Should only pass non-cancelled visits to the engine
    engine_call_kwargs = mock_engine_instance.run.call_args[1]
    visits_passed = engine_call_kwargs["visits"]
    assert len(visits_passed) == 1
    assert visits_passed[0].id == 1
    assert not visits_passed[0].is_cancelled

    # Should save a scenario with the correct KPIs
    mock_create_scenario.assert_called_once()
    call_kwargs = mock_create_scenario.call_args[1]
    assert call_kwargs["total_travel_hours"] == 0.2
    assert call_kwargs["total_mileage"] == 3.5
    assert call_kwargs["objective_score"] == 42.0
    assert "Auto-reoptimisation" in call_kwargs["name"]


@pytest.mark.asyncio
@patch("backend.app.routes.visits.get_visits")
@patch("backend.app.routes.visits.get_patients")
@patch("backend.app.routes.visits.get_carers")
async def test_trigger_reoptimisation_skips_when_no_active_visits(
    mock_get_carers, mock_get_patients, mock_get_visits,
):
    """Re-optimisation skips gracefully when all visits are cancelled."""
    mock_get_carers.return_value = [
        CarerModel(
            id=1, name="Alice", home_lat=51.5, home_lng=-0.1,
            skills=[], max_working_hours=8.0,
            max_continuous_hours=4.0, min_break_minutes=30,
        ),
    ]
    mock_get_patients.return_value = []
    mock_get_visits.return_value = [
        VisitModel(
            id=1, patient_id=1, duration_minutes=30,
            window_start="09:00", window_end="12:00",
            required_skills=[], preferred_time=None,
            is_cancelled=True,
        ),
    ]

    # Should not raise — just returns early
    await _trigger_reoptimisation()


@pytest.mark.asyncio
@patch("backend.app.routes.visits.GoogleMapsClient")
@patch("backend.app.routes.visits.get_constraints")
@patch("backend.app.routes.visits.get_visits")
@patch("backend.app.routes.visits.get_patients")
@patch("backend.app.routes.visits.get_carers")
async def test_trigger_reoptimisation_handles_maps_api_error(
    mock_get_carers,
    mock_get_patients,
    mock_get_visits,
    mock_get_constraints,
    mock_maps_class,
    sample_carers,
    sample_patients,
    sample_visits,
    sample_constraints,
):
    """Re-optimisation logs and returns if Maps API fails — no crash."""
    from backend.app.services.maps_client import MapsAPIError

    mock_get_carers.return_value = sample_carers
    mock_get_patients.return_value = sample_patients
    mock_get_visits.return_value = sample_visits
    mock_get_constraints.return_value = sample_constraints

    mock_maps_instance = AsyncMock()
    mock_maps_instance.get_distance_matrix.side_effect = MapsAPIError("API key invalid")
    mock_maps_class.return_value = mock_maps_instance

    # Should not raise
    await _trigger_reoptimisation()
