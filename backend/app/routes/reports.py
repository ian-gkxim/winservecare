"""Reports endpoints for the AI Care Operations Optimiser."""

from fastapi import APIRouter

from backend.app.db.repositories import get_scenarios

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/latest")
async def get_latest_report() -> dict:
    """Return a report comparing the two most recent scenarios.

    The report includes before/after KPIs and calculated differences
    (absolute and percentage). Returns a message if fewer than 2
    scenarios exist.
    """
    scenarios = await get_scenarios()  # ordered by created_at DESC

    if len(scenarios) < 2:
        return {
            "available": False,
            "message": "No optimisation results are available. At least two scenarios are required for a comparison report.",
        }

    # Most recent is the "after" (proposed), second-most-recent is "before" (current)
    after = scenarios[0]
    before = scenarios[1]

    def calc_diff(before_val: float, after_val: float) -> dict:
        absolute = round(before_val - after_val, 2)
        percentage = (
            round(((before_val - after_val) / before_val) * 100, 1)
            if before_val > 0
            else 0.0
        )
        return {"absolute": absolute, "percentage": percentage}

    return {
        "available": True,
        "before": {
            "scenario_name": before.name,
            "total_travel_hours": before.total_travel_hours,
            "total_mileage": before.total_mileage,
            "total_overtime_hours": before.total_overtime_hours,
            "continuity_score": before.continuity_score,
            "objective_score": before.objective_score,
        },
        "after": {
            "scenario_name": after.name,
            "total_travel_hours": after.total_travel_hours,
            "total_mileage": after.total_mileage,
            "total_overtime_hours": after.total_overtime_hours,
            "continuity_score": after.continuity_score,
            "objective_score": after.objective_score,
        },
        "differences": {
            "travel_hours": calc_diff(
                before.total_travel_hours, after.total_travel_hours
            ),
            "mileage": calc_diff(before.total_mileage, after.total_mileage),
            "overtime": calc_diff(
                before.total_overtime_hours, after.total_overtime_hours
            ),
            "continuity_score": calc_diff(
                after.continuity_score, before.continuity_score
            ),
            "objective_score": calc_diff(
                before.objective_score, after.objective_score
            ),
        },
    }
