"""Tests for the WebSocket optimisation endpoint."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.carer import CarerModel
from backend.app.models.constraint import ConstraintModel
from backend.app.models.optimisation import (
    KPIMetrics,
    OptimisationResult,
    RouteModel,
    RouteStop,
    TravelTimeMatrix,
)
from backend.app.models.patient import PatientModel
from backend.app.models.visit import VisitModel


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_carers():
    return [
        CarerModel(
            id=1,
            name="Alice",
            home_lat=51.5,
            home_lng=-0.1,
            skills=["medication"],
            max_working_hours=8.0,
            max_continuous_hours=4.0,
            min_break_minutes=30,
        ),
    ]


@pytest.fixture
def sample_patients():
    return [
        PatientModel(
            id=1,
            name="Bob",
            address="123 High St",
            lat=51.51,
            lng=-0.09,
            preferences=["morning"],
            priority="medium",
            continuity_score=80.0,
            usual_carer_id=1,
            preferred_carer_id=1,
        ),
    ]


@pytest.fixture
def sample_visits():
    return [
        VisitModel(
            id=1,
            patient_id=1,
            window_start="09:00",
            window_end="10:00",
            duration_minutes=30,
            required_skills=["medication"],
            preferred_time="09:15",
        ),
    ]


@pytest.fixture
def sample_constraints():
    return [
        ConstraintModel(
            id=1,
            name="skill_matching",
            description="Match skills",
            is_enabled=True,
        ),
    ]


@pytest.fixture
def sample_result():
    return OptimisationResult(
        routes=[
            RouteModel(
                carer_id=1,
                stops=[
                    RouteStop(
                        visit_id=1,
                        patient_id=1,
                        arrival_time="09:10",
                        start_time="09:10",
                        end_time="09:40",
                        travel_time_from_prev=10,
                        mileage_from_prev=2.5,
                    )
                ],
                total_travel_minutes=10,
                total_mileage=2.5,
                total_cost=5.0,
            )
        ],
        objective_score=85.5,
        kpis=KPIMetrics(
            total_visits=1,
            carers_available=1,
            travel_hours=0.17,
            mileage=2.5,
            overtime=0.0,
            continuity_score=100.0,
        ),
        recommendations=[],
        unassigned_visits=[],
        infeasibility_reasons=[],
    )


@pytest.fixture
def sample_travel_matrix():
    return TravelTimeMatrix(
        locations=[(51.5, -0.1), (51.51, -0.09)],
        durations=[[0, 600], [600, 0]],
        distances=[[0, 2000], [2000, 0]],
    )


class TestWebSocketOptimise:
    """Tests for the /ws/optimise WebSocket endpoint."""

    def test_start_message_triggers_optimisation(
        self,
        client,
        sample_carers,
        sample_patients,
        sample_visits,
        sample_constraints,
        sample_travel_matrix,
        sample_result,
    ):
        """Sending a 'start' message triggers the optimisation pipeline."""
        with (
            patch(
                "backend.app.routes.websocket.get_carers",
                new_callable=AsyncMock,
                return_value=sample_carers,
            ),
            patch(
                "backend.app.routes.websocket.get_patients",
                new_callable=AsyncMock,
                return_value=sample_patients,
            ),
            patch(
                "backend.app.routes.websocket.get_visits",
                new_callable=AsyncMock,
                return_value=sample_visits,
            ),
            patch(
                "backend.app.routes.websocket.get_constraints",
                new_callable=AsyncMock,
                return_value=sample_constraints,
            ),
            patch(
                "backend.app.routes.websocket.GoogleMapsClient"
            ) as mock_maps_cls,
            patch(
                "backend.app.routes.websocket.OptimisationEngine"
            ) as mock_engine_cls,
        ):
            # Configure mocks
            mock_maps_instance = mock_maps_cls.return_value
            mock_maps_instance.get_distance_matrix = AsyncMock(
                return_value=sample_travel_matrix
            )

            mock_engine_instance = mock_engine_cls.return_value
            mock_engine_instance.run = AsyncMock(return_value=sample_result)

            with client.websocket_connect("/ws/optimise") as ws:
                ws.send_json({"type": "start"})

                # Collect messages until we get "complete"
                messages = []
                for _ in range(50):  # Safety limit
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "complete":
                        break

                # Verify we received a complete message
                complete_msgs = [m for m in messages if m["type"] == "complete"]
                assert len(complete_msgs) == 1
                assert complete_msgs[0]["finalScore"] == 85.5
                assert len(complete_msgs[0]["routes"]) == 1

    def test_start_with_visit_ids_filters_visits(
        self,
        client,
        sample_carers,
        sample_patients,
        sample_visits,
        sample_constraints,
        sample_travel_matrix,
        sample_result,
    ):
        """Sending visit IDs in start message filters visits."""
        with (
            patch(
                "backend.app.routes.websocket.get_carers",
                new_callable=AsyncMock,
                return_value=sample_carers,
            ),
            patch(
                "backend.app.routes.websocket.get_patients",
                new_callable=AsyncMock,
                return_value=sample_patients,
            ),
            patch(
                "backend.app.routes.websocket.get_visits",
                new_callable=AsyncMock,
                return_value=sample_visits,
            ),
            patch(
                "backend.app.routes.websocket.get_constraints",
                new_callable=AsyncMock,
                return_value=sample_constraints,
            ),
            patch(
                "backend.app.routes.websocket.GoogleMapsClient"
            ) as mock_maps_cls,
            patch(
                "backend.app.routes.websocket.OptimisationEngine"
            ) as mock_engine_cls,
        ):
            mock_maps_instance = mock_maps_cls.return_value
            mock_maps_instance.get_distance_matrix = AsyncMock(
                return_value=sample_travel_matrix
            )
            mock_engine_instance = mock_engine_cls.return_value
            mock_engine_instance.run = AsyncMock(return_value=sample_result)

            with client.websocket_connect("/ws/optimise") as ws:
                # Consume the deprecation notice sent on connect
                deprecation_msg = ws.receive_json()
                assert deprecation_msg["type"] == "deprecation_notice"

                # Send start with a visit ID that doesn't exist in our sample
                ws.send_json({"type": "start", "visitIds": [999]})

                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert "No visits" in msg["message"]

    def test_error_on_no_carers(
        self,
        client,
        sample_patients,
        sample_visits,
        sample_constraints,
    ):
        """Error is sent when no carers are available."""
        with (
            patch(
                "backend.app.routes.websocket.get_carers",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "backend.app.routes.websocket.get_patients",
                new_callable=AsyncMock,
                return_value=sample_patients,
            ),
            patch(
                "backend.app.routes.websocket.get_visits",
                new_callable=AsyncMock,
                return_value=sample_visits,
            ),
            patch(
                "backend.app.routes.websocket.get_constraints",
                new_callable=AsyncMock,
                return_value=sample_constraints,
            ),
        ):
            with client.websocket_connect("/ws/optimise") as ws:
                # Consume the deprecation notice sent on connect
                deprecation_msg = ws.receive_json()
                assert deprecation_msg["type"] == "deprecation_notice"

                ws.send_json({"type": "start"})
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert "No carers" in msg["message"]

    def test_maps_api_error_sends_error_message(
        self,
        client,
        sample_carers,
        sample_patients,
        sample_visits,
        sample_constraints,
    ):
        """Maps API error is reported as an error message."""
        from backend.app.services.maps_client import MapsAPIError

        with (
            patch(
                "backend.app.routes.websocket.get_carers",
                new_callable=AsyncMock,
                return_value=sample_carers,
            ),
            patch(
                "backend.app.routes.websocket.get_patients",
                new_callable=AsyncMock,
                return_value=sample_patients,
            ),
            patch(
                "backend.app.routes.websocket.get_visits",
                new_callable=AsyncMock,
                return_value=sample_visits,
            ),
            patch(
                "backend.app.routes.websocket.get_constraints",
                new_callable=AsyncMock,
                return_value=sample_constraints,
            ),
            patch(
                "backend.app.routes.websocket.GoogleMapsClient"
            ) as mock_maps_cls,
        ):
            mock_maps_instance = mock_maps_cls.return_value
            mock_maps_instance.get_distance_matrix = AsyncMock(
                side_effect=MapsAPIError("API key not configured")
            )

            with client.websocket_connect("/ws/optimise") as ws:
                ws.send_json({"type": "start"})
                # The progress service emits solver_progress messages before
                # the error, so collect messages until we find the error
                messages = []
                for _ in range(10):
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "error":
                        break
                error_msgs = [m for m in messages if m["type"] == "error"]
                assert len(error_msgs) == 1
                assert "API key not configured" in error_msgs[0]["message"]

    def test_existing_step_messages_preserved_with_progress(
        self,
        client,
        sample_carers,
        sample_patients,
        sample_visits,
        sample_constraints,
        sample_travel_matrix,
        sample_result,
    ):
        """All 8 step/progress messages are preserved and solver_progress coexists.

        Verifies requirements 6.1-6.4: existing step-based messages continue
        to emit, solver_progress messages use a distinct type, both coexist on
        the same connection, and removing solver_progress leaves the original
        message flow intact.
        """

        # Define step names matching the 8 pipeline steps
        step_names = [
            "Locations plotted",
            "Matrix retrieved",
            "Feasible assignments",
            "Constraint pruning",
            "Route evaluation",
            "Improvement iterations",
            "Winning solution",
            "Route animation",
        ]

        async def fake_engine_run(
            carers,
            visits,
            patients,
            constraints,
            travel_matrix,
            on_step,
            on_progress,
            progress=None,
        ):
            """Simulate the real engine emitting all 8 steps and progress."""
            for i, name in enumerate(step_names, start=1):
                await on_step({
                    "stepNumber": i,
                    "stepName": name,
                    "data": {"type": "test_data"},
                })
                await on_progress({
                    "step": i,
                    "name": name,
                    "score": float(i * 10),
                })
            return sample_result

        with (
            patch(
                "backend.app.routes.websocket.get_carers",
                new_callable=AsyncMock,
                return_value=sample_carers,
            ),
            patch(
                "backend.app.routes.websocket.get_patients",
                new_callable=AsyncMock,
                return_value=sample_patients,
            ),
            patch(
                "backend.app.routes.websocket.get_visits",
                new_callable=AsyncMock,
                return_value=sample_visits,
            ),
            patch(
                "backend.app.routes.websocket.get_constraints",
                new_callable=AsyncMock,
                return_value=sample_constraints,
            ),
            patch(
                "backend.app.routes.websocket.GoogleMapsClient"
            ) as mock_maps_cls,
            patch(
                "backend.app.routes.websocket.OptimisationEngine"
            ) as mock_engine_cls,
        ):
            # Configure mocks
            mock_maps_instance = mock_maps_cls.return_value
            mock_maps_instance.get_distance_matrix = AsyncMock(
                return_value=sample_travel_matrix
            )

            mock_engine_instance = mock_engine_cls.return_value
            mock_engine_instance.run = AsyncMock(side_effect=fake_engine_run)

            with client.websocket_connect("/ws/optimise") as ws:
                ws.send_json({"type": "start"})

                # Collect ALL messages until "complete"
                messages = []
                for _ in range(100):  # Safety limit
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "complete":
                        break

                # --- Verify all 8 step messages arrive ---
                step_msgs = [m for m in messages if m["type"] == "step"]
                step_numbers = [
                    m["payload"]["stepNumber"] for m in step_msgs
                ]
                assert sorted(step_numbers) == list(range(1, 9)), (
                    f"Expected step numbers 1-8, got {step_numbers}"
                )

                # --- Verify all 8 progress messages arrive ---
                progress_msgs = [m for m in messages if m["type"] == "progress"]
                progress_steps = [m["step"] for m in progress_msgs]
                assert sorted(progress_steps) == list(range(1, 9)), (
                    f"Expected progress steps 1-8, got {progress_steps}"
                )

                # --- Verify progress messages have correct format ---
                for pm in progress_msgs:
                    assert "step" in pm
                    assert "name" in pm
                    assert "score" in pm
                    assert isinstance(pm["step"], int)
                    assert isinstance(pm["name"], str)

                # --- Verify solver_progress messages coexist ---
                solver_progress_msgs = [
                    m for m in messages if m["type"] == "solver_progress"
                ]
                # We expect at least some solver_progress messages
                # (distance_matrix phase from fetch_matrix_with_progress)
                assert len(solver_progress_msgs) >= 1, (
                    "Expected at least one solver_progress message"
                )

                # Verify solver_progress uses a distinct type from
                # step, progress, complete, error
                for sp in solver_progress_msgs:
                    assert sp["type"] == "solver_progress"
                    assert "phase" in sp
                    assert sp["phase"] in ("distance_matrix", "solver")

                # --- Verify filtering out solver_progress leaves original flow ---
                non_solver_progress_msgs = [
                    m for m in messages if m["type"] != "solver_progress"
                ]
                # The non-solver_progress stream should contain all steps,
                # all progress messages, and the complete message
                non_sp_types = [m["type"] for m in non_solver_progress_msgs]
                assert non_sp_types.count("step") == 8
                assert non_sp_types.count("progress") == 8
                assert non_sp_types.count("complete") == 1

                # Verify ordering: steps and progress alternate (step N, progress N)
                step_progress_msgs = [
                    m
                    for m in non_solver_progress_msgs
                    if m["type"] in ("step", "progress")
                ]
                for i in range(0, len(step_progress_msgs), 2):
                    step_msg = step_progress_msgs[i]
                    prog_msg = step_progress_msgs[i + 1]
                    assert step_msg["type"] == "step"
                    assert prog_msg["type"] == "progress"
                    assert (
                        step_msg["payload"]["stepNumber"] == prog_msg["step"]
                    )

    def test_start_with_target_date_filters_visits_by_date(
        self,
        client,
        sample_carers,
        sample_patients,
        sample_constraints,
        sample_travel_matrix,
        sample_result,
    ):
        """Sending targetDate in start message fetches visits for that date only."""
        target_date = "2025-07-14"
        visit_dicts = [
            {
                "id": 1,
                "patient_id": 1,
                "patient_name": "Bob",
                "duration_minutes": 30,
                "window_start": "09:00",
                "window_end": "10:00",
                "required_skills": ["medication"],
                "preferred_time": "09:15",
                "is_cancelled": False,
                "target_date": target_date,
                "contract_id": 1,
            },
            {
                "id": 2,
                "patient_id": 1,
                "patient_name": "Bob",
                "duration_minutes": 30,
                "window_start": "14:00",
                "window_end": "15:00",
                "required_skills": ["medication"],
                "preferred_time": "14:15",
                "is_cancelled": True,  # Should be excluded
                "target_date": target_date,
                "contract_id": 1,
            },
        ]

        with (
            patch(
                "backend.app.routes.websocket.get_carers",
                new_callable=AsyncMock,
                return_value=sample_carers,
            ),
            patch(
                "backend.app.routes.websocket.get_patients",
                new_callable=AsyncMock,
                return_value=sample_patients,
            ),
            patch(
                "backend.app.routes.websocket.get_visits_by_date",
                new_callable=AsyncMock,
                return_value=visit_dicts,
            ) as mock_get_by_date,
            patch(
                "backend.app.routes.websocket.get_visits",
                new_callable=AsyncMock,
            ) as mock_get_all,
            patch(
                "backend.app.routes.websocket.get_constraints",
                new_callable=AsyncMock,
                return_value=sample_constraints,
            ),
            patch(
                "backend.app.routes.websocket.GoogleMapsClient"
            ) as mock_maps_cls,
            patch(
                "backend.app.routes.websocket.OptimisationEngine"
            ) as mock_engine_cls,
        ):
            mock_maps_instance = mock_maps_cls.return_value
            mock_maps_instance.get_distance_matrix = AsyncMock(
                return_value=sample_travel_matrix
            )
            mock_engine_instance = mock_engine_cls.return_value
            mock_engine_instance.run = AsyncMock(return_value=sample_result)

            with client.websocket_connect("/ws/optimise") as ws:
                ws.send_json({"type": "start", "targetDate": target_date})

                # Collect messages until we get "complete"
                messages = []
                for _ in range(50):
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "complete":
                        break

                # Verify optimisation completed
                complete_msgs = [m for m in messages if m["type"] == "complete"]
                assert len(complete_msgs) == 1

                # Verify get_visits_by_date was called with the target date
                mock_get_by_date.assert_called_once_with(target_date)
                # Verify get_visits (all visits) was NOT called
                mock_get_all.assert_not_called()

                # Verify engine received only non-cancelled visits (1 out of 2)
                engine_call_kwargs = mock_engine_instance.run.call_args
                visits_passed = engine_call_kwargs.kwargs.get(
                    "visits"
                ) or engine_call_kwargs[1].get("visits", engine_call_kwargs[0][1] if len(engine_call_kwargs[0]) > 1 else None)
                if visits_passed is None:
                    # Try positional args
                    visits_passed = engine_call_kwargs[0][1]
                assert len(visits_passed) == 1
                assert visits_passed[0].id == 1

    def test_start_without_target_date_uses_all_visits(
        self,
        client,
        sample_carers,
        sample_patients,
        sample_visits,
        sample_constraints,
        sample_travel_matrix,
        sample_result,
    ):
        """Without targetDate, falls back to using all non-cancelled visits (backward compat)."""
        with (
            patch(
                "backend.app.routes.websocket.get_carers",
                new_callable=AsyncMock,
                return_value=sample_carers,
            ),
            patch(
                "backend.app.routes.websocket.get_patients",
                new_callable=AsyncMock,
                return_value=sample_patients,
            ),
            patch(
                "backend.app.routes.websocket.get_visits",
                new_callable=AsyncMock,
                return_value=sample_visits,
            ) as mock_get_all,
            patch(
                "backend.app.routes.websocket.get_visits_by_date",
                new_callable=AsyncMock,
            ) as mock_get_by_date,
            patch(
                "backend.app.routes.websocket.get_constraints",
                new_callable=AsyncMock,
                return_value=sample_constraints,
            ),
            patch(
                "backend.app.routes.websocket.GoogleMapsClient"
            ) as mock_maps_cls,
            patch(
                "backend.app.routes.websocket.OptimisationEngine"
            ) as mock_engine_cls,
        ):
            mock_maps_instance = mock_maps_cls.return_value
            mock_maps_instance.get_distance_matrix = AsyncMock(
                return_value=sample_travel_matrix
            )
            mock_engine_instance = mock_engine_cls.return_value
            mock_engine_instance.run = AsyncMock(return_value=sample_result)

            with client.websocket_connect("/ws/optimise") as ws:
                ws.send_json({"type": "start"})

                # Collect messages until complete
                messages = []
                for _ in range(50):
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "complete":
                        break

                complete_msgs = [m for m in messages if m["type"] == "complete"]
                assert len(complete_msgs) == 1

                # Verify get_visits was called (all visits path)
                mock_get_all.assert_called_once()
                # Verify get_visits_by_date was NOT called
                mock_get_by_date.assert_not_called()

    def test_start_with_target_date_no_scheduled_visits_sends_error(
        self,
        client,
        sample_carers,
        sample_patients,
        sample_constraints,
    ):
        """When targetDate has only cancelled visits, error message is sent."""
        target_date = "2025-07-14"
        # All visits are cancelled
        visit_dicts = [
            {
                "id": 1,
                "patient_id": 1,
                "patient_name": "Bob",
                "duration_minutes": 30,
                "window_start": "09:00",
                "window_end": "10:00",
                "required_skills": ["medication"],
                "preferred_time": "09:15",
                "is_cancelled": True,
                "target_date": target_date,
                "contract_id": 1,
            },
        ]

        with (
            patch(
                "backend.app.routes.websocket.get_carers",
                new_callable=AsyncMock,
                return_value=sample_carers,
            ),
            patch(
                "backend.app.routes.websocket.get_patients",
                new_callable=AsyncMock,
                return_value=sample_patients,
            ),
            patch(
                "backend.app.routes.websocket.get_visits_by_date",
                new_callable=AsyncMock,
                return_value=visit_dicts,
            ),
            patch(
                "backend.app.routes.websocket.get_constraints",
                new_callable=AsyncMock,
                return_value=sample_constraints,
            ),
        ):
            with client.websocket_connect("/ws/optimise") as ws:
                # Consume the deprecation notice sent on connect
                deprecation_msg = ws.receive_json()
                assert deprecation_msg["type"] == "deprecation_notice"

                ws.send_json({"type": "start", "targetDate": target_date})
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert "No visits" in msg["message"]

    def test_pause_and_resume_messages(self, client):
        """Pause and resume messages are accepted without error."""
        with client.websocket_connect("/ws/optimise") as ws:
            # These should not cause errors even without an active optimisation
            ws.send_json({"type": "pause"})
            ws.send_json({"type": "resume"})
            # Connection should still be alive; send another message
            ws.send_json({"type": "pause"})
            # If we get here without exception, pause/resume are handled
