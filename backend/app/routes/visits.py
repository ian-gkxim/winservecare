"""Visit API endpoints."""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response

from backend.app.db.repositories import (
    cancel_visit,
    cancel_visit_by_id,
    create_scenario,
    get_carers,
    get_constraints,
    get_patients,
    get_visits,
    get_visits_by_date,
)
from backend.app.models.contract import GenerateVisitsRequest
from backend.app.services.maps_client import GoogleMapsClient, MapsAPIError
from backend.app.services.optimiser import OptimisationEngine
from backend.app.services.visit_generator import VisitGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visits", tags=["visits"])


async def _noop_callback(payload: dict) -> None:
    """No-op callback for background optimisation (no WebSocket to stream to)."""
    pass


async def _trigger_reoptimisation() -> None:
    """Background task: re-optimise the schedule after a visit cancellation.

    Fetches remaining active visits, carers, patients, and constraints,
    builds a fresh travel matrix via the Maps API, runs the OR-Tools solver,
    and saves the result as a new scenario.

    Errors are logged but never raised — the HTTP response has already been sent.
    """
    try:
        # Fetch current data
        carers = await get_carers()
        patients = await get_patients()
        all_visits = await get_visits()
        constraints = await get_constraints()

        # Only optimise non-cancelled visits
        visits = [v for v in all_visits if not v.is_cancelled]

        if not visits or not carers:
            logger.info(
                "Re-optimisation skipped: no active visits (%d) or no carers (%d)",
                len(visits),
                len(carers),
            )
            return

        # Build location list: carer homes first, then visit patient locations
        patient_map = {p.id: p for p in patients}
        carer_locations = [(c.home_lat, c.home_lng) for c in carers]
        visit_locations = [
            (patient_map[v.patient_id].lat, patient_map[v.patient_id].lng)
            for v in visits
        ]
        all_locations = carer_locations + visit_locations

        # Fetch fresh travel matrix
        maps_client = GoogleMapsClient()
        try:
            travel_matrix = await maps_client.get_distance_matrix(
                origins=all_locations,
                destinations=all_locations,
            )
        except MapsAPIError as e:
            logger.error("Re-optimisation failed — Maps API error: %s", e.message)
            return

        # Run optimisation (no WebSocket callbacks needed)
        engine = OptimisationEngine()
        result = await engine.run(
            carers=carers,
            visits=visits,
            patients=patients,
            constraints=constraints,
            travel_matrix=travel_matrix,
            on_step=_noop_callback,
            on_progress=_noop_callback,
        )

        # Save result as a new scenario
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scenario_name = f"Auto-reoptimisation {timestamp}"

        assignments = [
            {"carer_id": route.carer_id, "visit_ids": [s.visit_id for s in route.stops]}
            for route in result.routes
        ]
        routes_data = [route.model_dump() for route in result.routes]

        await create_scenario(
            name=scenario_name,
            total_travel_hours=result.kpis.travel_hours,
            total_mileage=result.kpis.mileage,
            total_overtime_hours=result.kpis.overtime,
            continuity_score=result.kpis.continuity_score,
            objective_score=result.objective_score,
            assignments=assignments,
            routes=routes_data,
        )

        logger.info(
            "Re-optimisation complete — scenario '%s' saved (score=%.2f)",
            scenario_name,
            result.objective_score,
        )

    except Exception:
        logger.exception("Unexpected error during background re-optimisation")


@router.get("")
async def list_visits(target_date: Optional[str] = Query(None)):
    """Retrieve all visits, optionally filtered by target_date.

    If target_date query param is provided (YYYY-MM-DD), returns visits for that date.
    Otherwise returns all visits (backward compatible).
    """
    if target_date is not None:
        return await get_visits_by_date(target_date)
    return await get_visits()


@router.delete("/{visit_id}", status_code=204)
async def delete_visit(visit_id: int, background_tasks: BackgroundTasks) -> Response:
    """Cancel a visit and trigger re-optimisation in the background."""
    try:
        await cancel_visit(visit_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Visit with id {visit_id} not found")

    background_tasks.add_task(_trigger_reoptimisation)
    return Response(status_code=204)


@router.post("/generate")
async def generate_visits(request: GenerateVisitsRequest):
    """Generate visits for the target date from active care contracts.

    Validates that target_date is not in the past (< today).
    Deletes any existing visits for the date before generating new ones.
    """
    if request.target_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Target date cannot be in the past",
        )

    generator = VisitGenerator()
    response = await generator.generate_visits(request.target_date)
    return response


@router.post("/regenerate")
async def regenerate_visits(request: GenerateVisitsRequest):
    """Reset cancelled visits and regenerate for the target date.

    Validates that target_date is not in the past (< today).
    Deletes all existing visits (including cancelled) and regenerates from contracts.
    """
    if request.target_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Target date cannot be in the past",
        )

    generator = VisitGenerator()
    response = await generator.generate_visits(request.target_date)
    return response


@router.patch("/{visit_id}/cancel")
async def cancel_single_visit(visit_id: int):
    """Cancel a single visit by ID. Returns the updated visit model.

    Returns 404 if the visit does not exist.
    """
    try:
        updated_visit = await cancel_visit_by_id(visit_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Visit with id {visit_id} not found",
        )
    return updated_visit
