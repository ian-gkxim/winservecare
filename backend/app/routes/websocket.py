"""WebSocket endpoint for real-time optimisation with step/progress streaming."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.db.repositories import (
    create_exception,
    get_carers,
    get_constraints,
    get_patients,
    get_visits,
    get_visits_by_date,
)
from backend.app.models.visit import VisitModel
from backend.app.services.maps_client import GoogleMapsClient, MapsAPIError
from backend.app.services.optimiser import OptimisationEngine
from backend.app.services.progress import ProgressService, fetch_matrix_with_progress

logger = logging.getLogger(__name__)

router = APIRouter()


class OptimisationSession:
    """Manages state for a single WebSocket optimisation session.

    Handles pause/resume gating via an asyncio.Event and tracks
    whether the client has disconnected so callbacks can bail out early.
    """

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.paused = asyncio.Event()
        self.paused.set()  # Start in "running" (not paused) state
        self.disconnected = False

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send a JSON message, respecting pause state and disconnect."""
        if self.disconnected:
            return
        # Wait until resumed (event is set)
        await self.paused.wait()
        if self.disconnected:
            return
        try:
            await self.websocket.send_json(data)
        except Exception:
            self.disconnected = True

    def pause(self) -> None:
        """Pause emission of step/progress messages."""
        self.paused.clear()

    def resume(self) -> None:
        """Resume emission of step/progress messages."""
        self.paused.set()

    def disconnect(self) -> None:
        """Mark session as disconnected and unblock any paused waits."""
        self.disconnected = True
        # Unblock paused.wait() so callbacks can exit cleanly
        self.paused.set()


# DEPRECATED: This WebSocket endpoint is deprecated in favour of the background job REST API.
# Migration path:
#   1. Use POST /api/jobs to start an optimisation run
#   2. Use GET /api/jobs/{job_id}/progress to poll progress
#   3. Use GET /api/jobs/notifications (SSE) for push notifications
# This endpoint will be removed in a future version once all clients have migrated.
@router.websocket("/ws/optimise")
async def websocket_optimise(websocket: WebSocket) -> None:
    """WebSocket endpoint for running optimisation with live feedback.

    .. deprecated::
        Use POST /api/jobs for new optimisation runs. This endpoint will be
        removed in a future release.

    Client→Server messages:
        - { "type": "start", "visitIds": [...] }  — start optimisation
        - { "type": "pause" }                      — pause animation
        - { "type": "resume" }                     — resume animation

    Server→Client messages:
        - { "type": "deprecation_notice", "message": "..." }  — sent on connect
        - { "type": "step", "payload": { stepNumber, stepName, data } }
        - { "type": "progress", "step": N, "name": "...", "score": N }
        - { "type": "complete", "finalScore": N, "routes": [...] }
        - { "type": "error", "step": N, "message": "..." }
    """
    await websocket.accept()

    logger.warning("WebSocket /ws/optimise is deprecated. Use POST /api/jobs for new optimisation runs.")

    await websocket.send_json({
        "type": "deprecation_notice",
        "message": "This WebSocket endpoint is deprecated. Please use the REST API (POST /api/jobs) for new optimisation runs.",
    })

    session = OptimisationSession(websocket)

    try:
        await _handle_connection(session)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        session.disconnect()
    except Exception as exc:
        logger.exception("Unexpected WebSocket error: %s", exc)
        session.disconnect()


async def _handle_connection(session: OptimisationSession) -> None:
    """Main message loop for the WebSocket connection."""
    optimisation_task: asyncio.Task | None = None

    try:
        while not session.disconnected:
            data = await session.websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start":
                # Cancel any existing optimisation before starting a new one
                if optimisation_task and not optimisation_task.done():
                    optimisation_task.cancel()
                    try:
                        await optimisation_task
                    except (asyncio.CancelledError, Exception):
                        pass

                visit_ids = data.get("visitIds")
                target_date = data.get("targetDate")
                optimisation_task = asyncio.create_task(
                    _run_optimisation(session, visit_ids, target_date)
                )

            elif msg_type == "pause":
                session.pause()

            elif msg_type == "resume":
                session.resume()

    except WebSocketDisconnect:
        session.disconnect()
    finally:
        # Clean up running optimisation on disconnect
        if optimisation_task and not optimisation_task.done():
            optimisation_task.cancel()
            try:
                await optimisation_task
            except (asyncio.CancelledError, Exception):
                pass


async def _run_optimisation(
    session: OptimisationSession,
    visit_ids: list[int] | None = None,
    target_date: str | None = None,
) -> None:
    """Execute the optimisation pipeline and stream results over WebSocket.

    Args:
        session: The active WebSocket session.
        visit_ids: Optional list of visit IDs to optimise. If None, all visits are used.
        target_date: Optional target date (YYYY-MM-DD) to filter visits for that day.
    """
    current_step = 0

    async def on_step(payload: dict[str, Any]) -> None:
        """Callback invoked by OptimisationEngine for each animation step."""
        nonlocal current_step
        if session.disconnected:
            return
        current_step = payload.get("stepNumber", current_step)
        await session.send_json({"type": "step", "payload": payload})

    async def on_progress(payload: dict[str, Any]) -> None:
        """Callback invoked by OptimisationEngine for progress updates."""
        if session.disconnected:
            return
        await session.send_json({
            "type": "progress",
            "step": payload.get("step", 0),
            "name": payload.get("name", ""),
            "score": payload.get("score", 0.0),
        })

    try:
        # Fetch data from repositories
        carers = await get_carers()
        patients = await get_patients()
        constraints = await get_constraints()

        # Fetch visits based on target_date or fallback to all visits
        if target_date:
            # Get visits for the specific target date and convert dicts to VisitModel
            visit_dicts = await get_visits_by_date(target_date)
            visits = [
                VisitModel(
                    id=v["id"],
                    patient_id=v["patient_id"],
                    duration_minutes=v["duration_minutes"],
                    window_start=v["window_start"],
                    window_end=v["window_end"],
                    required_skills=v["required_skills"],
                    preferred_time=v["preferred_time"],
                    is_cancelled=v["is_cancelled"],
                    target_date=v["target_date"],
                    contract_id=v["contract_id"],
                )
                for v in visit_dicts
                if not v["is_cancelled"]
            ]
        else:
            # Backward compatible: use all non-cancelled visits
            all_visits = await get_visits()
            visits = [v for v in all_visits if not v.is_cancelled]

        # Filter visits if specific IDs were provided
        if visit_ids:
            visits = [v for v in visits if v.id in visit_ids]

        if not visits:
            await session.send_json({
                "type": "error",
                "step": 0,
                "message": "No visits available for optimisation",
            })
            return

        if not carers:
            await session.send_json({
                "type": "error",
                "step": 0,
                "message": "No carers available for optimisation",
            })
            return

        # Build travel matrix from Google Maps
        maps_client = GoogleMapsClient()

        # Collect all locations: carer homes + patient locations for visits
        patient_map = {p.id: p for p in patients}
        carer_locations = [(c.home_lat, c.home_lng) for c in carers]
        visit_locations = [
            (patient_map[v.patient_id].lat, patient_map[v.patient_id].lng)
            for v in visits
        ]
        all_locations = carer_locations + visit_locations

        # Create progress service for fine-grained progress reporting
        progress = ProgressService(session=session, time_limit_seconds=10)
        try:
            travel_matrix = await fetch_matrix_with_progress(
                maps_client=maps_client,
                origins=all_locations,
                destinations=all_locations,
                progress=progress,
            )

            # Run optimisation engine with callbacks
            engine = OptimisationEngine()
            result = await engine.run(
                carers=carers,
                visits=visits,
                patients=patients,
                constraints=constraints,
                travel_matrix=travel_matrix,
                on_step=on_step,
                on_progress=on_progress,
                progress=progress,
            )
        finally:
            await progress.stop()

        # Log exceptions for infeasible/unassigned visits
        if result.unassigned_visits and result.infeasibility_reasons:
            for reason in result.infeasibility_reasons:
                try:
                    await create_exception(
                        description=reason.reason,
                        constraint_names=[reason.constraint_name],
                        affected_entity_type="visit",
                        affected_entity_id=reason.visit_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to log exception for visit %d: %s",
                        reason.visit_id,
                        exc,
                    )

        # Send completion message
        if not session.disconnected:
            await session.send_json({
                "type": "complete",
                "finalScore": result.objective_score,
                "routes": [route.model_dump() for route in result.routes],
            })

    except MapsAPIError as e:
        logger.error("Maps API error during optimisation: %s", e.message)
        if not session.disconnected:
            await session.send_json({
                "type": "error",
                "step": current_step,
                "message": f"Maps API error: {e.message}",
            })

    except asyncio.CancelledError:
        # Optimisation was cancelled (client disconnected or restarted)
        logger.info("Optimisation task cancelled")
        raise

    except Exception as e:
        logger.exception("Optimisation error: %s", e)
        if not session.disconnected:
            await session.send_json({
                "type": "error",
                "step": current_step,
                "message": f"Optimisation failed: {str(e)}",
            })
