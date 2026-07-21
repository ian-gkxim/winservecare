"""Unit tests for the data access layer (repositories)."""

import json
from unittest.mock import patch

import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.db.repositories import (
    cancel_visit,
    cancel_visit_by_id,
    compare_scenarios,
    create_exception,
    create_scenario,
    create_skill,
    delete_visits_by_date,
    get_carers,
    get_config,
    get_constraints,
    get_exceptions,
    get_kpis,
    get_patients,
    get_scenario,
    get_scenarios,
    get_skills,
    get_visits,
    get_visits_by_date,
    insert_generated_visits,
    resolve_exception,
    update_carer,
    update_config,
    update_constraint,
    update_patient,
)
from backend.app.models.carer import CarerUpdate
from backend.app.models.constraint import ConstraintUpdate
from backend.app.models.patient import PatientUpdate


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and seed data."""
    import aiosqlite
    from pathlib import Path

    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    # Patch DB_PATH for the test - patch both places it's used
    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        # Manually apply schema without calling init_db (which seeds full mock data)
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(schema_sql)
            await db.commit()

        # Seed minimal test data
        async with database.get_db() as db:
            # Insert carers
            await db.execute(
                """INSERT INTO carers (name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Alice", 51.5, -0.1, json.dumps(["personal_care", "medication"]), 8.0, 6.0, 30),
            )
            await db.execute(
                """INSERT INTO carers (name, home_lat, home_lng, skills, max_working_hours, max_continuous_hours, min_break_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Bob", 51.6, -0.2, json.dumps(["personal_care"]), 10.0, 6.0, 30),
            )
            # Insert patients
            await db.execute(
                """INSERT INTO patients (name, address, lat, lng, preferences, priority, continuity_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("Patient A", "1 High St", 51.51, -0.11, json.dumps(["morning"]), "high", 85.0),
            )
            # Insert visits
            await db.execute(
                """INSERT INTO visits (patient_id, duration_minutes, window_start, window_end, required_skills, preferred_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (1, 30, "08:00", "10:00", json.dumps(["personal_care"]), "09:00"),
            )
            await db.execute(
                """INSERT INTO visits (patient_id, duration_minutes, window_start, window_end, required_skills)
                   VALUES (?, ?, ?, ?, ?)""",
                (1, 45, "14:00", "16:00", json.dumps(["medication"])),
            )
            # Insert skills
            await db.execute("INSERT INTO skills (name) VALUES (?)", ("personal_care",))
            await db.execute("INSERT INTO skills (name) VALUES (?)", ("medication",))
            # Insert constraints
            await db.execute(
                "INSERT INTO constraints (name, description, is_enabled) VALUES (?, ?, ?)",
                ("skill_match", "Carer must have required skills", 1),
            )
            # Insert an exception
            await db.execute(
                """INSERT INTO exceptions (description, constraint_names, affected_entity_type, affected_entity_id)
                   VALUES (?, ?, ?, ?)""",
                ("Skill mismatch", json.dumps(["skill_match"]), "visit", 1),
            )
            await db.commit()
        yield


# --- Carer tests ---


@pytest.mark.asyncio
async def test_get_carers(test_db):
    carers = await get_carers()
    assert len(carers) == 2
    assert carers[0].name == "Alice"
    assert carers[0].skills == ["personal_care", "medication"]
    assert carers[1].name == "Bob"


@pytest.mark.asyncio
async def test_update_carer_success(test_db):
    updated = await update_carer(1, CarerUpdate(name="Alice Smith", max_working_hours=9.0))
    assert updated.name == "Alice Smith"
    assert updated.max_working_hours == 9.0
    # Skills should remain unchanged
    assert updated.skills == ["personal_care", "medication"]


@pytest.mark.asyncio
async def test_update_carer_not_found(test_db):
    with pytest.raises(KeyError, match="not found"):
        await update_carer(999, CarerUpdate(name="Ghost"))


@pytest.mark.asyncio
async def test_update_carer_empty_name(test_db):
    with pytest.raises(ValueError, match="cannot be empty"):
        await update_carer(1, CarerUpdate(name="   "))


# --- Patient tests ---


@pytest.mark.asyncio
async def test_get_patients(test_db):
    patients = await get_patients()
    assert len(patients) == 1
    assert patients[0].name == "Patient A"
    assert patients[0].priority.value == "high"
    assert patients[0].preferences == ["morning"]


@pytest.mark.asyncio
async def test_update_patient_success(test_db):
    updated = await update_patient(1, PatientUpdate(name="Patient A Updated"))
    assert updated.name == "Patient A Updated"


@pytest.mark.asyncio
async def test_update_patient_not_found(test_db):
    with pytest.raises(KeyError, match="not found"):
        await update_patient(999, PatientUpdate(name="Ghost"))


# --- Visit tests ---


@pytest.mark.asyncio
async def test_get_visits(test_db):
    visits = await get_visits()
    assert len(visits) == 2
    assert visits[0].duration_minutes == 30
    assert visits[0].required_skills == ["personal_care"]
    assert visits[0].is_cancelled is False


@pytest.mark.asyncio
async def test_cancel_visit_success(test_db):
    await cancel_visit(1)
    visits = await get_visits()
    cancelled = [v for v in visits if v.id == 1][0]
    assert cancelled.is_cancelled is True


@pytest.mark.asyncio
async def test_cancel_visit_not_found(test_db):
    with pytest.raises(KeyError, match="not found"):
        await cancel_visit(999)


# --- Skill tests ---


@pytest.mark.asyncio
async def test_get_skills_with_counts(test_db):
    skills = await get_skills()
    assert len(skills) == 2
    # personal_care is used by 2 carers (Alice, Bob) and 1 visit
    pc = next(s for s in skills if s["name"] == "personal_care")
    assert pc["carer_count"] == 2
    assert pc["visit_count"] == 1
    # medication is used by 1 carer (Alice) and 1 visit
    med = next(s for s in skills if s["name"] == "medication")
    assert med["carer_count"] == 1
    assert med["visit_count"] == 1


@pytest.mark.asyncio
async def test_create_skill_success(test_db):
    skill = await create_skill("mobility")
    assert skill.name == "mobility"
    assert skill.id is not None


@pytest.mark.asyncio
async def test_create_skill_duplicate(test_db):
    with pytest.raises(ValueError, match="already exists"):
        await create_skill("personal_care")


@pytest.mark.asyncio
async def test_create_skill_empty_name(test_db):
    with pytest.raises(ValueError, match="between 1 and 100"):
        await create_skill("")


@pytest.mark.asyncio
async def test_create_skill_too_long(test_db):
    with pytest.raises(ValueError, match="between 1 and 100"):
        await create_skill("x" * 101)


# --- Constraint tests ---


@pytest.mark.asyncio
async def test_get_constraints(test_db):
    constraints = await get_constraints()
    assert len(constraints) == 1
    assert constraints[0].name == "skill_match"
    assert constraints[0].is_enabled is True


@pytest.mark.asyncio
async def test_update_constraint_disable(test_db):
    updated = await update_constraint(1, ConstraintUpdate(is_enabled=False))
    assert updated.is_enabled is False


@pytest.mark.asyncio
async def test_update_constraint_not_found(test_db):
    with pytest.raises(KeyError, match="not found"):
        await update_constraint(999, ConstraintUpdate(is_enabled=False))


# --- Scenario tests ---


@pytest.mark.asyncio
async def test_create_and_get_scenario(test_db):
    scenario = await create_scenario(
        name="Test Scenario",
        total_travel_hours=2.5,
        total_mileage=30.0,
        total_overtime_hours=0.5,
        continuity_score=75.0,
        objective_score=150.0,
        assignments=[{"visit_id": 1, "carer_id": 1}],
        routes=[{"carer_id": 1, "stops": [], "total_travel_minutes": 60, "total_mileage": 15.0, "total_cost": 25.0}],
    )
    assert scenario.name == "Test Scenario"
    assert scenario.id is not None

    # Retrieve by ID
    fetched = await get_scenario(scenario.id)
    assert fetched.name == "Test Scenario"
    assert fetched.total_travel_hours == 2.5


@pytest.mark.asyncio
async def test_create_scenario_duplicate_name(test_db):
    await create_scenario(
        name="Dup", total_travel_hours=1.0, total_mileage=10.0,
        total_overtime_hours=0.0, continuity_score=50.0,
        objective_score=100.0, assignments=[], routes=[],
    )
    with pytest.raises(ValueError, match="already exists"):
        await create_scenario(
            name="Dup", total_travel_hours=2.0, total_mileage=20.0,
            total_overtime_hours=0.0, continuity_score=60.0,
            objective_score=200.0, assignments=[], routes=[],
        )


@pytest.mark.asyncio
async def test_create_scenario_invalid_name(test_db):
    with pytest.raises(ValueError, match="between 1 and 100"):
        await create_scenario(
            name="", total_travel_hours=1.0, total_mileage=10.0,
            total_overtime_hours=0.0, continuity_score=50.0,
            objective_score=100.0, assignments=[], routes=[],
        )


@pytest.mark.asyncio
async def test_get_scenario_not_found(test_db):
    with pytest.raises(KeyError, match="not found"):
        await get_scenario(999)


@pytest.mark.asyncio
async def test_compare_scenarios(test_db):
    s1 = await create_scenario(
        name="S1", total_travel_hours=2.0, total_mileage=20.0,
        total_overtime_hours=0.5, continuity_score=70.0,
        objective_score=120.0, assignments=[], routes=[],
    )
    s2 = await create_scenario(
        name="S2", total_travel_hours=1.5, total_mileage=15.0,
        total_overtime_hours=0.0, continuity_score=80.0,
        objective_score=100.0, assignments=[], routes=[],
    )
    result = await compare_scenarios(s1.id, s2.id)
    assert result["scenario_1"].name == "S1"
    assert result["scenario_2"].name == "S2"


# --- Exception tests ---


@pytest.mark.asyncio
async def test_get_exceptions(test_db):
    exceptions = await get_exceptions()
    assert len(exceptions) == 1
    assert exceptions[0].description == "Skill mismatch"
    assert exceptions[0].is_resolved is False


@pytest.mark.asyncio
async def test_resolve_exception_success(test_db):
    resolved = await resolve_exception(1)
    assert resolved.is_resolved is True
    assert resolved.resolved_at is not None


@pytest.mark.asyncio
async def test_resolve_exception_already_resolved(test_db):
    await resolve_exception(1)
    with pytest.raises(ValueError, match="already resolved"):
        await resolve_exception(1)


@pytest.mark.asyncio
async def test_resolve_exception_not_found(test_db):
    with pytest.raises(KeyError, match="not found"):
        await resolve_exception(999)


# --- Config tests ---


@pytest.mark.asyncio
async def test_get_config_empty(test_db):
    config = await get_config()
    assert config == {}


@pytest.mark.asyncio
async def test_update_and_get_config(test_db):
    await update_config("google_maps_api_key", "test_key_123")
    config = await get_config()
    assert config["google_maps_api_key"] == "test_key_123"


@pytest.mark.asyncio
async def test_update_config_overwrite(test_db):
    await update_config("google_maps_api_key", "old_key")
    await update_config("google_maps_api_key", "new_key")
    config = await get_config()
    assert config["google_maps_api_key"] == "new_key"


# --- KPI tests ---


@pytest.mark.asyncio
async def test_get_kpis_no_scenario(test_db):
    kpis = await get_kpis()
    assert kpis.total_visits == 2
    assert kpis.carers_available == 2
    assert kpis.travel_hours == 0.0
    assert kpis.mileage == 0.0
    assert kpis.overtime == 0.0
    # Continuity comes from patient average (85.0)
    assert kpis.continuity_score == 85.0


@pytest.mark.asyncio
async def test_get_kpis_with_scenario(test_db):
    await create_scenario(
        name="Latest", total_travel_hours=3.5, total_mileage=45.2,
        total_overtime_hours=1.2, continuity_score=78.0,
        objective_score=130.0, assignments=[], routes=[],
    )
    kpis = await get_kpis()
    assert kpis.total_visits == 2
    assert kpis.carers_available == 2
    assert kpis.travel_hours == 3.5
    assert kpis.mileage == 45.2
    assert kpis.overtime == 1.2
    assert kpis.continuity_score == 78.0


# --- Create exception tests ---


@pytest.mark.asyncio
async def test_create_exception_success(test_db):
    exc = await create_exception(
        description="Visit cannot be assigned due to time window conflict",
        constraint_names=["time_window", "working_hours"],
        affected_entity_type="visit",
        affected_entity_id=1,
    )
    assert exc.id is not None
    assert exc.description == "Visit cannot be assigned due to time window conflict"
    assert exc.constraint_names == ["time_window", "working_hours"]
    assert exc.affected_entity_type == "visit"
    assert exc.affected_entity_id == 1
    assert exc.is_resolved is False
    assert exc.resolved_at is None
    assert exc.timestamp is not None


@pytest.mark.asyncio
async def test_create_exception_invalid_entity_type(test_db):
    with pytest.raises(ValueError, match="affected_entity_type must be"):
        await create_exception(
            description="Invalid type",
            constraint_names=["skill_match"],
            affected_entity_type="patient",
            affected_entity_id=1,
        )


@pytest.mark.asyncio
async def test_create_exception_appears_in_get_exceptions(test_db):
    await create_exception(
        description="New infeasibility",
        constraint_names=["skill_match"],
        affected_entity_type="visit",
        affected_entity_id=2,
    )
    exceptions = await get_exceptions()
    # 1 from seed + 1 new
    assert len(exceptions) == 2
    descriptions = [e.description for e in exceptions]
    assert "New infeasibility" in descriptions


# --- Visit generation repository tests ---


@pytest_asyncio.fixture
async def test_db_with_generated_visits(test_db):
    """Extend test_db with generated visits that have target_date and contract_id."""
    async with database.get_db() as db:
        # Insert a care_contract for patient 1
        await db.execute(
            """INSERT INTO care_contracts
               (patient_id, visit_frequency, visits_per_day, start_date, excluded_dates)
               VALUES (?, ?, ?, ?, ?)""",
            (1, "daily", 2, "2025-01-01", json.dumps([])),
        )
        # Insert generated visits for 2025-03-15
        await db.execute(
            """INSERT INTO visits
               (patient_id, duration_minutes, window_start, window_end, required_skills, preferred_time, target_date, contract_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (1, 30, "08:00", "10:00", json.dumps(["personal_care"]), "09:00", "2025-03-15", 1),
        )
        await db.execute(
            """INSERT INTO visits
               (patient_id, duration_minutes, window_start, window_end, required_skills, target_date, contract_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, 45, "14:00", "16:00", json.dumps(["medication"]), "2025-03-15", 1),
        )
        # Insert a visit for a different date
        await db.execute(
            """INSERT INTO visits
               (patient_id, duration_minutes, window_start, window_end, required_skills, target_date, contract_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, 60, "10:00", "12:00", json.dumps([]), "2025-03-16", 1),
        )
        await db.commit()
    yield


@pytest.mark.asyncio
async def test_get_visits_by_date_returns_visits(test_db_with_generated_visits):
    visits = await get_visits_by_date("2025-03-15")
    assert len(visits) == 2
    assert visits[0]["patient_name"] == "Patient A"
    assert visits[0]["duration_minutes"] == 30
    assert visits[0]["window_start"] == "08:00"
    assert visits[0]["required_skills"] == ["personal_care"]
    assert visits[0]["target_date"] == "2025-03-15"
    assert visits[0]["contract_id"] == 1
    assert visits[0]["is_cancelled"] is False


@pytest.mark.asyncio
async def test_get_visits_by_date_empty(test_db_with_generated_visits):
    visits = await get_visits_by_date("2025-01-01")
    assert visits == []


@pytest.mark.asyncio
async def test_get_visits_by_date_different_date(test_db_with_generated_visits):
    visits = await get_visits_by_date("2025-03-16")
    assert len(visits) == 1
    assert visits[0]["duration_minutes"] == 60


@pytest.mark.asyncio
async def test_insert_generated_visits_success(test_db):
    visits_to_insert = [
        {
            "patient_id": 1,
            "duration_minutes": 30,
            "window_start": "08:00",
            "window_end": "10:00",
            "required_skills": ["personal_care"],
            "preferred_time": "09:00",
            "target_date": "2025-04-01",
            "contract_id": None,
        },
        {
            "patient_id": 1,
            "duration_minutes": 45,
            "window_start": "14:00",
            "window_end": "16:00",
            "required_skills": ["medication"],
            "preferred_time": None,
            "target_date": "2025-04-01",
            "contract_id": None,
        },
    ]
    ids = await insert_generated_visits(visits_to_insert)
    assert len(ids) == 2
    assert all(isinstance(id_, int) for id_ in ids)

    # Verify they were inserted
    visits = await get_visits_by_date("2025-04-01")
    assert len(visits) == 2
    assert visits[0]["duration_minutes"] == 30
    assert visits[1]["duration_minutes"] == 45


@pytest.mark.asyncio
async def test_insert_generated_visits_empty_list(test_db):
    ids = await insert_generated_visits([])
    assert ids == []


@pytest.mark.asyncio
async def test_delete_visits_by_date_success(test_db_with_generated_visits):
    count = await delete_visits_by_date("2025-03-15")
    assert count == 2

    # Verify deletion
    visits = await get_visits_by_date("2025-03-15")
    assert visits == []

    # Other dates unaffected
    visits = await get_visits_by_date("2025-03-16")
    assert len(visits) == 1


@pytest.mark.asyncio
async def test_delete_visits_by_date_no_visits(test_db):
    count = await delete_visits_by_date("2099-01-01")
    assert count == 0


@pytest.mark.asyncio
async def test_cancel_visit_by_id_success(test_db_with_generated_visits):
    # Get visits for the date to find an ID
    visits = await get_visits_by_date("2025-03-15")
    visit_id = visits[0]["id"]

    result = await cancel_visit_by_id(visit_id)
    assert result["is_cancelled"] is True
    assert result["id"] == visit_id
    assert result["patient_name"] == "Patient A"
    assert result["duration_minutes"] == 30


@pytest.mark.asyncio
async def test_cancel_visit_by_id_not_found(test_db):
    with pytest.raises(KeyError, match="not found"):
        await cancel_visit_by_id(999)


@pytest.mark.asyncio
async def test_cancel_visit_by_id_does_not_affect_others(test_db_with_generated_visits):
    visits = await get_visits_by_date("2025-03-15")
    visit_id = visits[0]["id"]

    await cancel_visit_by_id(visit_id)

    # Check the other visit is still scheduled
    updated_visits = await get_visits_by_date("2025-03-15")
    other = [v for v in updated_visits if v["id"] != visit_id][0]
    assert other["is_cancelled"] is False
