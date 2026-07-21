"""Unit tests for recommendation and warning generation."""

import pytest

from backend.app.models.carer import CarerModel
from backend.app.models.optimisation import RecommendationModel, RouteModel, RouteStop
from backend.app.models.visit import VisitModel
from backend.app.services.recommendations import (
    generate_recommendations,
    _calculate_carer_hours,
    _generate_hours_warnings,
    _generate_flexibility_warnings,
)


def _make_carer(
    id: int = 1,
    name: str = "Alice",
    max_working_hours: float = 8.0,
    skills: list[str] | None = None,
) -> CarerModel:
    return CarerModel(
        id=id,
        name=name,
        home_lat=51.5,
        home_lng=-0.1,
        skills=skills or [],
        max_working_hours=max_working_hours,
    )


def _make_visit(
    id: int = 1,
    patient_id: int = 1,
    duration_minutes: int = 30,
    window_start: str = "09:00",
    window_end: str = "11:00",
    required_skills: list[str] | None = None,
) -> VisitModel:
    return VisitModel(
        id=id,
        patient_id=patient_id,
        duration_minutes=duration_minutes,
        window_start=window_start,
        window_end=window_end,
        required_skills=required_skills or [],
    )


def _make_route(
    carer_id: int = 1,
    stops: list[RouteStop] | None = None,
    total_travel_minutes: int = 30,
) -> RouteModel:
    return RouteModel(
        carer_id=carer_id,
        stops=stops or [],
        total_travel_minutes=total_travel_minutes,
        total_mileage=10.0,
        total_cost=50.0,
    )


def _make_stop(
    visit_id: int = 1,
    patient_id: int = 1,
    start_time: str = "09:00",
    end_time: str = "09:30",
    travel_time_from_prev: int = 10,
) -> RouteStop:
    return RouteStop(
        visit_id=visit_id,
        patient_id=patient_id,
        arrival_time=start_time,
        start_time=start_time,
        end_time=end_time,
        travel_time_from_prev=travel_time_from_prev,
        mileage_from_prev=2.0,
    )


class TestCalculateCarerHours:
    def test_empty_route(self):
        route = _make_route(stops=[], total_travel_minutes=0)
        assert _calculate_carer_hours(route) == 0.0

    def test_single_stop(self):
        # 30 min visit + 10 min travel = 40 min = 0.667h
        stop = _make_stop(start_time="09:00", end_time="09:30")
        route = _make_route(stops=[stop], total_travel_minutes=10)
        hours = _calculate_carer_hours(route)
        assert abs(hours - (40 / 60)) < 0.01

    def test_multiple_stops(self):
        stops = [
            _make_stop(visit_id=1, start_time="09:00", end_time="09:30"),
            _make_stop(visit_id=2, start_time="10:00", end_time="10:45"),
        ]
        # Visit durations: 30 + 45 = 75 min
        # Travel: 60 min
        # Total: 135 min = 2.25h
        route = _make_route(stops=stops, total_travel_minutes=60)
        hours = _calculate_carer_hours(route)
        assert abs(hours - (135 / 60)) < 0.01


class TestHoursWarnings:
    def test_no_warning_below_threshold(self):
        """No warning when carer is under 80% of max hours."""
        carer = _make_carer(max_working_hours=10.0)
        # 30 min visit + 10 min travel = 40 min = 0.67h (6.7% of 10h)
        stop = _make_stop(start_time="09:00", end_time="09:30")
        route = _make_route(carer_id=1, stops=[stop], total_travel_minutes=10)

        warnings = _generate_hours_warnings([route], [carer])
        assert len(warnings) == 0

    def test_warning_at_80_percent(self):
        """Warning generated when carer is at exactly 80% of max."""
        carer = _make_carer(max_working_hours=8.0)
        # Need 6.4h = 384 min of work
        # Let's use 354 min visits + 30 min travel = 384 min
        stop = _make_stop(start_time="09:00", end_time="14:54")  # 354 min
        route = _make_route(carer_id=1, stops=[stop], total_travel_minutes=30)

        warnings = _generate_hours_warnings([route], [carer])
        assert len(warnings) == 1
        assert warnings[0].type == "warning"
        assert warnings[0].title == "Approaching hours limit"

    def test_warning_above_80_percent(self):
        """Warning generated when carer exceeds 80% of max."""
        carer = _make_carer(max_working_hours=8.0)
        # 7h = 420 min work (87.5% of 8h)
        stop = _make_stop(start_time="08:00", end_time="14:30")  # 390 min
        route = _make_route(carer_id=1, stops=[stop], total_travel_minutes=30)

        warnings = _generate_hours_warnings([route], [carer])
        assert len(warnings) == 1
        assert "87%" in warnings[0].description


class TestFlexibilityWarnings:
    def test_no_warning_comfortable_margin(self):
        """No warning when visit is well within time window."""
        visit = _make_visit(window_start="09:00", window_end="12:00", duration_minutes=30)
        stop = _make_stop(visit_id=1, start_time="10:00", end_time="10:30")
        route = _make_route(stops=[stop])

        warnings = _generate_flexibility_warnings([route], [visit])
        assert len(warnings) == 0

    def test_warning_near_window_start(self):
        """Warning when visit starts within 15 min of window start."""
        visit = _make_visit(window_start="09:00", window_end="12:00", duration_minutes=30)
        stop = _make_stop(visit_id=1, start_time="09:10", end_time="09:40")
        route = _make_route(stops=[stop])

        warnings = _generate_flexibility_warnings([route], [visit])
        assert len(warnings) == 1
        assert warnings[0].title == "Limited flexibility"
        assert "start" in warnings[0].description

    def test_warning_near_window_end(self):
        """Warning when visit ends within 15 min of window end."""
        visit = _make_visit(window_start="09:00", window_end="11:00", duration_minutes=30)
        stop = _make_stop(visit_id=1, start_time="10:20", end_time="10:50")
        route = _make_route(stops=[stop])

        warnings = _generate_flexibility_warnings([route], [visit])
        assert len(warnings) == 1
        assert warnings[0].title == "Limited flexibility"
        assert "end" in warnings[0].description

    def test_no_warning_exactly_at_15_min(self):
        """No warning when visit is exactly 15 min from edge (not within)."""
        visit = _make_visit(window_start="09:00", window_end="12:00", duration_minutes=30)
        # Start at 09:15 => 15 min from start. 15 < 15 is False, so no warning.
        stop = _make_stop(visit_id=1, start_time="09:15", end_time="09:45")
        route = _make_route(stops=[stop])

        warnings = _generate_flexibility_warnings([route], [visit])
        assert len(warnings) == 0


class TestGenerateRecommendations:
    def test_empty_inputs(self):
        """No recommendations for empty inputs."""
        result = generate_recommendations([], [], [], [])
        assert result == []

    def test_unassigned_visits_generate_recommendations(self):
        """Unassigned visits produce recommendation items."""
        visit = _make_visit(id=5, window_start="09:00", window_end="11:00")
        result = generate_recommendations([], [], [visit], [5])

        assert len(result) == 1
        assert result[0].type == "recommendation"
        assert result[0].title == "Unassigned visit"
        assert "5" in result[0].description

    def test_workload_imbalance_over_2_hours(self):
        """Imbalance recommendation when spread > 2h."""
        carer1 = _make_carer(id=1, name="Alice", max_working_hours=10.0)
        carer2 = _make_carer(id=2, name="Bob", max_working_hours=10.0)

        # Carer 1: 5h of work
        stop1 = _make_stop(visit_id=1, start_time="08:00", end_time="12:30")  # 270 min
        route1 = _make_route(carer_id=1, stops=[stop1], total_travel_minutes=30)

        # Carer 2: 1h of work
        stop2 = _make_stop(visit_id=2, start_time="09:00", end_time="09:30")  # 30 min
        route2 = _make_route(carer_id=2, stops=[stop2], total_travel_minutes=30)

        result = generate_recommendations([route1, route2], [carer1, carer2], [], [])

        imbalance = [r for r in result if r.title == "Workload imbalance"]
        assert len(imbalance) == 1

    def test_no_workload_imbalance_within_2_hours(self):
        """No imbalance recommendation when spread <= 2h."""
        carer1 = _make_carer(id=1, name="Alice", max_working_hours=10.0)
        carer2 = _make_carer(id=2, name="Bob", max_working_hours=10.0)

        stop1 = _make_stop(visit_id=1, start_time="09:00", end_time="10:30")  # 90 min
        route1 = _make_route(carer_id=1, stops=[stop1], total_travel_minutes=30)

        stop2 = _make_stop(visit_id=2, start_time="09:00", end_time="09:30")  # 30 min
        route2 = _make_route(carer_id=2, stops=[stop2], total_travel_minutes=30)

        result = generate_recommendations([route1, route2], [carer1, carer2], [], [])

        imbalance = [r for r in result if r.title == "Workload imbalance"]
        assert len(imbalance) == 0

    def test_sorted_by_impact_descending(self):
        """Results are sorted by impact, highest first."""
        carer = _make_carer(id=1, max_working_hours=8.0)
        # Trigger hours warning (impact 0.9)
        stop = _make_stop(visit_id=1, start_time="08:00", end_time="14:54")  # ~7h
        route = _make_route(carer_id=1, stops=[stop], total_travel_minutes=30)

        # Trigger unassigned visit (impact 0.7)
        visit1 = _make_visit(id=1, window_start="08:00", window_end="15:00")
        visit2 = _make_visit(id=2, window_start="09:00", window_end="11:00")

        result = generate_recommendations([route], [carer], [visit1, visit2], [2])

        # Verify descending order
        for i in range(len(result) - 1):
            assert result[i].impact >= result[i + 1].impact

    def test_max_10_items(self):
        """Output capped at 10 items."""
        visits = [_make_visit(id=i, window_start="09:00", window_end="11:00") for i in range(1, 16)]
        unassigned = list(range(1, 16))  # 15 unassigned visits

        result = generate_recommendations([], [], visits, unassigned)
        assert len(result) <= 10

    def test_descriptions_max_200_chars(self):
        """All descriptions are at most 200 characters."""
        carer = _make_carer(id=1, max_working_hours=8.0)
        stop = _make_stop(visit_id=1, start_time="08:00", end_time="14:54")
        route = _make_route(carer_id=1, stops=[stop], total_travel_minutes=30)

        visit = _make_visit(
            id=1,
            window_start="08:00",
            window_end="15:00",
            required_skills=["skill_a", "skill_b", "skill_c"],
        )

        result = generate_recommendations([route], [carer], [visit], [2])

        for item in result:
            assert len(item.description) <= 200

    def test_warnings_have_higher_impact_than_recommendations(self):
        """Warnings default to higher impact values than recommendations."""
        carer = _make_carer(id=1, max_working_hours=8.0)
        # Trigger hours warning
        stop = _make_stop(visit_id=1, start_time="08:00", end_time="14:54")
        route = _make_route(carer_id=1, stops=[stop], total_travel_minutes=30)

        visit = _make_visit(id=1, window_start="08:00", window_end="15:00")
        visit2 = _make_visit(id=2, window_start="09:00", window_end="11:00")

        result = generate_recommendations([route], [carer], [visit, visit2], [2])

        warnings = [r for r in result if r.type == "warning"]
        recs = [r for r in result if r.type == "recommendation"]

        if warnings and recs:
            min_warning_impact = min(w.impact for w in warnings)
            max_rec_impact = max(r.impact for r in recs)
            assert min_warning_impact > max_rec_impact
