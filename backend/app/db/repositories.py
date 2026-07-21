"""Data access layer providing async CRUD operations for all entities."""

import json
from datetime import datetime

from backend.app.db.database import get_db
from backend.app.models.carer import CarerModel, CarerUpdate
from backend.app.models.config import ConfigModel
from backend.app.models.constraint import ConstraintModel, ConstraintUpdate
from backend.app.models.exception import ExceptionModel
from backend.app.models.optimisation import KPIMetrics
from backend.app.models.patient import PatientModel, PatientUpdate
from backend.app.models.scenario import ScenarioModel
from backend.app.models.skill import SkillModel
from backend.app.models.visit import VisitModel


# --- Carer operations ---


async def get_carers() -> list[CarerModel]:
    """Retrieve all carers from the database."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM carers ORDER BY id")
        rows = await cursor.fetchall()
        return [
            CarerModel(
                id=row["id"],
                name=row["name"],
                home_lat=row["home_lat"],
                home_lng=row["home_lng"],
                skills=json.loads(row["skills"]),
                max_working_hours=row["max_working_hours"],
                max_continuous_hours=row["max_continuous_hours"],
                min_break_minutes=row["min_break_minutes"],
            )
            for row in rows
        ]


async def update_carer(carer_id: int, data: CarerUpdate) -> CarerModel:
    """Update a carer record. Raises KeyError if not found."""
    async with get_db() as db:
        # Check existence
        cursor = await db.execute("SELECT id FROM carers WHERE id = ?", (carer_id,))
        if not await cursor.fetchone():
            raise KeyError(f"Carer with id {carer_id} not found")

        # Build update fields
        updates = {}
        if data.name is not None:
            if not data.name.strip():
                raise ValueError("Carer name cannot be empty")
            updates["name"] = data.name
        if data.home_lat is not None:
            updates["home_lat"] = data.home_lat
        if data.home_lng is not None:
            updates["home_lng"] = data.home_lng
        if data.skills is not None:
            updates["skills"] = json.dumps(data.skills)
        if data.max_working_hours is not None:
            updates["max_working_hours"] = data.max_working_hours
        if data.max_continuous_hours is not None:
            updates["max_continuous_hours"] = data.max_continuous_hours
        if data.min_break_minutes is not None:
            updates["min_break_minutes"] = data.min_break_minutes

        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [carer_id]
            await db.execute(
                f"UPDATE carers SET {set_clause} WHERE id = ?", values
            )
            await db.commit()

        # Return updated record
        cursor = await db.execute("SELECT * FROM carers WHERE id = ?", (carer_id,))
        row = await cursor.fetchone()
        return CarerModel(
            id=row["id"],
            name=row["name"],
            home_lat=row["home_lat"],
            home_lng=row["home_lng"],
            skills=json.loads(row["skills"]),
            max_working_hours=row["max_working_hours"],
            max_continuous_hours=row["max_continuous_hours"],
            min_break_minutes=row["min_break_minutes"],
        )


# --- Patient operations ---


async def get_patients() -> list[PatientModel]:
    """Retrieve all patients from the database."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM patients ORDER BY id")
        rows = await cursor.fetchall()
        return [
            PatientModel(
                id=row["id"],
                name=row["name"],
                address=row["address"],
                lat=row["lat"],
                lng=row["lng"],
                preferences=json.loads(row["preferences"]),
                priority=row["priority"],
                continuity_score=row["continuity_score"],
                usual_carer_id=row["usual_carer_id"],
                preferred_carer_id=row["preferred_carer_id"],
            )
            for row in rows
        ]


async def update_patient(patient_id: int, data: PatientUpdate) -> PatientModel:
    """Update a patient record. Raises KeyError if not found."""
    async with get_db() as db:
        # Check existence
        cursor = await db.execute(
            "SELECT id FROM patients WHERE id = ?", (patient_id,)
        )
        if not await cursor.fetchone():
            raise KeyError(f"Patient with id {patient_id} not found")

        # Build update fields
        updates = {}
        if data.name is not None:
            if not data.name.strip():
                raise ValueError("Patient name cannot be empty")
            updates["name"] = data.name
        if data.address is not None:
            updates["address"] = data.address
        if data.lat is not None:
            updates["lat"] = data.lat
        if data.lng is not None:
            updates["lng"] = data.lng
        if data.preferences is not None:
            updates["preferences"] = json.dumps(data.preferences)
        if data.priority is not None:
            updates["priority"] = data.priority.value
        if data.usual_carer_id is not None:
            updates["usual_carer_id"] = data.usual_carer_id
        if data.preferred_carer_id is not None:
            updates["preferred_carer_id"] = data.preferred_carer_id

        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [patient_id]
            await db.execute(
                f"UPDATE patients SET {set_clause} WHERE id = ?", values
            )
            await db.commit()

        # Return updated record
        cursor = await db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        )
        row = await cursor.fetchone()
        return PatientModel(
            id=row["id"],
            name=row["name"],
            address=row["address"],
            lat=row["lat"],
            lng=row["lng"],
            preferences=json.loads(row["preferences"]),
            priority=row["priority"],
            continuity_score=row["continuity_score"],
            usual_carer_id=row["usual_carer_id"],
            preferred_carer_id=row["preferred_carer_id"],
        )


# --- Visit operations ---


async def get_visits() -> list[VisitModel]:
    """Retrieve all visits from the database."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM visits ORDER BY id")
        rows = await cursor.fetchall()
        return [
            VisitModel(
                id=row["id"],
                patient_id=row["patient_id"],
                duration_minutes=row["duration_minutes"],
                window_start=row["window_start"],
                window_end=row["window_end"],
                required_skills=json.loads(row["required_skills"]),
                preferred_time=row["preferred_time"],
                is_cancelled=bool(row["is_cancelled"]),
            )
            for row in rows
        ]


async def cancel_visit(visit_id: int) -> None:
    """Cancel a visit by setting is_cancelled=1. Raises KeyError if not found."""
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM visits WHERE id = ?", (visit_id,))
        if not await cursor.fetchone():
            raise KeyError(f"Visit with id {visit_id} not found")

        await db.execute(
            "UPDATE visits SET is_cancelled = 1, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), visit_id),
        )
        await db.commit()


async def get_visits_by_date(target_date: str) -> list[dict]:
    """Get all visits for a target date with patient name.

    Returns dicts with: id, patient_id, patient_name, duration_minutes,
    window_start, window_end, required_skills, preferred_time, is_cancelled,
    target_date, contract_id.

    Args:
        target_date: Date string in YYYY-MM-DD format.

    Returns:
        List of visit dicts including patient_name from LEFT JOIN with patients.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT v.id, v.patient_id, p.name AS patient_name,
                      v.duration_minutes, v.window_start, v.window_end,
                      v.required_skills, v.preferred_time, v.is_cancelled,
                      v.target_date, v.contract_id
               FROM visits v
               LEFT JOIN patients p ON v.patient_id = p.id
               WHERE v.target_date = ?
               ORDER BY v.id""",
            (target_date,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "patient_id": row["patient_id"],
                "patient_name": row["patient_name"],
                "duration_minutes": row["duration_minutes"],
                "window_start": row["window_start"],
                "window_end": row["window_end"],
                "required_skills": json.loads(row["required_skills"]),
                "preferred_time": row["preferred_time"],
                "is_cancelled": bool(row["is_cancelled"]),
                "target_date": row["target_date"],
                "contract_id": row["contract_id"],
            }
            for row in rows
        ]


async def insert_generated_visits(visits: list[dict]) -> list[int]:
    """Insert multiple generated visits in a single transaction.

    Each visit dict should have: patient_id, duration_minutes, window_start,
    window_end, required_skills (list), preferred_time, target_date, contract_id.

    Args:
        visits: List of visit dicts to insert.

    Returns:
        List of inserted visit IDs.
    """
    if not visits:
        return []

    async with get_db() as db:
        inserted_ids = []
        for visit in visits:
            cursor = await db.execute(
                """INSERT INTO visits
                   (patient_id, duration_minutes, window_start, window_end,
                    required_skills, preferred_time, target_date, contract_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    visit["patient_id"],
                    visit["duration_minutes"],
                    visit["window_start"],
                    visit["window_end"],
                    json.dumps(visit["required_skills"]),
                    visit.get("preferred_time"),
                    visit["target_date"],
                    visit.get("contract_id"),
                ),
            )
            inserted_ids.append(cursor.lastrowid)
        await db.commit()
        return inserted_ids


async def delete_visits_by_date(target_date: str) -> int:
    """Delete all visits for a specific target_date.

    Args:
        target_date: Date string in YYYY-MM-DD format.

    Returns:
        Count of deleted rows.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM visits WHERE target_date = ?",
            (target_date,),
        )
        await db.commit()
        return cursor.rowcount


async def cancel_visit_by_id(visit_id: int) -> dict:
    """Cancel a specific visit (set is_cancelled=1). Returns the updated visit dict.

    Args:
        visit_id: ID of the visit to cancel.

    Returns:
        Dict with all visit fields including patient_name from LEFT JOIN.

    Raises:
        KeyError: If visit with the given ID is not found.
    """
    async with get_db() as db:
        # Check existence
        cursor = await db.execute("SELECT id FROM visits WHERE id = ?", (visit_id,))
        if not await cursor.fetchone():
            raise KeyError(f"Visit with id {visit_id} not found")

        # Set is_cancelled
        await db.execute(
            "UPDATE visits SET is_cancelled = 1, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), visit_id),
        )
        await db.commit()

        # Return updated record with patient name
        cursor = await db.execute(
            """SELECT v.id, v.patient_id, p.name AS patient_name,
                      v.duration_minutes, v.window_start, v.window_end,
                      v.required_skills, v.preferred_time, v.is_cancelled,
                      v.target_date, v.contract_id
               FROM visits v
               LEFT JOIN patients p ON v.patient_id = p.id
               WHERE v.id = ?""",
            (visit_id,),
        )
        row = await cursor.fetchone()
        return {
            "id": row["id"],
            "patient_id": row["patient_id"],
            "patient_name": row["patient_name"],
            "duration_minutes": row["duration_minutes"],
            "window_start": row["window_start"],
            "window_end": row["window_end"],
            "required_skills": json.loads(row["required_skills"]),
            "preferred_time": row["preferred_time"],
            "is_cancelled": bool(row["is_cancelled"]),
            "target_date": row["target_date"],
            "contract_id": row["contract_id"],
        }


# --- Skill operations ---


async def get_skills() -> list[dict]:
    """Retrieve all skills with usage counts (carers + visits using each skill)."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM skills ORDER BY id")
        skill_rows = await cursor.fetchall()

        # Get all carers' skills for counting
        carer_cursor = await db.execute("SELECT skills FROM carers")
        carer_rows = await carer_cursor.fetchall()

        # Get all visits' required_skills for counting
        visit_cursor = await db.execute("SELECT required_skills FROM visits")
        visit_rows = await visit_cursor.fetchall()

        # Count skill usage
        results = []
        for skill_row in skill_rows:
            skill_name = skill_row["name"]
            carer_count = sum(
                1
                for row in carer_rows
                if skill_name in json.loads(row["skills"])
            )
            visit_count = sum(
                1
                for row in visit_rows
                if skill_name in json.loads(row["required_skills"])
            )
            results.append(
                {
                    "id": skill_row["id"],
                    "name": skill_name,
                    "carer_count": carer_count,
                    "visit_count": visit_count,
                }
            )

        return results


async def create_skill(name: str) -> SkillModel:
    """Create a new skill. Raises ValueError for invalid/duplicate names."""
    name = name.strip()
    if not name or len(name) > 100:
        raise ValueError("Skill name must be between 1 and 100 characters")

    async with get_db() as db:
        # Check uniqueness
        cursor = await db.execute("SELECT id FROM skills WHERE name = ?", (name,))
        if await cursor.fetchone():
            raise ValueError(f"Skill with name '{name}' already exists")

        cursor = await db.execute(
            "INSERT INTO skills (name) VALUES (?)", (name,)
        )
        await db.commit()

        return SkillModel(id=cursor.lastrowid, name=name)


# --- Constraint operations ---


async def get_constraints() -> list[ConstraintModel]:
    """Retrieve all constraints from the database."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM constraints ORDER BY id")
        rows = await cursor.fetchall()
        return [
            ConstraintModel(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                is_enabled=bool(row["is_enabled"]),
            )
            for row in rows
        ]


async def update_constraint(
    constraint_id: int, data: ConstraintUpdate
) -> ConstraintModel:
    """Update a constraint's is_enabled field. Raises KeyError if not found."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM constraints WHERE id = ?", (constraint_id,)
        )
        if not await cursor.fetchone():
            raise KeyError(f"Constraint with id {constraint_id} not found")

        await db.execute(
            "UPDATE constraints SET is_enabled = ?, updated_at = ? WHERE id = ?",
            (int(data.is_enabled), datetime.now().isoformat(), constraint_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM constraints WHERE id = ?", (constraint_id,)
        )
        row = await cursor.fetchone()
        return ConstraintModel(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            is_enabled=bool(row["is_enabled"]),
        )


# --- Scenario operations ---


async def get_scenarios() -> list[ScenarioModel]:
    """Retrieve all scenarios from the database."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM scenarios ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [
            ScenarioModel(
                id=row["id"],
                name=row["name"],
                total_travel_hours=row["total_travel_hours"],
                total_mileage=row["total_mileage"],
                total_overtime_hours=row["total_overtime_hours"],
                continuity_score=row["continuity_score"],
                objective_score=row["objective_score"],
                assignments=json.loads(row["assignments"]),
                routes=json.loads(row["routes"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]


async def create_scenario(
    name: str,
    total_travel_hours: float,
    total_mileage: float,
    total_overtime_hours: float,
    continuity_score: float,
    objective_score: float,
    assignments: list[dict],
    routes: list[dict],
) -> ScenarioModel:
    """Create a new scenario. Raises ValueError for invalid/duplicate names."""
    name = name.strip()
    if not name or len(name) > 100:
        raise ValueError("Scenario name must be between 1 and 100 characters")

    async with get_db() as db:
        # Check uniqueness
        cursor = await db.execute(
            "SELECT id FROM scenarios WHERE name = ?", (name,)
        )
        if await cursor.fetchone():
            raise ValueError(f"Scenario with name '{name}' already exists")

        cursor = await db.execute(
            """INSERT INTO scenarios
               (name, total_travel_hours, total_mileage, total_overtime_hours,
                continuity_score, objective_score, assignments, routes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                total_travel_hours,
                total_mileage,
                total_overtime_hours,
                continuity_score,
                objective_score,
                json.dumps(assignments),
                json.dumps(routes),
            ),
        )
        await db.commit()

        # Return the created scenario
        new_cursor = await db.execute(
            "SELECT * FROM scenarios WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return ScenarioModel(
            id=row["id"],
            name=row["name"],
            total_travel_hours=row["total_travel_hours"],
            total_mileage=row["total_mileage"],
            total_overtime_hours=row["total_overtime_hours"],
            continuity_score=row["continuity_score"],
            objective_score=row["objective_score"],
            assignments=json.loads(row["assignments"]),
            routes=json.loads(row["routes"]),
            created_at=row["created_at"],
        )


async def get_scenario(scenario_id: int) -> ScenarioModel:
    """Retrieve a single scenario by ID. Raises KeyError if not found."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise KeyError(f"Scenario with id {scenario_id} not found")

        return ScenarioModel(
            id=row["id"],
            name=row["name"],
            total_travel_hours=row["total_travel_hours"],
            total_mileage=row["total_mileage"],
            total_overtime_hours=row["total_overtime_hours"],
            continuity_score=row["continuity_score"],
            objective_score=row["objective_score"],
            assignments=json.loads(row["assignments"]),
            routes=json.loads(row["routes"]),
            created_at=row["created_at"],
        )


async def compare_scenarios(
    scenario_id_1: int, scenario_id_2: int
) -> dict:
    """Compare two scenarios. Raises KeyError if either not found."""
    scenario_1 = await get_scenario(scenario_id_1)
    scenario_2 = await get_scenario(scenario_id_2)
    return {"scenario_1": scenario_1, "scenario_2": scenario_2}


# --- Exception operations ---


async def get_exceptions() -> list[ExceptionModel]:
    """Retrieve all exceptions ordered by timestamp descending."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM exceptions ORDER BY timestamp DESC"
        )
        rows = await cursor.fetchall()
        return [
            ExceptionModel(
                id=row["id"],
                timestamp=row["timestamp"],
                description=row["description"],
                constraint_names=json.loads(row["constraint_names"]),
                affected_entity_type=row["affected_entity_type"],
                affected_entity_id=row["affected_entity_id"],
                is_resolved=bool(row["is_resolved"]),
                resolved_at=row["resolved_at"],
            )
            for row in rows
        ]


async def create_exception(
    description: str,
    constraint_names: list[str],
    affected_entity_type: str,
    affected_entity_id: int,
) -> ExceptionModel:
    """Create a new exception record (e.g. from infeasible optimisation).

    Args:
        description: Human-readable explanation of the issue.
        constraint_names: List of constraint names that caused the issue.
        affected_entity_type: Either 'carer' or 'visit'.
        affected_entity_id: ID of the affected carer or visit.

    Returns:
        The newly created ExceptionModel.

    Raises:
        ValueError: If affected_entity_type is invalid.
    """
    if affected_entity_type not in ("carer", "visit"):
        raise ValueError(
            f"affected_entity_type must be 'carer' or 'visit', got '{affected_entity_type}'"
        )

    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO exceptions
               (description, constraint_names, affected_entity_type, affected_entity_id)
               VALUES (?, ?, ?, ?)""",
            (
                description,
                json.dumps(constraint_names),
                affected_entity_type,
                affected_entity_id,
            ),
        )
        await db.commit()

        # Return the created exception
        new_cursor = await db.execute(
            "SELECT * FROM exceptions WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return ExceptionModel(
            id=row["id"],
            timestamp=row["timestamp"],
            description=row["description"],
            constraint_names=json.loads(row["constraint_names"]),
            affected_entity_type=row["affected_entity_type"],
            affected_entity_id=row["affected_entity_id"],
            is_resolved=bool(row["is_resolved"]),
            resolved_at=row["resolved_at"],
        )


async def resolve_exception(exception_id: int) -> ExceptionModel:
    """Mark an exception as resolved. Raises KeyError if not found.

    If already resolved, raises ValueError.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM exceptions WHERE id = ?", (exception_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise KeyError(f"Exception with id {exception_id} not found")

        if bool(row["is_resolved"]):
            raise ValueError(
                f"Exception with id {exception_id} is already resolved"
            )

        resolved_at = datetime.now().isoformat()
        await db.execute(
            "UPDATE exceptions SET is_resolved = 1, resolved_at = ? WHERE id = ?",
            (resolved_at, exception_id),
        )
        await db.commit()

        return ExceptionModel(
            id=row["id"],
            timestamp=row["timestamp"],
            description=row["description"],
            constraint_names=json.loads(row["constraint_names"]),
            affected_entity_type=row["affected_entity_type"],
            affected_entity_id=row["affected_entity_id"],
            is_resolved=True,
            resolved_at=resolved_at,
        )


# --- Config operations ---


async def get_config() -> dict[str, str]:
    """Retrieve all config key-value pairs as a dictionary."""
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM config")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}


async def update_config(key: str, value: str) -> ConfigModel:
    """Insert or update a config key-value pair."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO config (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value),
        )
        await db.commit()
        return ConfigModel(key=key, value=value)


# --- KPI operations ---


async def get_kpis() -> KPIMetrics:
    """Calculate KPIs from current visits, carers, and latest scenario data."""
    async with get_db() as db:
        # Total non-cancelled visits
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM visits WHERE is_cancelled = 0"
        )
        row = await cursor.fetchone()
        total_visits = row["cnt"]

        # Carers available
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM carers")
        row = await cursor.fetchone()
        carers_available = row["cnt"]

        # Get latest scenario for travel/mileage/overtime/continuity
        cursor = await db.execute(
            "SELECT * FROM scenarios ORDER BY created_at DESC LIMIT 1"
        )
        latest_scenario = await cursor.fetchone()

        if latest_scenario:
            travel_hours = latest_scenario["total_travel_hours"]
            mileage = latest_scenario["total_mileage"]
            overtime = latest_scenario["total_overtime_hours"]
            continuity_score = latest_scenario["continuity_score"]
        else:
            travel_hours = 0.0
            mileage = 0.0
            overtime = 0.0
            # Calculate average continuity from patients if no scenario exists
            cursor = await db.execute(
                "SELECT AVG(continuity_score) as avg_score FROM patients"
            )
            row = await cursor.fetchone()
            continuity_score = row["avg_score"] if row["avg_score"] else 0.0

        return KPIMetrics(
            total_visits=total_visits,
            carers_available=carers_available,
            travel_hours=round(travel_hours, 1),
            mileage=round(mileage, 1),
            overtime=round(overtime, 1),
            continuity_score=round(continuity_score, 1),
        )
