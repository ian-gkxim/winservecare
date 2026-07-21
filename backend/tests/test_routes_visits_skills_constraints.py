"""Unit tests for visits, skills, and constraints route endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.constraint import ConstraintModel
from backend.app.models.skill import SkillModel
from backend.app.models.visit import VisitModel


@pytest.fixture
def client():
    """Create a test client without triggering lifespan."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestVisitsEndpoints:
    """Tests for GET /api/visits and DELETE /api/visits/{id}."""

    @patch("backend.app.routes.visits.get_visits")
    def test_list_visits_returns_200(self, mock_get, client):
        mock_get.return_value = [
            VisitModel(
                id=1,
                patient_id=1,
                duration_minutes=30,
                window_start="09:00",
                window_end="10:00",
                required_skills=["personal_care"],
                preferred_time="09:15",
                is_cancelled=False,
            )
        ]
        resp = client.get("/api/visits")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["patient_id"] == 1

    @patch("backend.app.routes.visits._trigger_reoptimisation")
    @patch("backend.app.routes.visits.cancel_visit")
    def test_delete_visit_returns_204(self, mock_cancel, mock_reopt, client):
        mock_cancel.return_value = None
        mock_reopt.return_value = None
        resp = client.delete("/api/visits/1")
        assert resp.status_code == 204
        mock_cancel.assert_called_once_with(1)

    @patch("backend.app.routes.visits.cancel_visit")
    def test_delete_visit_not_found_returns_404(self, mock_cancel, client):
        mock_cancel.side_effect = KeyError("Visit with id 999 not found")
        resp = client.delete("/api/visits/999")
        assert resp.status_code == 404
        assert "999" in resp.json()["detail"]


class TestSkillsEndpoints:
    """Tests for GET /api/skills and POST /api/skills."""

    @patch("backend.app.routes.skills.get_skills")
    def test_list_skills_returns_200(self, mock_get, client):
        mock_get.return_value = [
            {"id": 1, "name": "personal_care", "carer_count": 3, "visit_count": 5}
        ]
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "personal_care"
        assert data[0]["carer_count"] == 3

    @patch("backend.app.routes.skills.create_skill")
    def test_create_skill_returns_201(self, mock_create, client):
        mock_create.return_value = SkillModel(id=10, name="New Skill")
        resp = client.post("/api/skills", json={"name": "New Skill"})
        assert resp.status_code == 201
        assert resp.json()["id"] == 10
        assert resp.json()["name"] == "New Skill"

    @patch("backend.app.routes.skills.create_skill")
    def test_create_skill_duplicate_returns_422(self, mock_create, client):
        mock_create.side_effect = ValueError("Skill with name 'dup' already exists")
        resp = client.post("/api/skills", json={"name": "dup"})
        assert resp.status_code == 422

    def test_create_skill_empty_name_returns_422(self, client):
        """Pydantic validation rejects empty names via min_length=1."""
        resp = client.post("/api/skills", json={"name": ""})
        assert resp.status_code == 422

    def test_create_skill_too_long_name_returns_422(self, client):
        """Pydantic validation rejects names > 100 chars via max_length=100."""
        resp = client.post("/api/skills", json={"name": "x" * 101})
        assert resp.status_code == 422


class TestConstraintsEndpoints:
    """Tests for GET /api/constraints and PUT /api/constraints/{id}."""

    @patch("backend.app.routes.constraints.get_constraints")
    def test_list_constraints_returns_200(self, mock_get, client):
        mock_get.return_value = [
            ConstraintModel(
                id=1,
                name="Skill Matching",
                description="Carer must have required skills",
                is_enabled=True,
            )
        ]
        resp = client.get("/api/constraints")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["is_enabled"] is True

    @patch("backend.app.routes.constraints.update_constraint")
    def test_update_constraint_returns_200(self, mock_update, client):
        mock_update.return_value = ConstraintModel(
            id=1,
            name="Skill Matching",
            description="Carer must have required skills",
            is_enabled=False,
        )
        resp = client.put("/api/constraints/1", json={"is_enabled": False})
        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is False

    @patch("backend.app.routes.constraints.update_constraint")
    def test_update_constraint_not_found_returns_404(self, mock_update, client):
        mock_update.side_effect = KeyError("Constraint with id 999 not found")
        resp = client.put("/api/constraints/999", json={"is_enabled": False})
        assert resp.status_code == 404
        assert "999" in resp.json()["detail"]
