"""Tests for KPI, reports, and config API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.database import init_db, get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)

    # Patch get_db_path in database module
    import backend.app.db.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    await init_db()
    yield


@pytest_asyncio.fixture
async def client():
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_kpis_returns_metrics(client):
    """GET /api/kpis returns KPIMetrics with expected fields."""
    response = await client.get("/api/kpis")
    assert response.status_code == 200
    data = response.json()
    assert "total_visits" in data
    assert "carers_available" in data
    assert "travel_hours" in data
    assert "mileage" in data
    assert "overtime" in data
    assert "continuity_score" in data


@pytest.mark.asyncio
async def test_get_kpis_returns_zero_defaults_when_no_data(client):
    """GET /api/kpis returns zeroes when no scenarios or data exist."""
    response = await client.get("/api/kpis")
    assert response.status_code == 200
    data = response.json()
    assert data["total_visits"] == 0
    assert data["carers_available"] == 0
    assert data["travel_hours"] == 0.0
    assert data["mileage"] == 0.0
    assert data["overtime"] == 0.0


@pytest.mark.asyncio
async def test_get_config_no_key_set(client):
    """GET /api/config returns hasApiKey=False when no key is set."""
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["hasApiKey"] is False
    assert data["googleMapsApiKey"] == ""


@pytest.mark.asyncio
async def test_put_config_sets_api_key(client):
    """PUT /api/config persists the API key and returns masked value."""
    response = await client.put(
        "/api/config",
        json={"google_maps_api_key": "AIzaSyTestKey123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["hasApiKey"] is True
    assert data["googleMapsApiKey"] == "***"


@pytest.mark.asyncio
async def test_put_config_then_get_shows_key_set(client):
    """After setting API key, GET /api/config reports hasApiKey=True."""
    await client.put(
        "/api/config",
        json={"google_maps_api_key": "AIzaSyTestKey123"},
    )
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["hasApiKey"] is True
    assert data["googleMapsApiKey"] == "***"


@pytest.mark.asyncio
async def test_put_config_empty_key_rejected(client):
    """PUT /api/config with empty key returns 422."""
    response = await client.put(
        "/api/config",
        json={"google_maps_api_key": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_config_whitespace_key_rejected(client):
    """PUT /api/config with whitespace-only key returns 422."""
    response = await client.put(
        "/api/config",
        json={"google_maps_api_key": "   "},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_reports_latest_no_scenarios(client):
    """GET /api/reports/latest returns not-available when no scenarios exist."""
    response = await client.get("/api/reports/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is False
    assert "message" in data


@pytest.mark.asyncio
async def test_get_reports_latest_with_two_scenarios(client):
    """GET /api/reports/latest returns comparison when 2+ scenarios exist."""
    from backend.app.db.database import get_db

    # Insert two scenarios with explicit timestamps so ordering is deterministic
    async with get_db() as db:
        await db.execute(
            """INSERT INTO scenarios
               (name, total_travel_hours, total_mileage, total_overtime_hours,
                continuity_score, objective_score, assignments, routes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Baseline", 10.0, 50.0, 3.0, 60.0, 100.0, "[]", "[]",
             "2024-01-01T10:00:00"),
        )
        await db.execute(
            """INSERT INTO scenarios
               (name, total_travel_hours, total_mileage, total_overtime_hours,
                continuity_score, objective_score, assignments, routes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Optimised", 7.0, 35.0, 1.0, 75.0, 70.0, "[]", "[]",
             "2024-01-01T11:00:00"),
        )
        await db.commit()

    response = await client.get("/api/reports/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert "before" in data
    assert "after" in data
    assert "differences" in data

    # "Optimised" is most recent (after), "Baseline" is before
    assert data["after"]["scenario_name"] == "Optimised"
    assert data["before"]["scenario_name"] == "Baseline"

    # Check differences calculated correctly
    travel_diff = data["differences"]["travel_hours"]
    assert travel_diff["absolute"] == 3.0  # 10 - 7
    assert travel_diff["percentage"] == 30.0  # (3/10)*100
