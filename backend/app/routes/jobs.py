"""REST API endpoints for background optimisation job management."""

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.app.models.job import (
    ActiveJobInfo,
    JobCreateRequest,
    JobCreateResponse,
    JobProgress,
    JobSummary,
)
from backend.app.services.job_registry import (
    JobConflictError,
    JobNotActiveError,
    JobNotFoundError,
    JobRegistry,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Module-level registry instance (will be initialized on app startup)
_registry: JobRegistry | None = None


def get_registry() -> JobRegistry:
    """Get the global JobRegistry instance."""
    if _registry is None:
        raise RuntimeError("JobRegistry not initialized")
    return _registry


def init_registry() -> JobRegistry:
    """Initialize and return the global JobRegistry instance."""
    global _registry
    _registry = JobRegistry()
    return _registry


# --- POST /api/jobs ---
@router.post("", status_code=202, response_model=JobCreateResponse)
async def create_job(body: JobCreateRequest) -> JobCreateResponse:
    """Create a new background optimisation job.

    Returns 202 Accepted with the job_id.
    Returns 409 Conflict if a job is already active.
    """
    registry = get_registry()
    try:
        job_id = await registry.create_job(visit_ids=body.visit_ids)
        return JobCreateResponse(job_id=job_id)
    except JobConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "Optimisation already in progress", "active_job_id": e.active_job_id},
        )


# --- GET /api/jobs ---
@router.get("", response_model=list[JobSummary])
async def list_jobs() -> list[JobSummary]:
    """List all retained jobs ordered by creation timestamp descending."""
    registry = get_registry()
    return await registry.list_jobs()


# --- GET /api/jobs/active ---
@router.get("/active", response_model=ActiveJobInfo)
async def check_active_job() -> ActiveJobInfo:
    """Check if a job is currently running (for edit guard)."""
    registry = get_registry()
    return await registry.check_active_job()


# --- GET /api/jobs/notifications (SSE) ---
@router.get("/notifications")
async def job_notifications(request: Request) -> StreamingResponse:
    """SSE endpoint for job status change notifications.

    Sends events as:
        event: job_status
        data: {"event_type": "...", "job_id": "...", "message": "..."}

    Sends heartbeat every 15 seconds.
    """
    registry = get_registry()
    queue = registry.subscribe()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                try:
                    # Wait for event with 15s timeout for heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: job_status\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield ": heartbeat\n\n"
        finally:
            registry.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- GET /api/jobs/{job_id}/progress ---
@router.get("/{job_id}/progress", response_model=JobProgress)
async def get_job_progress(job_id: str) -> JobProgress:
    """Get progress snapshot for a specific job."""
    registry = get_registry()
    progress = await registry.get_job_progress(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return progress


# --- DELETE /api/jobs/{job_id} ---
@router.delete("/{job_id}")
async def cancel_job(job_id: str) -> dict:
    """Cancel an active job.

    Returns 200 on success.
    Returns 404 if job not found.
    Returns 409 if job is not active (already completed/failed).
    """
    registry = get_registry()
    try:
        await registry.cancel_job(job_id)
        return {"message": "Job cancelled", "job_id": job_id}
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")
    except JobNotActiveError as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "Job is not active", "status": e.current_status},
        )
