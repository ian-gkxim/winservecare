"""Exception (optimisation issue) management endpoints."""

from fastapi import APIRouter, HTTPException

from backend.app.db.repositories import get_exceptions, resolve_exception
from backend.app.models.exception import ExceptionModel

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])


@router.get("", response_model=list[ExceptionModel])
async def list_exceptions():
    """List all optimisation exceptions ordered by timestamp (newest first)."""
    return await get_exceptions()


@router.put("/{exception_id}/resolve")
async def resolve_exception_endpoint(exception_id: int):
    """Mark an exception as resolved.

    Idempotent: if already resolved, returns 200 with a message indicating so.
    """
    try:
        resolved = await resolve_exception(exception_id)
        return resolved
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        # Already resolved — idempotent response per spec
        return {"message": str(e), "already_resolved": True}
