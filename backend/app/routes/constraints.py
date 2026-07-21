"""Constraint API endpoints."""

from fastapi import APIRouter, HTTPException

from backend.app.db.repositories import get_constraints, update_constraint
from backend.app.models.constraint import ConstraintModel, ConstraintUpdate

router = APIRouter(prefix="/api/constraints", tags=["constraints"])


@router.get("", response_model=list[ConstraintModel])
async def list_constraints() -> list[ConstraintModel]:
    """Retrieve all constraints."""
    return await get_constraints()


@router.put("/{constraint_id}", response_model=ConstraintModel)
async def edit_constraint(constraint_id: int, data: ConstraintUpdate) -> ConstraintModel:
    """Enable or disable a constraint."""
    try:
        return await update_constraint(constraint_id, data)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Constraint with id {constraint_id} not found"
        )
