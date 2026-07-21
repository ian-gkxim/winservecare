"""Carer CRUD API endpoints."""

from fastapi import APIRouter, HTTPException

from backend.app.db.repositories import get_carers, update_carer
from backend.app.models.carer import CarerModel, CarerUpdate

router = APIRouter(prefix="/api/carers", tags=["carers"])


@router.get("", response_model=list[CarerModel])
async def list_carers() -> list[CarerModel]:
    """Retrieve all carers."""
    return await get_carers()


@router.put("/{carer_id}", response_model=CarerModel)
async def edit_carer(carer_id: int, data: CarerUpdate) -> CarerModel:
    """Update a carer record with partial data."""
    try:
        return await update_carer(carer_id, data)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Carer with id {carer_id} not found")
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={"errors": [{"field": "name", "message": str(e)}]},
        )
