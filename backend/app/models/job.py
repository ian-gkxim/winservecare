"""Pydantic models for the background optimisation jobs API."""

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    """Request body for creating a new optimisation job."""

    visit_ids: list[int] | None = None


class JobCreateResponse(BaseModel):
    """Response body after creating a new job (HTTP 202)."""

    job_id: str


class JobProgress(BaseModel):
    """Progress snapshot for a running/completed job."""

    job_id: str
    status: str  # queued | running | completed | failed | stale | cancelled
    elapsed_seconds: int = 0
    percentage_complete: int = Field(ge=0, le=100, default=0)
    solutions_found: int = 0
    current_best_score: float | None = None
    is_stale: bool = False
    stale_tables: dict[str, bool] | None = None


class JobSummary(BaseModel):
    """Summary of a job for the list endpoint."""

    job_id: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    is_stale: bool = False
    visit_count: int = 0


class ActiveJobInfo(BaseModel):
    """Response for checking if a job is currently running."""

    active: bool
    job_id: str | None = None
    status: str | None = None


class JobNotificationEvent(BaseModel):
    """SSE notification event payload."""

    event_type: str  # "job_completed" | "job_failed" | "job_stale"
    job_id: str
    message: str
    error_summary: str | None = None  # max 200 chars for failed jobs
