"""Care Contract API endpoints for patient contract CRUD operations."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.app.db.contract_repository import (
    create_or_update_contract,
    delete_contract,
    get_contract_by_patient,
)
from backend.app.db.database import get_db
from backend.app.models.contract import CareContractCreate, CareContractModel, VisitFrequency

router = APIRouter(prefix="/api/patients", tags=["contracts"])


async def _check_patient_exists(patient_id: int) -> None:
    """Raise 404 if the patient does not exist."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM patients WHERE id = ?", (patient_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Patient with id {patient_id} not found",
            )


async def _get_existing_skill_names() -> set[str]:
    """Return the set of all skill names in the database."""
    async with get_db() as db:
        cursor = await db.execute("SELECT name FROM skills")
        rows = await cursor.fetchall()
        return {row["name"] for row in rows}


def _validate_contract(data: CareContractCreate, existing_skills: set[str]) -> None:
    """Validate business rules for a contract payload. Raises HTTPException(422) on failure."""
    errors: list[dict[str, str]] = []

    # Rule 1: visit_slots count must equal visits_per_day
    if len(data.visit_slots) != data.visits_per_day:
        errors.append({
            "field": "visit_slots",
            "message": f"visit_slots count ({len(data.visit_slots)}) must equal visits_per_day ({data.visits_per_day})",
        })

    # Rule 2: For each slot, earliest_start must be >= 06:00 and <= 22:00
    for idx, slot in enumerate(data.visit_slots):
        if slot.earliest_start < "06:00" or slot.earliest_start > "22:00":
            errors.append({
                "field": f"visit_slots[{idx}].earliest_start",
                "message": f"earliest_start ({slot.earliest_start}) must be between 06:00 and 22:00",
            })
        if slot.latest_start < "06:00" or slot.latest_start > "22:00":
            errors.append({
                "field": f"visit_slots[{idx}].latest_start",
                "message": f"latest_start ({slot.latest_start}) must be between 06:00 and 22:00",
            })

    # Rule 3: For each slot, earliest_start must be < latest_start
    for idx, slot in enumerate(data.visit_slots):
        if slot.earliest_start >= slot.latest_start:
            errors.append({
                "field": f"visit_slots[{idx}].latest_start",
                "message": f"earliest_start ({slot.earliest_start}) must be before latest_start ({slot.latest_start})",
            })

    # Rule 4: end_date must be >= start_date (if end_date is provided)
    if data.end_date is not None and data.end_date < data.start_date:
        errors.append({
            "field": "end_date",
            "message": "end_date must be on or after start_date",
        })

    # Rule 5: For specific_days frequency, days_of_week must be non-empty
    if data.visit_frequency == VisitFrequency.SPECIFIC_DAYS:
        if not data.days_of_week:
            errors.append({
                "field": "days_of_week",
                "message": "days_of_week must be non-empty when visit_frequency is 'specific_days'",
            })

    # Rule 6: Referenced skills must exist
    for idx, slot in enumerate(data.visit_slots):
        for skill_name in slot.required_skills:
            if skill_name not in existing_skills:
                errors.append({
                    "field": f"visit_slots[{idx}].required_skills",
                    "message": f"Skill '{skill_name}' does not exist",
                })

    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})


@router.get("/{patient_id}/contract", response_model=CareContractModel | None)
async def get_patient_contract(patient_id: int):
    """Get the care contract for a patient. Returns null if no contract exists."""
    await _check_patient_exists(patient_id)

    contract = await get_contract_by_patient(patient_id)
    if contract is None:
        return None
    return contract


@router.put("/{patient_id}/contract", response_model=CareContractModel)
async def upsert_patient_contract(
    patient_id: int, data: CareContractCreate
):
    """Create or update a care contract for a patient.

    Returns 201 on creation, 200 on update.
    """
    await _check_patient_exists(patient_id)

    existing_skills = await _get_existing_skill_names()
    _validate_contract(data, existing_skills)

    # Check if contract already exists to determine status code
    existing_contract = await get_contract_by_patient(patient_id)
    contract = await create_or_update_contract(patient_id, data)

    if existing_contract is None:
        return JSONResponse(
            status_code=201,
            content=contract.model_dump(mode="json"),
        )
    return contract


@router.delete("/{patient_id}/contract", status_code=204)
async def remove_patient_contract(patient_id: int):
    """Delete a patient's care contract. Returns 204 on success, 404 if not found."""
    await _check_patient_exists(patient_id)

    try:
        await delete_contract(patient_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"No care contract found for patient with id {patient_id}",
        )
