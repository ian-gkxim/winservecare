"""Backend integration tests for Care Contracts & Visit Generation.

Covers:
- Full contract CRUD lifecycle (create → read → update → delete)
- Visit generation end-to-end (create contracts → generate for date → verify visits in DB)
- Regeneration resets cancelled visits
- Cancellation flow (cancel visit → verify status → verify other visits unchanged)
- Seed data verification (all 12 patients have contracts after init)
- Idempotent seeding (restart does not overwrite modified contracts)

Requirements: 1.1, 2.1, 4.3, 4.4, 4.5, 7.1, 7.7
"""

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.db import database, seed as seed_module
from backend.app.db.seed import seed_contracts, seed_db
from backend.app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Set up a temporary test database with schema and minimal seed data."""
    import aiosqlite

    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db_conn:
            await db_conn.execute("PRAGMA foreign_keys=ON")
            await db_conn.executescript(schema_sql)
            await db_conn.commit()

        # Seed minimal test data: 3 patients and skills
        async with database.get_db() as db_conn:
            for i in range(1, 4):
                await db_conn.execute(
                    """INSERT INTO patients (name, address, lat, lng, preferences, priority, continuity_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (f"Patient {i}", f"{i} High St", 51.50 + i * 0.01, -0.10 + i * 0.01,
                     json.dumps(["morning"]), "medium", 50.0 + i * 10),
                )
            await db_conn.execute("INSERT INTO skills (name) VALUES (?)", ("personal_care",))
            await db_conn.execute("INSERT INTO skills (name) VALUES (?)", ("medication",))
            await db_conn.execute("INSERT INTO skills (name) VALUES (?)", ("mobility",))
            await db_conn.commit()
        yield


@pytest_asyncio.fixture
async def seeded_db(tmp_path):
    """Set up a temporary test database with full seed data (all 12 patients + contracts)."""
    import aiosqlite

    db_path = tmp_path / "test.db"
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with patch.object(database, "DB_PATH", db_path), \
         patch.object(database, "DB_DIR", tmp_path), \
         patch.object(seed_module, "DB_PATH", db_path), \
         patch.object(seed_module, "DB_DIR", tmp_path):
        async with aiosqlite.connect(str(db_path)) as db_conn:
            await db_conn.execute("PRAGMA foreign_keys=ON")
            await db_conn.executescript(schema_sql)
            await db_conn.commit()

        # Run the full seed (carers, patients, visits, contracts)
        await seed_db()
        yield


@pytest_asyncio.fixture
async def client(test_db):
    """Create an async test client with minimal test data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_client(seeded_db):
    """Create an async test client with full seed data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _valid_contract_payload(**overrides) -> dict:
    """Helper to build a valid contract creation payload."""
    defaults = {
        "visit_frequency": "daily",
        "days_of_week": None,
        "visits_per_day": 1,
        "start_date": "2025-01-01",
        "end_date": None,
        "excluded_dates": [],
        "visit_slots": [
            {
                "label": "Morning visit",
                "earliest_start": "08:00",
                "latest_start": "09:00",
                "duration_minutes": 30,
                "required_skills": ["personal_care"],
            }
        ],
    }
    defaults.update(overrides)
    return defaults


def _future_weekday() -> str:
    """Return a future weekday date as YYYY-MM-DD string (always valid for generation)."""
    today = date.today()
    # Find next Monday if we're on weekend, or use tomorrow if weekday
    candidate = today + timedelta(days=1)
    while candidate.weekday() >= 5:  # skip weekends
        candidate += timedelta(days=1)
    return candidate.isoformat()


# ---------------------------------------------------------------------------
# Test: Full contract CRUD lifecycle
# ---------------------------------------------------------------------------


class TestContractCRUDLifecycle:
    """Test full contract lifecycle: create → read → update → delete."""

    @pytest.mark.asyncio
    async def test_create_contract(self, client):
        """Creating a contract returns 201 with the full contract model."""
        payload = _valid_contract_payload()
        resp = await client.put("/api/patients/1/contract", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == 1
        assert data["visit_frequency"] == "daily"
        assert data["visits_per_day"] == 1
        assert len(data["visit_slots"]) == 1
        assert data["visit_slots"][0]["label"] == "Morning visit"

    @pytest.mark.asyncio
    async def test_read_contract_after_create(self, client):
        """GET returns the contract after creation."""
        payload = _valid_contract_payload()
        await client.put("/api/patients/1/contract", json=payload)

        resp = await client.get("/api/patients/1/contract")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == 1
        assert data["visit_frequency"] == "daily"
        assert data["start_date"] == "2025-01-01"
        assert data["end_date"] is None
        assert data["visit_slots"][0]["duration_minutes"] == 30
        assert data["visit_slots"][0]["required_skills"] == ["personal_care"]

    @pytest.mark.asyncio
    async def test_update_contract(self, client):
        """Updating a contract changes fields and returns 200."""
        # Create
        payload = _valid_contract_payload()
        await client.put("/api/patients/1/contract", json=payload)

        # Update with different frequency and multiple slots
        updated_payload = _valid_contract_payload(
            visit_frequency="weekdays_only",
            visits_per_day=2,
            visit_slots=[
                {
                    "label": "Morning care",
                    "earliest_start": "07:00",
                    "latest_start": "08:00",
                    "duration_minutes": 45,
                    "required_skills": ["personal_care"],
                },
                {
                    "label": "Evening care",
                    "earliest_start": "17:00",
                    "latest_start": "18:00",
                    "duration_minutes": 30,
                    "required_skills": ["medication"],
                },
            ],
        )
        resp = await client.put("/api/patients/1/contract", json=updated_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["visit_frequency"] == "weekdays_only"
        assert data["visits_per_day"] == 2
        assert len(data["visit_slots"]) == 2
        assert data["visit_slots"][0]["label"] == "Morning care"
        assert data["visit_slots"][1]["label"] == "Evening care"

    @pytest.mark.asyncio
    async def test_delete_contract(self, client):
        """Deleting a contract returns 204 and subsequent GET returns null."""
        # Create
        payload = _valid_contract_payload()
        await client.put("/api/patients/1/contract", json=payload)

        # Delete
        resp = await client.delete("/api/patients/1/contract")
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get("/api/patients/1/contract")
        assert resp.status_code == 200
        assert resp.json() is None

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, client):
        """Complete CRUD cycle: create → read → update → read → delete → read."""
        # Create
        payload = _valid_contract_payload(
            visit_frequency="specific_days",
            days_of_week=["mon", "wed", "fri"],
        )
        resp = await client.put("/api/patients/2/contract", json=payload)
        assert resp.status_code == 201

        # Read
        resp = await client.get("/api/patients/2/contract")
        data = resp.json()
        assert data["visit_frequency"] == "specific_days"
        assert data["days_of_week"] == ["mon", "wed", "fri"]

        # Update
        updated = _valid_contract_payload(
            visit_frequency="daily",
            days_of_week=None,
            visits_per_day=2,
            visit_slots=[
                {"label": "AM", "earliest_start": "08:00", "latest_start": "09:00",
                 "duration_minutes": 30, "required_skills": []},
                {"label": "PM", "earliest_start": "16:00", "latest_start": "17:00",
                 "duration_minutes": 30, "required_skills": []},
            ],
        )
        resp = await client.put("/api/patients/2/contract", json=updated)
        assert resp.status_code == 200

        # Re-read
        resp = await client.get("/api/patients/2/contract")
        data = resp.json()
        assert data["visit_frequency"] == "daily"
        assert data["visits_per_day"] == 2
        assert len(data["visit_slots"]) == 2

        # Delete
        resp = await client.delete("/api/patients/2/contract")
        assert resp.status_code == 204

        # Confirm deleted
        resp = await client.get("/api/patients/2/contract")
        assert resp.json() is None


# ---------------------------------------------------------------------------
# Test: Visit generation end-to-end
# ---------------------------------------------------------------------------


class TestVisitGenerationE2E:
    """Test visit generation from contracts: create contracts → generate → verify."""

    @pytest.mark.asyncio
    async def test_generate_visits_from_contracts(self, client):
        """Generating visits for a date produces visits from eligible contracts."""
        target = _future_weekday()

        # Create a daily contract for patient 1
        payload = _valid_contract_payload(
            start_date="2025-01-01",
            visits_per_day=2,
            visit_slots=[
                {"label": "Morning", "earliest_start": "08:00", "latest_start": "09:00",
                 "duration_minutes": 30, "required_skills": ["personal_care"]},
                {"label": "Evening", "earliest_start": "17:00", "latest_start": "18:00",
                 "duration_minutes": 45, "required_skills": ["medication"]},
            ],
        )
        resp = await client.put("/api/patients/1/contract", json=payload)
        assert resp.status_code == 201

        # Generate visits
        resp = await client.post("/api/visits/generate", json={"target_date": target})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_contracts_evaluated"] == 1
        assert data["eligible_contracts"] == 1
        assert data["scheduled_count"] == 2
        assert len(data["visits"]) == 2

        # Verify visit details
        visits = data["visits"]
        morning_visit = next(v for v in visits if v["window_start"] == "08:00")
        assert morning_visit["patient_id"] == 1
        assert morning_visit["duration_minutes"] == 30
        assert morning_visit["window_end"] == "09:00"
        assert morning_visit["required_skills"] == ["personal_care"]
        assert morning_visit["is_cancelled"] is False

        evening_visit = next(v for v in visits if v["window_start"] == "17:00")
        assert evening_visit["duration_minutes"] == 45
        assert evening_visit["required_skills"] == ["medication"]

    @pytest.mark.asyncio
    async def test_generate_visits_multiple_contracts(self, client):
        """Visit generation evaluates all contracts and generates for eligible ones."""
        target = _future_weekday()

        # Daily contract for patient 1 (1 slot)
        await client.put("/api/patients/1/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
        ))

        # Daily contract for patient 2 (1 slot)
        await client.put("/api/patients/2/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
            visit_slots=[
                {"label": "Afternoon care", "earliest_start": "14:00", "latest_start": "15:00",
                 "duration_minutes": 60, "required_skills": ["mobility"]},
            ],
        ))

        # Generate
        resp = await client.post("/api/visits/generate", json={"target_date": target})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_contracts_evaluated"] == 2
        assert data["eligible_contracts"] == 2
        assert data["scheduled_count"] == 2

        # Verify both patients have visits
        patient_ids = {v["patient_id"] for v in data["visits"]}
        assert patient_ids == {1, 2}

    @pytest.mark.asyncio
    async def test_generate_visits_respects_frequency(self, client):
        """Contracts with non-matching frequency are not eligible."""
        # Pick a Monday
        today = date.today()
        days_ahead = (7 - today.weekday()) % 7  # next Monday
        if days_ahead == 0:
            days_ahead = 7
        next_monday = (today + timedelta(days=days_ahead)).isoformat()

        # Tuesday/Thursday only contract
        await client.put("/api/patients/1/contract", json=_valid_contract_payload(
            visit_frequency="specific_days",
            days_of_week=["tue", "thu"],
            start_date="2025-01-01",
        ))

        # Generate for Monday — should not match
        resp = await client.post("/api/visits/generate", json={"target_date": next_monday})
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligible_contracts"] == 0
        assert data["scheduled_count"] == 0
        assert len(data["visits"]) == 0

    @pytest.mark.asyncio
    async def test_generate_visits_verifiable_in_db(self, client):
        """Generated visits are persisted and retrievable via GET /api/visits."""
        target = _future_weekday()

        await client.put("/api/patients/1/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
        ))

        # Generate
        await client.post("/api/visits/generate", json={"target_date": target})

        # Verify via GET
        resp = await client.get(f"/api/visits?target_date={target}")
        assert resp.status_code == 200
        visits = resp.json()
        assert len(visits) == 1
        assert visits[0]["patient_id"] == 1
        assert visits[0]["target_date"] == target

    @pytest.mark.asyncio
    async def test_generate_replaces_previous_visits(self, client):
        """Regenerating for same date replaces existing visits."""
        target = _future_weekday()

        # Create contract and generate
        await client.put("/api/patients/1/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
        ))
        await client.post("/api/visits/generate", json={"target_date": target})

        # Update contract to 2 slots
        await client.put("/api/patients/1/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
            visits_per_day=2,
            visit_slots=[
                {"label": "AM", "earliest_start": "08:00", "latest_start": "09:00",
                 "duration_minutes": 30, "required_skills": []},
                {"label": "PM", "earliest_start": "16:00", "latest_start": "17:00",
                 "duration_minutes": 30, "required_skills": []},
            ],
        ))

        # Regenerate — should now have 2 visits
        resp = await client.post("/api/visits/generate", json={"target_date": target})
        data = resp.json()
        assert data["scheduled_count"] == 2

        # Verify DB only has new visits
        resp = await client.get(f"/api/visits?target_date={target}")
        visits = resp.json()
        assert len(visits) == 2


# ---------------------------------------------------------------------------
# Test: Regeneration resets cancelled visits
# ---------------------------------------------------------------------------


class TestRegeneration:
    """Test that regeneration resets cancelled visits and regenerates from contracts."""

    @pytest.mark.asyncio
    async def test_regenerate_resets_cancelled_visits(self, client):
        """Regeneration replaces all visits including cancelled ones with fresh scheduled visits."""
        target = _future_weekday()

        # Create contract with 2 slots
        await client.put("/api/patients/1/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
            visits_per_day=2,
            visit_slots=[
                {"label": "AM", "earliest_start": "08:00", "latest_start": "09:00",
                 "duration_minutes": 30, "required_skills": []},
                {"label": "PM", "earliest_start": "16:00", "latest_start": "17:00",
                 "duration_minutes": 30, "required_skills": []},
            ],
        ))

        # Generate visits
        resp = await client.post("/api/visits/generate", json={"target_date": target})
        visits = resp.json()["visits"]
        assert len(visits) == 2

        # Cancel one visit
        visit_id = visits[0]["id"]
        resp = await client.patch(f"/api/visits/{visit_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["is_cancelled"] is True

        # Verify one is cancelled
        resp = await client.get(f"/api/visits?target_date={target}")
        db_visits = resp.json()
        cancelled_count = sum(1 for v in db_visits if v["is_cancelled"])
        assert cancelled_count == 1

        # Regenerate
        resp = await client.post("/api/visits/regenerate", json={"target_date": target})
        assert resp.status_code == 200
        data = resp.json()
        assert data["scheduled_count"] == 2

        # Verify all visits are now scheduled (cancelled ones were reset)
        resp = await client.get(f"/api/visits?target_date={target}")
        db_visits = resp.json()
        assert len(db_visits) == 2
        assert all(not v["is_cancelled"] for v in db_visits)


# ---------------------------------------------------------------------------
# Test: Cancellation flow
# ---------------------------------------------------------------------------


class TestCancellationFlow:
    """Test visit cancellation: cancel → verify status → other visits unchanged."""

    @pytest.mark.asyncio
    async def test_cancel_visit_changes_status(self, client):
        """Cancelling a visit sets is_cancelled to True."""
        target = _future_weekday()

        await client.put("/api/patients/1/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
        ))
        resp = await client.post("/api/visits/generate", json={"target_date": target})
        visit_id = resp.json()["visits"][0]["id"]

        # Cancel
        resp = await client.patch(f"/api/visits/{visit_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_cancelled"] is True
        assert data["id"] == visit_id

    @pytest.mark.asyncio
    async def test_cancel_does_not_affect_other_visits(self, client):
        """Cancelling one visit leaves other visits unchanged."""
        target = _future_weekday()

        # Create contracts for 2 patients
        await client.put("/api/patients/1/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
        ))
        await client.put("/api/patients/2/contract", json=_valid_contract_payload(
            start_date="2025-01-01",
            visit_slots=[
                {"label": "Care", "earliest_start": "10:00", "latest_start": "11:00",
                 "duration_minutes": 30, "required_skills": []},
            ],
        ))

        # Generate visits
        resp = await client.post("/api/visits/generate", json={"target_date": target})
        visits = resp.json()["visits"]
        assert len(visits) == 2

        # Cancel patient 1's visit
        patient1_visit = next(v for v in visits if v["patient_id"] == 1)
        patient2_visit = next(v for v in visits if v["patient_id"] == 2)

        resp = await client.patch(f"/api/visits/{patient1_visit['id']}/cancel")
        assert resp.status_code == 200

        # Verify patient 2's visit is unchanged
        resp = await client.get(f"/api/visits?target_date={target}")
        db_visits = resp.json()
        p2_visit = next(v for v in db_visits if v["patient_id"] == 2)
        assert p2_visit["is_cancelled"] is False
        assert p2_visit["id"] == patient2_visit["id"]

        # Verify patient 1's visit is cancelled
        p1_visit = next(v for v in db_visits if v["patient_id"] == 1)
        assert p1_visit["is_cancelled"] is True

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_visit_returns_404(self, client):
        """Cancelling a non-existent visit returns 404."""
        resp = await client.patch("/api/visits/99999/cancel")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: Seed data verification
# ---------------------------------------------------------------------------


class TestSeedDataVerification:
    """Test that seeding creates contracts for all 12 patients."""

    @pytest.mark.asyncio
    async def test_all_12_patients_have_contracts(self, seeded_client):
        """After seeding, all 12 patients should have care contracts."""
        for patient_id in range(1, 13):
            resp = await seeded_client.get(f"/api/patients/{patient_id}/contract")
            assert resp.status_code == 200, f"Patient {patient_id} contract fetch failed"
            data = resp.json()
            assert data is not None, f"Patient {patient_id} has no contract"
            assert data["patient_id"] == patient_id
            assert len(data["visit_slots"]) == data["visits_per_day"]

    @pytest.mark.asyncio
    async def test_seeded_contracts_have_valid_frequencies(self, seeded_client):
        """Seeded contracts have a valid visit_frequency value."""
        valid_frequencies = {"daily", "weekdays_only", "specific_days", "alternate_days", "weekly"}
        for patient_id in range(1, 13):
            resp = await seeded_client.get(f"/api/patients/{patient_id}/contract")
            data = resp.json()
            assert data["visit_frequency"] in valid_frequencies

    @pytest.mark.asyncio
    async def test_seeded_contracts_cover_all_frequencies(self, seeded_client):
        """The seeded data includes at least one contract per frequency type."""
        frequencies_seen = set()
        for patient_id in range(1, 13):
            resp = await seeded_client.get(f"/api/patients/{patient_id}/contract")
            data = resp.json()
            frequencies_seen.add(data["visit_frequency"])

        expected = {"daily", "weekdays_only", "specific_days", "alternate_days", "weekly"}
        assert frequencies_seen == expected

    @pytest.mark.asyncio
    async def test_seeded_contracts_have_start_date_2025_01_01(self, seeded_client):
        """All seeded contracts have start_date of 2025-01-01."""
        for patient_id in range(1, 13):
            resp = await seeded_client.get(f"/api/patients/{patient_id}/contract")
            data = resp.json()
            assert data["start_date"] == "2025-01-01"
            assert data["end_date"] is None


# ---------------------------------------------------------------------------
# Test: Idempotent seeding
# ---------------------------------------------------------------------------


class TestIdempotentSeeding:
    """Test that restarting the application does not overwrite modified contracts."""

    @pytest.mark.asyncio
    async def test_seed_does_not_overwrite_existing_contracts(self, seeded_client, seeded_db):
        """Modifying a contract and re-seeding preserves the modification."""
        # Modify patient 1's contract
        updated_payload = _valid_contract_payload(
            visit_frequency="weekly",
            visits_per_day=1,
            start_date="2025-06-01",
            visit_slots=[
                {"label": "Modified visit", "earliest_start": "10:00", "latest_start": "11:00",
                 "duration_minutes": 60, "required_skills": ["personal_care"]},
            ],
        )
        resp = await seeded_client.put("/api/patients/1/contract", json=updated_payload)
        assert resp.status_code == 200

        # Re-run seeding (simulates app restart)
        await seed_contracts()

        # Verify the modification is preserved (not overwritten by seed)
        resp = await seeded_client.get("/api/patients/1/contract")
        data = resp.json()
        assert data["visit_frequency"] == "weekly"
        assert data["start_date"] == "2025-06-01"
        assert data["visit_slots"][0]["label"] == "Modified visit"

    @pytest.mark.asyncio
    async def test_seed_is_idempotent_with_existing_data(self, seeded_client, seeded_db):
        """Running seed_contracts multiple times does not create duplicate contracts."""
        # Count contracts before
        contracts_before = []
        for patient_id in range(1, 13):
            resp = await seeded_client.get(f"/api/patients/{patient_id}/contract")
            contracts_before.append(resp.json())

        # Re-run seeding
        await seed_contracts()

        # Count contracts after — should be identical
        for patient_id in range(1, 13):
            resp = await seeded_client.get(f"/api/patients/{patient_id}/contract")
            data = resp.json()
            assert data is not None
            assert data["id"] == contracts_before[patient_id - 1]["id"]
