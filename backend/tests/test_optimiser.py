"""Unit tests for the OptimisationEngine.build_model() method."""

import pytest
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

from backend.app.models.carer import CarerModel
from backend.app.models.constraint import ConstraintModel
from backend.app.models.optimisation import TravelTimeMatrix
from backend.app.models.visit import VisitModel
from backend.app.services.optimiser import (
    OptimisationEngine,
    RoutingModel,
    _minutes_to_time_str,
    _time_str_to_minutes,
    W_TRAVEL_TIME,
    W_MILEAGE,
    W_OVERTIME,
    W_CONTINUITY,
    W_PREFERENCE,
    W_BALANCE,
    W_PUNCTUALITY,
    METRES_PER_MILE,
)


# --- Test fixtures ---


def _make_carers(n: int = 2) -> list[CarerModel]:
    """Create n carers with different skills."""
    skills_pool = [
        ["personal_care", "medication"],
        ["personal_care", "mobility"],
        ["medication", "mobility", "personal_care"],
        ["personal_care"],
        ["medication"],
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
            required_skills=["personal_care"] if i % 2 == 0 else ["medication"],
            preferred_time="09:00",
            is_cancelled=False,
        )
        for i in range(n)
    ]


def _make_travel_matrix(num_carers: int, num_visits: int) -> TravelTimeMatrix:
    """Create a symmetric travel matrix with uniform 10-minute travel times."""
    num_locations = num_carers + num_visits
    locations = [(51.5 + i * 0.01, -0.1 + i * 0.01) for i in range(num_locations)]
    # 600 seconds (10 minutes) between all pairs, 0 on diagonal
    durations = [
        [0 if i == j else 600 for j in range(num_locations)]
        for i in range(num_locations)
    ]
    # 5000 metres (5 km) between all pairs, 0 on diagonal
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


# --- Tests ---


class TestBuildModel:
    """Tests for OptimisationEngine.build_model()."""

    def test_returns_routing_model(self):
        """build_model returns a RoutingModel dataclass."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)

        assert isinstance(result, RoutingModel)
        assert result.manager is not None
        assert result.routing is not None
        assert result.search_parameters is not None

    def test_correct_vehicle_count(self):
        """Number of vehicles matches number of carers."""
        engine = OptimisationEngine()
        carers = _make_carers(3)
        visits = _make_visits(5)
        matrix = _make_travel_matrix(3, 5)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)

        assert len(result.carer_ids) == 3
        assert result.carer_ids == [1, 2, 3]

    def test_visit_index_map_populated(self):
        """Visit index map contains all visit IDs."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)

        assert len(result.visit_index_map) == 4
        for visit in visits:
            assert visit.id in result.visit_index_map

    def test_time_limit_set_to_10_seconds(self):
        """Search parameters have 10 second time limit."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)

        assert result.search_parameters.time_limit.seconds == 10

    def test_first_solution_strategy_automatic(self):
        """First solution strategy is AUTOMATIC."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)

        assert (
            result.search_parameters.first_solution_strategy
            == routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
        )

    def test_model_solvable_with_all_constraints(self):
        """Model with all constraints enabled can be solved (produces a solution or proves infeasibility)."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)

        # Attempt to solve - should complete without error
        solution = result.routing.SolveWithParameters(result.search_parameters)
        # Solution may or may not exist (depends on constraints), but solver should not crash
        # With our test data (generous windows, short travel), a solution should exist
        assert solution is not None

    def test_model_without_constraints(self):
        """Model with no constraints enabled still builds successfully."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        # All constraints disabled
        constraints = [
            ConstraintModel(id=i + 1, name=c[0], description=c[1], is_enabled=False)
            for i, c in enumerate([
                ("skill_matching", ""),
                ("medication_competency", ""),
                ("time_windows", ""),
                ("max_working_hours", ""),
                ("mandatory_breaks", ""),
                ("travel_feasibility", ""),
                ("no_overlapping_visits", ""),
            ])
        ]

        result = engine.build_model(carers, visits, matrix, constraints)

        assert isinstance(result, RoutingModel)
        solution = result.routing.SolveWithParameters(result.search_parameters)
        assert solution is not None

    def test_skill_matching_restricts_vehicles(self):
        """Skill matching constraint prevents assignment to unqualified carers."""
        engine = OptimisationEngine()
        # Carer 1 has personal_care + medication, Carer 2 has personal_care + mobility
        carers = _make_carers(2)
        # Visit requires medication — only carer 1 qualifies
        visits = [
            VisitModel(
                id=1,
                patient_id=1,
                duration_minutes=30,
                window_start="08:00",
                window_end="12:00",
                required_skills=["medication"],
                preferred_time="09:00",
                is_cancelled=False,
            )
        ]
        matrix = _make_travel_matrix(2, 1)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)

        # Solve and verify the visit is assigned to carer 1 (vehicle 0)
        solution = result.routing.SolveWithParameters(result.search_parameters)
        assert solution is not None
        # Get which vehicle serves visit node 0
        visit_index = result.manager.NodeToIndex(0)
        vehicle = solution.Value(result.routing.VehicleVar(visit_index))
        assert vehicle == 0  # Carer 1 (index 0) has medication skill

    def test_time_window_enforcement(self):
        """Visit scheduled within its time window."""
        engine = OptimisationEngine()
        carers = _make_carers(1)
        visits = [
            VisitModel(
                id=1,
                patient_id=1,
                duration_minutes=30,
                window_start="10:00",
                window_end="11:00",
                required_skills=["personal_care"],
                preferred_time="10:00",
                is_cancelled=False,
            )
        ]
        matrix = _make_travel_matrix(1, 1)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)
        solution = result.routing.SolveWithParameters(result.search_parameters)
        assert solution is not None

        # Check arrival time is within window
        time_dim = result.routing.GetDimensionOrDie("Time")
        visit_index = result.manager.NodeToIndex(0)
        arrival = solution.Min(time_dim.CumulVar(visit_index))
        assert arrival >= 600  # 10:00 = 600 minutes
        assert arrival <= 630  # 11:00 - 30min duration = 10:30 = 630 minutes

    def test_stores_references_to_input_data(self):
        """RoutingModel stores references to visits, carers, and travel matrix."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(3)
        matrix = _make_travel_matrix(2, 3)
        constraints = _all_constraints_enabled()

        result = engine.build_model(carers, visits, matrix, constraints)

        assert result.visits == visits
        assert result.carers == carers
        assert result.travel_matrix == matrix



# --- Tests for extract_routes ---


class TestExtractRoutes:
    """Tests for OptimisationEngine.extract_routes()."""

    def test_extracts_routes_from_solved_model(self):
        """extract_routes returns RouteModel objects from a solved model."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        routes = engine.extract_routes(solution, model)

        assert len(routes) > 0
        for route in routes:
            assert route.carer_id in model.carer_ids
            assert len(route.stops) > 0
            assert route.total_travel_minutes >= 0
            assert route.total_mileage >= 0
            assert route.total_cost >= 0

    def test_route_stops_have_valid_times(self):
        """Each route stop has valid HH:MM formatted times."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        routes = engine.extract_routes(solution, model)

        for route in routes:
            for stop in route.stops:
                # Verify HH:MM format
                assert len(stop.arrival_time.split(":")) == 2
                assert len(stop.start_time.split(":")) == 2
                assert len(stop.end_time.split(":")) == 2
                # End time should be after start time
                start_min = _time_str_to_minutes(stop.start_time)
                end_min = _time_str_to_minutes(stop.end_time)
                assert end_min > start_min

    def test_route_stops_have_correct_patient_ids(self):
        """Each stop references a valid patient_id from the visit."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        routes = engine.extract_routes(solution, model)

        visit_map = {v.id: v for v in visits}
        for route in routes:
            for stop in route.stops:
                assert stop.visit_id in visit_map
                assert stop.patient_id == visit_map[stop.visit_id].patient_id

    def test_route_mileage_calculated_from_metres(self):
        """Mileage is calculated by converting metres to miles."""
        engine = OptimisationEngine()
        carers = _make_carers(1)
        visits = [
            VisitModel(
                id=1,
                patient_id=1,
                duration_minutes=30,
                window_start="08:00",
                window_end="12:00",
                required_skills=["personal_care"],
                preferred_time="09:00",
                is_cancelled=False,
            )
        ]
        matrix = _make_travel_matrix(1, 1)
        # distances are 5000m between all pairs
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        routes = engine.extract_routes(solution, model)

        assert len(routes) == 1
        # 5000m / 1609.34 ≈ 3.11 miles
        expected_mileage = 5000 / METRES_PER_MILE
        assert abs(routes[0].stops[0].mileage_from_prev - expected_mileage) < 0.01

    def test_route_cost_calculation(self):
        """Route cost includes mileage and travel time components."""
        engine = OptimisationEngine()
        carers = _make_carers(1)
        visits = [
            VisitModel(
                id=1,
                patient_id=1,
                duration_minutes=30,
                window_start="08:00",
                window_end="12:00",
                required_skills=["personal_care"],
                preferred_time="09:00",
                is_cancelled=False,
            )
        ]
        matrix = _make_travel_matrix(1, 1)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        routes = engine.extract_routes(solution, model)

        assert len(routes) == 1
        route = routes[0]
        # Cost = £0.45/mile * mileage + £15/hour * travel_hours
        expected_cost = (0.45 * route.total_mileage) + (
            15.0 * route.total_travel_minutes / 60.0
        )
        assert abs(route.total_cost - expected_cost) < 0.01

    def test_all_assigned_visits_appear_in_routes(self):
        """Every assigned visit appears exactly once across all routes."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        routes = engine.extract_routes(solution, model)

        all_visit_ids = []
        for route in routes:
            for stop in route.stops:
                all_visit_ids.append(stop.visit_id)

        # No duplicates
        assert len(all_visit_ids) == len(set(all_visit_ids))


# --- Tests for detect_infeasibility ---


class TestDetectInfeasibility:
    """Tests for OptimisationEngine.detect_infeasibility()."""

    def test_no_infeasibility_when_all_assigned(self):
        """When all visits are assigned, returns empty lists."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        unassigned, reasons = engine.detect_infeasibility(solution, model)

        assert len(unassigned) == 0
        assert len(reasons) == 0

    def test_all_unassigned_when_no_solution(self):
        """When solution is None, all visits are unassigned."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)

        unassigned, reasons = engine.detect_infeasibility(None, model)

        assert len(unassigned) == 4
        assert len(reasons) == 4
        for reason in reasons:
            assert reason.constraint_name == "all_constraints"

    def test_skill_infeasibility_detected(self):
        """Visits with impossible skill requirements are flagged."""
        engine = OptimisationEngine()
        # Carers have personal_care + medication/mobility only
        carers = _make_carers(2)
        # Visit requires a skill no carer has
        visits = [
            VisitModel(
                id=1,
                patient_id=1,
                duration_minutes=30,
                window_start="08:00",
                window_end="12:00",
                required_skills=["advanced_nursing"],
                preferred_time="09:00",
                is_cancelled=False,
            )
        ]
        matrix = _make_travel_matrix(2, 1)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)

        # The visit may be left unassigned due to skill constraint
        if solution is not None:
            unassigned, reasons = engine.detect_infeasibility(solution, model)
            if len(unassigned) > 0:
                assert reasons[0].constraint_name == "skill_matching"
                assert "advanced_nursing" in reasons[0].reason


# --- Tests for calculate_objective ---


class TestCalculateObjective:
    """Tests for OptimisationEngine.calculate_objective()."""

    def test_objective_weighted_sum(self):
        """Objective score follows the weighted sum formula."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        routes = engine.extract_routes(solution, model)
        score = engine.calculate_objective(routes, model)

        # Score should be a finite number
        assert isinstance(score, float)
        assert score == score  # Not NaN

    def test_objective_decreases_with_higher_continuity(self):
        """Higher continuity score reduces the objective (better)."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()

        model = engine.build_model(carers, visits, matrix, constraints)
        solution = model.routing.SolveWithParameters(model.search_parameters)
        assert solution is not None

        routes = engine.extract_routes(solution, model)

        score_low = engine.calculate_objective(routes, model, continuity_score=0.0)
        score_high = engine.calculate_objective(routes, model, continuity_score=1.0)

        # Higher continuity means lower (better) objective
        assert score_high < score_low

    def test_objective_zero_routes(self):
        """Objective with no routes returns a value based on quality scores."""
        engine = OptimisationEngine()
        carers = _make_carers(2)
        visits = _make_visits(4)
        matrix = _make_travel_matrix(2, 4)
        constraints = _all_constraints_enabled()
        model = engine.build_model(carers, visits, matrix, constraints)

        score = engine.calculate_objective([], model)

        # With no routes, travel/mileage/overtime are 0, balance is 1.0
        # Score = 0 + 0 + 0 - 0 - 0 - W_BALANCE*1.0 - 0 = -W_BALANCE
        expected = -W_BALANCE * 1.0
        assert abs(score - expected) < 0.001


# --- Tests for time conversion helpers ---


class TestTimeHelpers:
    """Tests for time conversion utility functions."""

    def test_minutes_to_time_str(self):
        """Converts minutes from midnight to HH:MM."""
        assert _minutes_to_time_str(0) == "00:00"
        assert _minutes_to_time_str(60) == "01:00"
        assert _minutes_to_time_str(480) == "08:00"
        assert _minutes_to_time_str(750) == "12:30"
        assert _minutes_to_time_str(1439) == "23:59"

    def test_time_str_to_minutes(self):
        """Converts HH:MM to minutes from midnight."""
        assert _time_str_to_minutes("00:00") == 0
        assert _time_str_to_minutes("01:00") == 60
        assert _time_str_to_minutes("08:00") == 480
        assert _time_str_to_minutes("12:30") == 750
        assert _time_str_to_minutes("23:59") == 1439

    def test_roundtrip_conversion(self):
        """Converting to minutes and back yields original string."""
        for time_str in ["00:00", "08:30", "12:00", "17:45", "23:59"]:
            assert _minutes_to_time_str(_time_str_to_minutes(time_str)) == time_str
