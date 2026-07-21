"""Patient CRUD API endpoints."""

from fastapi import APIRouter, HTTPException

from backend.app.db.repositories import get_patients, update_patient
from backend.app.models.patient import PatientModel, PatientUpdate

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("", response_model=list[PatientModel])
async def list_patients() -> list[PatientModel]:
    """Retrieve all patients."""
    return await get_patients()


@router.put("/{patient_id}", response_model=PatientModel)
async def edit_patient(patient_id: int, data: PatientUpdate) -> PatientModel:
    """Update a patient record with partial data."""
    try:
        return await update_patient(patient_id, data)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Patient with id {patient_id} not found")
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={"errors": [{"field": "name", "message": str(e)}]},
        )
