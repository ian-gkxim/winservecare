"""Unit tests for the OptimisationEngine.run() orchestrator method."""

import pytest
import pytest_asyncio

from backend.app.models.carer import CarerModel
from backend.app.models.constraint import ConstraintModel
from backend.app.models.optimisation import OptimisationResult, TravelTimeMatrix
from backend.app.models.patient import PatientModel
from backend.app.models.visit import VisitModel
from backend.app.services.optimiser import OptimisationEngine


# --- Test fixtures ---


def _make_carers(n: int = 2) -> list[CarerModel]:
    """Create n carers with different skills."""
    skills_pool = [
        ["personal_care", "medication"],
        ["personal_care", "mobility"],
        ["medication", "mobility", "personal_care"],
    ]
    return [
        CarerModel(
            id=i + 1,
            name=f"Carer {i + 1}",
            home_lat=51.5 + i * 0.01,
            home_lng=-0.1 + i * 0.01,
            skills=skills_pool[i % len(skills_pool)],
            max_working_hours=8.0,
            max_continuous_hours=6.0,
            min_break_minutes=30,
        )
        for i in range(n)
    ]


def _make_visits(n: int = 4) -> list[VisitModel]:
    """Create n visits with varied requirements."""
    return [
        VisitModel(
            id=i + 1,
            patient_id=i + 1,
            duration_minutes=30,
            window_start="08:00",
            window_end="12:00",
            required_skills=["personal_care"],
            preferred_time="09:00",
            is_cancelled=False,
        )
        for i in range(n)
    ]


def _make_patients(n: int = 4) -> list[PatientModel]:
    """Create n patients at different locations."""
    return [
        PatientModel(
            id=i + 1,
            name=f"Patient {i + 1}",
            address=f"{i + 1} Test Street, London",
            lat=51.5 + (i + 2) * 0.01,
            lng=-0.1 + (i + 2) * 0.01,
            preferences=["morning"],
            priority="medium",
            continuity_score=50.0,
            usual_carer_id=1,
            preferred_carer_id=1,
        )
        for i in range(n)
    ]


def _make_travel_matrix(num_carers: int, num_visits: int) -> TravelTimeMatrix:
    """Create a symmetric travel matrix with uniform 10-minute travel times."""
    num_locations = num_carers + num_visits
    locations = [(51.5 + i * 0.01, -0.1 + i * 0.01) for i in range(num_locations)]
    durations = [
        [0 if i == j else 600 for j in range(num_locations)]
        for i in range(num_locations)
    ]
    distances = [
        [0 if i == j else 5000 for j in range(num_locations)]
        for i in range(num_locations)
    ]
    return TravelTimeMatrix(locations=locations, durations=durations, distances=distances)


def _all_constraints_enabled() -> list[ConstraintModel]:
    """Return all 7 hard constraints in enabled state."""
    constraints = [
        ("skill_matching", "Carer must have required skills"),
        ("medication_competency", "Carer must have medication competency"),
        ("time_windows", "Visit must start within time window"),
        ("max_working_hours", "Carer must not exceed maximum hours"),
        ("mandatory_breaks", "Carer must take breaks"),
        ("travel_feasibility", "Travel time must fit between visits"),
        ("no_overlapping_visits", "No two visits may overlap for a carer"),
    ]
    return [
        ConstraintModel(id=i + 1, name=name, description=desc, is_enabled=True)
        for i, (name, desc) in enumerate(constraints)
    ]


# --- Callback helpers ---


class StepCollector:
    """Collects step and progress callbacks for assertions."""

    def __init__(self):
        self.steps: list[dict] = []
        self.progress: list[dict] = []

    async def on_step(self, payload: dict) -> None:
        self.steps.append(payload)

    async def on_progress(self, payload: dict) -> None:
        self.progress.append(payload)


# --- Tests ---


class TestRunOrchestrator:
    """Tests for OptimisationEngine.run()."""

    @pytest.mark.asyncio
    async def test_run_returns_optimisation_result(self):
        """run() returns a valid OptimisationResult."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        result = await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        assert isinstance(result, OptimisationResult)
        assert result.objective_score != 0.0 or len(result.unassigned_visits) > 0

    @pytest.mark.asyncio
    async def test_run_emits_8_animation_steps(self):
        """run() emits exactly 8 animation steps via on_step callback."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        assert len(collector.steps) == 8
        # Verify step numbers are sequential 1-8
        step_numbers = [s["stepNumber"] for s in collector.steps]
        assert step_numbers == [1, 2, 3, 4, 5, 6, 7, 8]

    @pytest.mark.asyncio
    async def test_run_emits_8_progress_updates(self):
        """run() emits exactly 8 progress updates via on_progress callback."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        assert len(collector.progress) == 8
        progress_steps = [p["step"] for p in collector.progress]
        assert progress_steps == [1, 2, 3, 4, 5, 6, 7, 8]

    @pytest.mark.asyncio
    async def test_step_names_match_spec(self):
        """Each step has the correct name per the specification."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        expected_names = [
            "Locations plotted",
            "Matrix retrieved",
            "Feasible assignments",
            "Constraint pruning",
            "Route evaluation",
            "Improvement iterations",
            "Winning solution",
            "Route animation",
        ]
        actual_names = [s["stepName"] for s in collector.steps]
        assert actual_names == expected_names

    @pytest.mark.asyncio
    async def test_step_data_types_match_spec(self):
        """Each step's data has the correct 'type' field."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        expected_types = [
            "locations",
            "matrix",
            "assignments",
            "pruning",
            "evaluation",
            "improvement",
            "solution",
            "animation",
        ]
        actual_types = [s["data"]["type"] for s in collector.steps]
        assert actual_types == expected_types

    @pytest.mark.asyncio
    async def test_step1_contains_carer_and_patient_data(self):
        """Step 1 (Locations plotted) includes carer and patient markers."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        step1_data = collector.steps[0]["data"]
        assert len(step1_data["carers"]) == 2
        assert len(step1_data["patients"]) == 4
        # Verify carer marker has id, name, lat, lng
        carer_marker = step1_data["carers"][0]
        assert "id" in carer_marker
        assert "name" in carer_marker
        assert "lat" in carer_marker
        assert "lng" in carer_marker

    @pytest.mark.asyncio
    async def test_step2_has_pair_count(self):
        """Step 2 (Matrix retrieved) includes the pair count."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        step2_data = collector.steps[1]["data"]
        # 6 locations (2 carers + 4 visits) => 36 pairs
        assert step2_data["pairCount"] == 36

    @pytest.mark.asyncio
    async def test_step3_has_all_assignment_edges(self):
        """Step 3 (Feasible assignments) includes all carer-visit pairs."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        step3_data = collector.steps[2]["data"]
        # 2 carers * 4 visits = 8 edges
        assert len(step3_data["edges"]) == 8

    @pytest.mark.asyncio
    async def test_result_has_routes_when_solution_found(self):
        """When a solution is found, the result contains routes."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        result = await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        assert len(result.routes) > 0
        # All assigned visits should appear in routes
        assigned_visit_ids = set()
        for route in result.routes:
            for stop in route.stops:
                assigned_visit_ids.add(stop.visit_id)
        # Total assigned + unassigned should equal total visits
        assert len(assigned_visit_ids) + len(result.unassigned_visits) == 4

    @pytest.mark.asyncio
    async def test_result_kpis_populated(self):
        """The result includes populated KPI metrics."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        result = await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        assert result.kpis.total_visits == 4
        assert result.kpis.carers_available == 2
        assert result.kpis.travel_hours >= 0.0
        assert result.kpis.mileage >= 0.0

    @pytest.mark.asyncio
    async def test_progress_includes_score_after_solver(self):
        """Progress updates after step 5 include a non-zero score when routes exist."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        result = await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        if result.routes:
            # Steps 5-8 should have a score
            for p in collector.progress[4:]:
                assert "score" in p
                assert p["score"] != 0.0

    @pytest.mark.asyncio
    async def test_progress_has_name_field(self):
        """All progress updates include 'name' and 'step' fields."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        patients = _make_patients(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        collector = StepCollector()

        await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=matrix,
            on_step=collector.on_step,
            on_progress=collector.on_progress,
        )

        for p in collector.progress:
            assert "step" in p
            assert "name" in p
            assert "score" in p
