"""Scenario management endpoints."""

from fastapi import APIRouter, HTTPException, Query

from backend.app.db.repositories import (
    compare_scenarios,
    create_scenario,
    get_scenario,
    get_scenarios,
)
from backend.app.models.scenario import ScenarioCreate, ScenarioModel

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioModel])
async def list_scenarios():
    """List all saved scenarios ordered by creation date (newest first)."""
    return await get_scenarios()


@router.get("/compare")
async def compare_scenarios_endpoint(ids: str = Query(..., description="Comma-separated scenario IDs to compare")):
    """Compare two or more scenarios side by side.

    Query parameter `ids` should contain comma-separated scenario IDs (e.g. ?ids=1,2).
    At least 2 IDs are required.
    """
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs must be comma-separated integers")

    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="At least 2 scenario IDs are required for comparison")

    try:
        result = await compare_scenarios(id_list[0], id_list[1])
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@router.post("", response_model=ScenarioModel, status_code=201)
async def create_scenario_endpoint(payload: ScenarioCreate):
    """Save an optimisation result as a named scenario.

    Validates that the scenario name is unique.
    """
    try:
        scenario = await create_scenario(
            name=payload.name,
            total_travel_hours=payload.total_travel_hours,
            total_mileage=payload.total_mileage,
            total_overtime_hours=payload.total_overtime_hours,
            continuity_score=payload.continuity_score,
            objective_score=payload.objective_score,
            assignments=payload.assignments,
            routes=payload.routes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return scenario


@router.get("/{scenario_id}", response_model=ScenarioModel)
async def get_scenario_endpoint(scenario_id: int):
    """Get full details of a specific scenario."""
    try:
        return await get_scenario(scenario_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
