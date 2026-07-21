"""Unit tests for the contract repository data access layer."""

import json
from datetime import date
from unittest.mock import patch

import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db.contract_repository import (
    create_or_update_contract,
    delete_contract,
    get_all_contracts,
    get_contract_by_patient,
)
from backend.app.models.contract import (
    CareContractCreate,
    DayOfWeek,
    VisitFrequency,
    VisitSlotCreate,
)


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and a patient."""
    import aiosqlite
    from pathlib import Path

    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(schema_sql)
            await db.commit()

        # Seed minimal test data: one patient
        async with database.get_db() as db:
            await db.execute(
                """INSERT INTO patients (name, address, lat, lng, preferences, priority, continuity_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Patient A", "1 High St", 51.51, -0.11, json.dumps([]), "high", 85.0),
            )
            await db.execute(
                """INSERT INTO patients (name, address, lat, lng, preferences, priority, continuity_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Patient B", "2 Low St", 51.52, -0.12, json.dumps([]), "medium", 70.0),
            )
            await db.commit()

        yield


@pytest.mark.asyncio
async def test_get_contract_by_patient_none(test_db):
    """Returns None when no contract exists for a patient."""
    result = await get_contract_by_patient(1)
    assert result is None


@pytest.mark.asyncio
async def test_create_contract(test_db):
    """Creates a new contract with visit slots."""
    data = CareContractCreate(
        visit_frequency=VisitFrequency.DAILY,
        days_of_week=None,
        visits_per_day=2,
        start_date=date(2025, 1, 1),
        end_date=None,
        excluded_dates=[date(2025, 12, 25)],
        visit_slots=[
            VisitSlotCreate(
                label="Morning",
                earliest_start="07:00",
                latest_start="09:00",
                duration_minutes=30,
                required_skills=["personal_care"],
            ),
            VisitSlotCreate(
                label="Evening",
                earliest_start="17:00",
                latest_start="19:00",
                duration_minutes=45,
                required_skills=[],
            ),
        ],
    )

    result = await create_or_update_contract(1, data)

    assert result.patient_id == 1
    assert result.visit_frequency == VisitFrequency.DAILY
    assert result.days_of_week is None
    assert result.visits_per_day == 2
    assert result.start_date == date(2025, 1, 1)
    assert result.end_date is None
    assert result.excluded_dates == [date(2025, 12, 25)]
    assert len(result.visit_slots) == 2
    assert result.visit_slots[0].label == "Morning"
    assert result.visit_slots[0].earliest_start == "07:00"
    assert result.visit_slots[0].latest_start == "09:00"
    assert result.visit_slots[0].duration_minutes == 30
    assert result.visit_slots[0].required_skills == ["personal_care"]
    assert result.visit_slots[0].slot_index == 0
    assert result.visit_slots[1].label == "Evening"
    assert result.visit_slots[1].slot_index == 1


@pytest.mark.asyncio
async def test_update_contract(test_db):
    """Updating an existing contract replaces slots."""
    # Create initial contract
    data = CareContractCreate(
        visit_frequency=VisitFrequency.DAILY,
        visits_per_day=1,
        start_date=date(2025, 1, 1),
        excluded_dates=[],
        visit_slots=[
            VisitSlotCreate(
                label="Morning",
                earliest_start="07:00",
                latest_start="09:00",
                duration_minutes=30,
                required_skills=[],
            ),
        ],
    )
    await create_or_update_contract(1, data)

    # Update with different data
    updated_data = CareContractCreate(
        visit_frequency=VisitFrequency.SPECIFIC_DAYS,
        days_of_week=[DayOfWeek.MON, DayOfWeek.WED, DayOfWeek.FRI],
        visits_per_day=1,
        start_date=date(2025, 2, 1),
        end_date=date(2025, 12, 31),
        excluded_dates=[date(2025, 4, 18)],
        visit_slots=[
            VisitSlotCreate(
                label="Afternoon",
                earliest_start="13:00",
                latest_start="15:00",
                duration_minutes=60,
                required_skills=["medication"],
            ),
        ],
    )
    result = await create_or_update_contract(1, updated_data)

    assert result.visit_frequency == VisitFrequency.SPECIFIC_DAYS
    assert result.days_of_week == [DayOfWeek.MON, DayOfWeek.WED, DayOfWeek.FRI]
    assert result.start_date == date(2025, 2, 1)
    assert result.end_date == date(2025, 12, 31)
    assert result.excluded_dates == [date(2025, 4, 18)]
    assert len(result.visit_slots) == 1
    assert result.visit_slots[0].label == "Afternoon"
    assert result.visit_slots[0].duration_minutes == 60


@pytest.mark.asyncio
async def test_get_contract_by_patient_after_create(test_db):
    """Fetching a contract after creation returns the correct data."""
    data = CareContractCreate(
        visit_frequency=VisitFrequency.WEEKDAYS_ONLY,
        visits_per_day=1,
        start_date=date(2025, 3, 1),
        excluded_dates=[],
        visit_slots=[
            VisitSlotCreate(
                label="Midday",
                earliest_start="11:00",
                latest_start="13:00",
                duration_minutes=45,
                required_skills=["personal_care"],
            ),
        ],
    )
    await create_or_update_contract(1, data)

    result = await get_contract_by_patient(1)
    assert result is not None
    assert result.patient_id == 1
    assert result.visit_frequency == VisitFrequency.WEEKDAYS_ONLY
    assert len(result.visit_slots) == 1
    assert result.visit_slots[0].label == "Midday"


@pytest.mark.asyncio
async def test_delete_contract(test_db):
    """Deleting a contract removes it and its slots."""
    data = CareContractCreate(
        visit_frequency=VisitFrequency.DAILY,
        visits_per_day=1,
        start_date=date(2025, 1, 1),
        excluded_dates=[],
        visit_slots=[
            VisitSlotCreate(
                label="Morning",
                earliest_start="07:00",
                latest_start="09:00",
                duration_minutes=30,
                required_skills=[],
            ),
        ],
    )
    await create_or_update_contract(1, data)

    await delete_contract(1)

    result = await get_contract_by_patient(1)
    assert result is None


@pytest.mark.asyncio
async def test_delete_contract_not_found(test_db):
    """Deleting a non-existent contract raises KeyError."""
    with pytest.raises(KeyError):
        await delete_contract(999)


@pytest.mark.asyncio
async def test_get_all_contracts(test_db):
    """get_all_contracts returns all contracts with their slots."""
    data1 = CareContractCreate(
        visit_frequency=VisitFrequency.DAILY,
        visits_per_day=1,
        start_date=date(2025, 1, 1),
        excluded_dates=[],
        visit_slots=[
            VisitSlotCreate(
                label="Morning",
                earliest_start="07:00",
                latest_start="09:00",
                duration_minutes=30,
                required_skills=[],
            ),
        ],
    )
    data2 = CareContractCreate(
        visit_frequency=VisitFrequency.WEEKLY,
        visits_per_day=2,
        start_date=date(2025, 1, 1),
        excluded_dates=[],
        visit_slots=[
            VisitSlotCreate(
                label="AM",
                earliest_start="08:00",
                latest_start="10:00",
                duration_minutes=30,
                required_skills=[],
            ),
            VisitSlotCreate(
                label="PM",
                earliest_start="14:00",
                latest_start="16:00",
                duration_minutes=45,
                required_skills=[],
            ),
        ],
    )

    await create_or_update_contract(1, data1)
    await create_or_update_contract(2, data2)

    results = await get_all_contracts()
    assert len(results) == 2
    assert results[0].patient_id == 1
    assert len(results[0].visit_slots) == 1
    assert results[1].patient_id == 2
    assert len(results[1].visit_slots) == 2
