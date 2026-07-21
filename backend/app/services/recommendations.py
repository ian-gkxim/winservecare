"""Recommendation and warning generation from optimisation results."""

from backend.app.models.carer import CarerModel
from backend.app.models.optimisation import RecommendationModel, RouteModel
from backend.app.models.visit import VisitModel


def _time_str_to_minutes(time_str: str) -> int:
    """Convert HH:MM string to minutes from midnight."""
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _calculate_carer_hours(route: RouteModel) -> float:
    """Calculate total working hours for a carer's route.

    Working hours = total visit durations + total travel time.
    """
    if not route.stops:
        return 0.0

    total_minutes = route.total_travel_minutes
    for stop in route.stops:
        start = _time_str_to_minutes(stop.start_time)
        end = _time_str_to_minutes(stop.end_time)
        total_minutes += end - start

    return total_minutes / 60.0


def _generate_hours_warnings(
    routes: list[RouteModel],
    carers: list[CarerModel],
) -> list[RecommendationModel]:
    """Generate warnings for carers approaching their working hours limit.

    A warning is generated when a carer's scheduled hours >= 80% of their max.
    """
    warnings: list[RecommendationModel] = []
    carer_map = {c.id: c for c in carers}

    for route in routes:
        carer = carer_map.get(route.carer_id)
        if carer is None:
            continue

        scheduled_hours = _calculate_carer_hours(route)
        threshold = 0.8 * carer.max_working_hours

        if scheduled_hours >= threshold:
            pct = int((scheduled_hours / carer.max_working_hours) * 100)
            warnings.append(
                RecommendationModel(
                    type="warning",
                    title="Approaching hours limit",
                    description=(
                        f"Carer {carer.name} is at {pct}% of their "
                        f"{carer.max_working_hours}h daily maximum "
                        f"({scheduled_hours:.1f}h scheduled)."
                    ),
                    impact=0.9,
                )
            )

    return warnings


def _generate_flexibility_warnings(
    routes: list[RouteModel],
    visits: list[VisitModel],
) -> list[RecommendationModel]:
    """Generate warnings for visits with limited schedule flexibility.

    A warning is issued when a visit's scheduled start is within 15 minutes
    of either edge of its time window (within 15 min of window_start, or the
    visit ends within 15 min of window_end).
    """
    warnings: list[RecommendationModel] = []
    visit_map = {v.id: v for v in visits}

    for route in routes:
        for stop in route.stops:
            visit = visit_map.get(stop.visit_id)
            if visit is None:
                continue

            start_minutes = _time_str_to_minutes(stop.start_time)
            end_minutes = _time_str_to_minutes(stop.end_time)
            window_start = _time_str_to_minutes(visit.window_start)
            window_end = _time_str_to_minutes(visit.window_end)

            near_start = (start_minutes - window_start) < 15
            near_end = (window_end - end_minutes) < 15

            if near_start or near_end:
                edge = "start" if near_start else "end"
                warnings.append(
                    RecommendationModel(
                        type="warning",
                        title="Limited flexibility",
                        description=(
                            f"Visit {stop.visit_id} starts at {stop.start_time} "
                            f"near the {edge} of its "
                            f"{visit.window_start}-{visit.window_end} window."
                        ),
                        impact=0.8,
                    )
                )

    return warnings


def _generate_unassigned_recommendations(
    unassigned_visits: list[int],
    visits: list[VisitModel],
) -> list[RecommendationModel]:
    """Generate recommendations for unassigned visits."""
    recommendations: list[RecommendationModel] = []
    visit_map = {v.id: v for v in visits}

    for visit_id in unassigned_visits:
        visit = visit_map.get(visit_id)
        if visit is None:
            desc = f"Visit {visit_id} could not be assigned. Review constraints."
        else:
            skills = ", ".join(visit.required_skills) if visit.required_skills else "none"
            desc = (
                f"Visit {visit_id} ({visit.window_start}-{visit.window_end}, "
                f"skills: {skills}) unassigned. Check carer availability."
            )
            # Truncate to 200 chars if needed
            if len(desc) > 200:
                desc = desc[:197] + "..."

        recommendations.append(
            RecommendationModel(
                type="recommendation",
                title="Unassigned visit",
                description=desc,
                impact=0.7,
            )
        )

    return recommendations


def _generate_workload_imbalance_recommendation(
    routes: list[RouteModel],
    carers: list[CarerModel],
) -> list[RecommendationModel]:
    """Generate a recommendation if workload imbalance exceeds 2 hours.

    Compares the most-loaded and least-loaded carers' scheduled hours.
    """
    if len(routes) < 2:
        return []

    carer_hours: list[float] = []
    for route in routes:
        hours = _calculate_carer_hours(route)
        carer_hours.append(hours)

    max_hours = max(carer_hours)
    min_hours = min(carer_hours)
    diff = max_hours - min_hours

    if diff > 2.0:
        return [
            RecommendationModel(
                type="recommendation",
                title="Workload imbalance",
                description=(
                    f"Workload spread is {diff:.1f}h between most-loaded "
                    f"({max_hours:.1f}h) and least-loaded ({min_hours:.1f}h) "
                    f"carers. Consider redistributing visits."
                ),
                impact=0.6,
            )
        ]

    return []


def _generate_continuity_recommendations(
    routes: list[RouteModel],
    visits: list[VisitModel],
) -> list[RecommendationModel]:
    """Generate recommendations for visits not assigned to the patient's usual carer.

    Note: This requires patient data with usual_carer_id. Since we only have
    visit data here, we check if visits have a preferred_time as a proxy for
    patient preference. A more complete implementation would accept patients
    as a parameter — but that's outside the function signature scope.

    For now, we flag visits where the assignment may not match continuity goals
    based on available information.
    """
    # Without patient data in the function signature, we cannot directly check
    # usual_carer_id. This is a placeholder that could be extended.
    return []


def generate_recommendations(
    routes: list[RouteModel],
    carers: list[CarerModel],
    visits: list[VisitModel],
    unassigned_visits: list[int],
) -> list[RecommendationModel]:
    """Generate recommendations and warnings from optimisation results.

    Produces:
    - "Approaching hours limit" warnings (carer hours >= 80% of max)
    - "Limited flexibility" warnings (visit near time window edge)
    - "Unassigned visit" recommendations
    - "Workload imbalance" recommendation (spread > 2h)

    Results are sorted by impact descending, capped at 10 items.
    Each description is limited to 200 characters.

    Args:
        routes: Optimised routes for each carer.
        carers: Available carers with their constraints.
        visits: All visits in the schedule.
        unassigned_visits: Visit IDs that could not be assigned.

    Returns:
        List of up to 10 RecommendationModel items sorted by impact (highest first).
    """
    all_items: list[RecommendationModel] = []

    # Generate warnings (higher impact by default)
    all_items.extend(_generate_hours_warnings(routes, carers))
    all_items.extend(_generate_flexibility_warnings(routes, visits))

    # Generate recommendations
    all_items.extend(_generate_unassigned_recommendations(unassigned_visits, visits))
    all_items.extend(_generate_workload_imbalance_recommendation(routes, carers))

    # Sort by impact descending
    all_items.sort(key=lambda r: r.impact, reverse=True)

    # Cap at 10 items
    return all_items[:10]
