"""Fine-grained progress reporting for the optimisation pipeline.

Emits structured solver_progress WebSocket messages covering both
the distance matrix retrieval phase and the OR-Tools solver phase.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.app.models.optimisation import TravelTimeMatrix
from backend.app.services.maps_client import GoogleMapsClient, MapsAPIError

if TYPE_CHECKING:
    from backend.app.routes.websocket import OptimisationSession

logger = logging.getLogger(__name__)


@dataclass
class SolverPhaseState:
    """Tracks solver phase progress on the async side."""

    start_time: float
    time_limit_seconds: int
    solutions_found: int = 0
    current_best_score: float | None = None
    completed: bool = False
    error: str | None = None


@dataclass
class DistanceMatrixPhaseState:
    """Tracks distance matrix phase progress."""

    start_time: float
    total_pairs: int
    pairs_completed: int = 0
    status: str = "in_progress"  # "in_progress" | "complete" | "failed"
    error: str | None = None


def _clamp_time_limit(raw_seconds: int) -> tuple[int, bool]:
    """Clamp time limit to valid range [1, 3600].

    Returns:
        A tuple of (clamped_value, was_clamped).
    """
    if raw_seconds < 1:
        return 1, True
    if raw_seconds > 3600:
        return 3600, True
    return raw_seconds, False


class ProgressService:
    """Manages fine-grained progress reporting for an optimisation session.

    Emits solver_progress messages over WebSocket for both the distance matrix
    and solver phases. All emission methods check session.disconnected before
    sending and handle failures gracefully.
    """

    def __init__(
        self,
        session: OptimisationSession,
        time_limit_seconds: int,
    ) -> None:
        """Initialise the progress service.

        Args:
            session: The WebSocket session to emit messages on.
            time_limit_seconds: Configured solver time limit (clamped to 1-3600).
        """
        self._session = session
        self._time_limit_seconds, self._time_limit_was_clamped = _clamp_time_limit(
            time_limit_seconds
        )
        self._raw_time_limit = time_limit_seconds
        self._solver_state: SolverPhaseState | None = None
        self._dm_state: DistanceMatrixPhaseState | None = None

    @property
    def time_limit_seconds(self) -> int:
        """The clamped time limit in seconds."""
        return self._time_limit_seconds

    @property
    def time_limit_was_clamped(self) -> bool:
        """Whether the time limit was clamped from its original value."""
        return self._time_limit_was_clamped

    # ------------------------------------------------------------------
    # Distance Matrix Phase
    # ------------------------------------------------------------------

    async def start_distance_matrix_phase(self, total_pairs: int) -> None:
        """Begin the distance matrix phase, emit initial solver_progress message.

        Args:
            total_pairs: Total number of origin-destination pairs to compute.
        """
        self._dm_state = DistanceMatrixPhaseState(
            start_time=time.monotonic(),
            total_pairs=total_pairs,
        )
        await self._emit_dm_message(elapsed_seconds=0)

    async def tick_distance_matrix(self, elapsed_seconds: int) -> None:
        """Emit a distance matrix heartbeat with elapsed time.

        Args:
            elapsed_seconds: Whole seconds elapsed since phase start.
        """
        await self._emit_dm_message(elapsed_seconds=elapsed_seconds)

    async def complete_distance_matrix(self, elapsed_seconds: int) -> None:
        """Emit final distance_matrix message with status='complete'.

        Args:
            elapsed_seconds: Whole seconds elapsed since phase start.
        """
        if self._dm_state is not None:
            self._dm_state.status = "complete"
        await self._emit_dm_message(elapsed_seconds=elapsed_seconds)

    async def fail_distance_matrix(self, elapsed_seconds: int, error: str) -> None:
        """Emit final distance_matrix message with status='failed'.

        Args:
            elapsed_seconds: Whole seconds elapsed since phase start.
            error: Error description (truncated to 500 chars).
        """
        truncated_error = error[:500]
        if self._dm_state is not None:
            self._dm_state.status = "failed"
            self._dm_state.error = truncated_error
        await self._emit_dm_message(
            elapsed_seconds=elapsed_seconds, error=truncated_error
        )

    # ------------------------------------------------------------------
    # Solver Phase
    # ------------------------------------------------------------------

    async def start_solver_phase(self) -> None:
        """Begin the solver phase, emit first solver progress message.

        Records start_time and emits initial message with time_limit_seconds,
        percentage_complete=0, solutions_found=0, current_best_score=None.
        Includes a warning field if time_limit was clamped.
        """
        self._solver_state = SolverPhaseState(
            start_time=time.monotonic(),
            time_limit_seconds=self._time_limit_seconds,
        )
        await self._emit_solver_message(elapsed_seconds=0)

    async def emit_solver_tick(self, elapsed_seconds: int) -> None:
        """Emit a solver progress tick with calculated percentage.

        Args:
            elapsed_seconds: Whole seconds elapsed since solver start.
        """
        await self._emit_solver_message(elapsed_seconds=elapsed_seconds)

    async def on_solution_found(
        self, solutions_found: int, best_score: float
    ) -> None:
        """Called when the solver discovers an improved solution.

        Updates state and emits solver message with updated solutions_found
        and current_best_score.

        Args:
            solutions_found: Total number of solutions found so far.
            best_score: The objective score of the best solution.
        """
        if self._solver_state is not None:
            self._solver_state.solutions_found = solutions_found
            self._solver_state.current_best_score = best_score
        elapsed = 0
        if self._solver_state is not None:
            elapsed = int(time.monotonic() - self._solver_state.start_time)
        await self._emit_solver_message(elapsed_seconds=elapsed)

    async def complete_solver_phase(
        self,
        elapsed_seconds: int,
        solutions_found: int,
        best_score: float | None,
    ) -> None:
        """Emit final solver progress message with percentage_complete=100.

        Args:
            elapsed_seconds: Whole seconds elapsed since solver start.
            solutions_found: Total solutions found during the search.
            best_score: Best objective score, or None if no solutions found.
        """
        if self._solver_state is not None:
            self._solver_state.solutions_found = solutions_found
            self._solver_state.current_best_score = best_score
            self._solver_state.completed = True
        await self._emit_solver_message(
            elapsed_seconds=elapsed_seconds, force_complete=True
        )

    async def fail_solver_phase(self, elapsed_seconds: int, error: str) -> None:
        """Emit solver phase error message.

        Args:
            elapsed_seconds: Whole seconds elapsed since solver start.
            error: Error description.
        """
        if self._solver_state is not None:
            self._solver_state.error = error
            self._solver_state.completed = True
        await self._emit_solver_message(
            elapsed_seconds=elapsed_seconds, error=error
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Clean up resources. No-op for now, will be extended in later tasks."""
        pass

    # ------------------------------------------------------------------
    # Internal emission helpers
    # ------------------------------------------------------------------

    async def _emit_dm_message(
        self,
        elapsed_seconds: int,
        error: str | None = None,
    ) -> None:
        """Build and send a distance_matrix phase solver_progress message."""
        if self._session.disconnected:
            return

        state = self._dm_state
        if state is None:
            return

        message: dict = {
            "type": "solver_progress",
            "phase": "distance_matrix",
            "elapsed_seconds": elapsed_seconds,
            "total_pairs": state.total_pairs,
            "pairs_completed": state.pairs_completed,
            "status": state.status,
        }

        if error is not None:
            message["error"] = error

        await self._safe_send(message)

    async def _emit_solver_message(
        self,
        elapsed_seconds: int,
        force_complete: bool = False,
        error: str | None = None,
    ) -> None:
        """Build and send a solver phase solver_progress message."""
        if self._session.disconnected:
            return

        state = self._solver_state
        if state is None:
            return

        # Calculate percentage: min(100, floor(elapsed / time_limit * 100))
        if force_complete:
            percentage_complete = 100
        else:
            percentage_complete = min(
                100, math.floor(elapsed_seconds / state.time_limit_seconds * 100)
            )

        message: dict = {
            "type": "solver_progress",
            "phase": "solver",
            "elapsed_seconds": elapsed_seconds,
            "time_limit_seconds": state.time_limit_seconds,
            "percentage_complete": percentage_complete,
            "solutions_found": state.solutions_found,
            "current_best_score": state.current_best_score,
        }

        # Include warning if time limit was clamped (on first message or always)
        if self._time_limit_was_clamped:
            if self._raw_time_limit < 1:
                message["warning"] = "time_limit clamped to minimum 1s"
            else:
                message["warning"] = "time_limit clamped to maximum 3600s"

        if error is not None:
            message["error"] = error

        await self._safe_send(message)

    async def _safe_send(self, message: dict) -> None:
        """Send a message via the session, logging and swallowing any errors.

        This ensures that a failed progress emission never propagates
        and never disrupts subsequent message delivery.
        """
        if self._session.disconnected:
            return
        try:
            await self._session.send_json(message)
        except Exception as exc:
            logger.warning(
                "Failed to emit solver_progress message: %s", exc
            )


# ------------------------------------------------------------------
# Distance Matrix Progress Wrapper
# ------------------------------------------------------------------


async def fetch_matrix_with_progress(
    maps_client: GoogleMapsClient,
    origins: list[tuple[float, float]],
    destinations: list[tuple[float, float]],
    progress: ProgressService,
) -> TravelTimeMatrix:
    """Fetch distance matrix while emitting progress heartbeats.

    Wraps the Google Maps API call with periodic elapsed-time updates
    so the user can see progress during the distance matrix retrieval phase.

    Args:
        maps_client: The Google Maps client instance.
        origins: List of (lat, lng) tuples for origins.
        destinations: List of (lat, lng) tuples for destinations.
        progress: The ProgressService to emit heartbeats on.

    Returns:
        TravelTimeMatrix from the Google Maps API.

    Raises:
        MapsAPIError: On API failures (after emitting failure progress message).
    """
    total_pairs = len(origins) * len(destinations)
    await progress.start_distance_matrix_phase(total_pairs)
    start = time.monotonic()

    # Run the matrix fetch as a background task
    fetch_task = asyncio.create_task(
        maps_client.get_distance_matrix(origins=origins, destinations=destinations)
    )

    # Emit heartbeats every <=2 seconds while waiting
    while not fetch_task.done():
        await asyncio.sleep(2.0)
        if fetch_task.done():
            break
        elapsed = int(time.monotonic() - start)
        await progress.tick_distance_matrix(elapsed)

    elapsed = int(time.monotonic() - start)
    try:
        result = fetch_task.result()
        await progress.complete_distance_matrix(elapsed)
        return result
    except MapsAPIError as e:
        await progress.fail_distance_matrix(elapsed, str(e.message)[:500])
        raise
