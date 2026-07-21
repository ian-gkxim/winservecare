"""Data access layer for Care Contract CRUD operations."""

import json
from datetime import date, datetime

from backend.app.db.database import get_db
from backend.app.models.contract import (
    CareContractCreate,
    CareContractModel,
    DayOfWeek,
    VisitFrequency,
    VisitSlotModel,
)


def _parse_date(value: str | None) -> date | None:
    """Parse a YYYY-MM-DD string to a date object, or None."""
    if value is None:
        return None
    return date.fromisoformat(value)


def _format_date(value: date | None) -> str | None:
    """Format a date object to YYYY-MM-DD string, or None."""
    if value is None:
        return None
    return value.isoformat()


def _row_to_contract(row, slots: list[VisitSlotModel]) -> CareContractModel:
    """Convert a database row and its slots to a CareContractModel."""
    days_raw = row["days_of_week"]
    days_of_week = (
        [DayOfWeek(d) for d in json.loads(days_raw)] if days_raw else None
    )

    excluded_raw = row["excluded_dates"]
    excluded_dates = (
        [date.fromisoformat(d) for d in json.loads(excluded_raw)]
        if excluded_raw
        else []
    )

    return CareContractModel(
        id=row["id"],
        patient_id=row["patient_id"],
        visit_frequency=VisitFrequency(row["visit_frequency"]),
        days_of_week=days_of_week,
        visits_per_day=row["visits_per_day"],
        start_date=date.fromisoformat(row["start_date"]),
        end_date=_parse_date(row["end_date"]),
        excluded_dates=excluded_dates,
        visit_slots=slots,
    )


def _row_to_slot(row) -> VisitSlotModel:
    """Convert a database row to a VisitSlotModel."""
    return VisitSlotModel(
        id=row["id"],
        contract_id=row["contract_id"],
        slot_index=row["slot_index"],
        label=row["label"],
        earliest_start=row["earliest_start"],
        latest_start=row["latest_start"],
        duration_minutes=row["duration_minutes"],
        required_skills=json.loads(row["required_skills"]),
    )


async def get_contract_by_patient(patient_id: int) -> CareContractModel | None:
    """Get the care contract for a patient, including all visit slots.

    Returns None if no contract exists.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM care_contracts WHERE patient_id = ?", (patient_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        # Fetch associated visit slots
        slot_cursor = await db.execute(
            "SELECT * FROM visit_slots WHERE contract_id = ? ORDER BY slot_index",
            (row["id"],),
        )
        slot_rows = await slot_cursor.fetchall()
        slots = [_row_to_slot(sr) for sr in slot_rows]

        return _row_to_contract(row, slots)


async def create_or_update_contract(
    patient_id: int, data: CareContractCreate
) -> CareContractModel:
    """Create or update (upsert) a care contract for a patient.

    Replaces existing visit_slots. All operations run in a single transaction.
    """
    async with get_db() as db:
        now = datetime.now().isoformat()

        # Serialise JSON fields
        days_of_week_json = (
            json.dumps([d.value for d in data.days_of_week])
            if data.days_of_week
            else None
        )
        excluded_dates_json = json.dumps(
            [d.isoformat() for d in data.excluded_dates]
        )

        # Check if contract already exists for this patient
        cursor = await db.execute(
            "SELECT id FROM care_contracts WHERE patient_id = ?", (patient_id,)
        )
        existing = await cursor.fetchone()

        if existing:
            contract_id = existing["id"]
            # Update existing contract
            await db.execute(
                """UPDATE care_contracts
                   SET visit_frequency = ?,
                       days_of_week = ?,
                       visits_per_day = ?,
                       start_date = ?,
                       end_date = ?,
                       excluded_dates = ?,
                       updated_at = ?
                   WHERE id = ?""",
                (
                    data.visit_frequency.value,
                    days_of_week_json,
                    data.visits_per_day,
                    data.start_date.isoformat(),
                    _format_date(data.end_date),
                    excluded_dates_json,
                    now,
                    contract_id,
                ),
            )
            # Delete old visit slots (will be replaced)
            await db.execute(
                "DELETE FROM visit_slots WHERE contract_id = ?", (contract_id,)
            )
        else:
            # Insert new contract
            cursor = await db.execute(
                """INSERT INTO care_contracts
                   (patient_id, visit_frequency, days_of_week, visits_per_day,
                    start_date, end_date, excluded_dates, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    patient_id,
                    data.visit_frequency.value,
                    days_of_week_json,
                    data.visits_per_day,
                    data.start_date.isoformat(),
                    _format_date(data.end_date),
                    excluded_dates_json,
                    now,
                    now,
                ),
            )
            contract_id = cursor.lastrowid

        # Insert new visit slots
        for idx, slot in enumerate(data.visit_slots):
            await db.execute(
                """INSERT INTO visit_slots
                   (contract_id, slot_index, label, earliest_start,
                    latest_start, duration_minutes, required_skills)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    contract_id,
                    idx,
                    slot.label,
                    slot.earliest_start,
                    slot.latest_start,
                    slot.duration_minutes,
                    json.dumps(slot.required_skills),
                ),
            )

        await db.commit()

        # Fetch and return the full contract with slots
        cursor = await db.execute(
            "SELECT * FROM care_contracts WHERE id = ?", (contract_id,)
        )
        contract_row = await cursor.fetchone()

        slot_cursor = await db.execute(
            "SELECT * FROM visit_slots WHERE contract_id = ? ORDER BY slot_index",
            (contract_id,),
        )
        slot_rows = await slot_cursor.fetchall()
        slots = [_row_to_slot(sr) for sr in slot_rows]

        return _row_to_contract(contract_row, slots)


async def delete_contract(patient_id: int) -> None:
    """Delete a patient's care contract and all associated visit_slots (CASCADE).

    Raises KeyError if no contract found for the patient.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM care_contracts WHERE patient_id = ?", (patient_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise KeyError(
                f"No care contract found for patient with id {patient_id}"
            )

        await db.execute("DELETE FROM care_contracts WHERE id = ?", (row["id"],))
        await db.commit()


async def get_all_contracts() -> list[CareContractModel]:
    """Get all care contracts with their visit slots."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM care_contracts ORDER BY id"
        )
        contract_rows = await cursor.fetchall()

        # Fetch all visit slots in one query for efficiency
        slot_cursor = await db.execute(
            "SELECT * FROM visit_slots ORDER BY contract_id, slot_index"
        )
        all_slot_rows = await slot_cursor.fetchall()

        # Group slots by contract_id
        slots_by_contract: dict[int, list[VisitSlotModel]] = {}
        for sr in all_slot_rows:
            cid = sr["contract_id"]
            if cid not in slots_by_contract:
                slots_by_contract[cid] = []
            slots_by_contract[cid].append(_row_to_slot(sr))

        return [
            _row_to_contract(row, slots_by_contract.get(row["id"], []))
            for row in contract_rows
        ]
