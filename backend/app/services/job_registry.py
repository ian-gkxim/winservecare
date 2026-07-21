"""Background optimisation job registry.

Manages the lifecycle of background optimisation jobs including creation,
progress tracking, cancellation, cleanup, and SSE subscriber notification.
"""

import asyncio
import json
import math
import time
import uuid
from datetime import datetime, timezone

from backend.app.db.database import get_db
from backend.app.models.job import ActiveJobInfo, JobProgress, JobSummary
from backend.app.services.fingerprint import DataFingerprint, FingerprintService


# --- Custom Exceptions ---


class JobConflictError(Exception):
    """Raised when trying to create a job while one is already active."""

    def __init__(self, active_job_id: str):
        self.active_job_id = active_job_id
        super().__init__(f"Job already active: {active_job_id}")


class JobNotFoundError(Exception):
    """Raised when a job ID doesn't exist."""

    pass


class JobNotActiveError(Exception):
    """Raised when trying to cancel a non-active job."""

    def __init__(self, current_status: str):
        self.current_status = current_status
        super().__init__(f"Job is not active, current status: {current_status}")


# --- JobProgressAdapter ---


class JobProgressAdapter:
    """Adapts ProgressService interface to write progress to JobRegistry.

    Bridges the same interface that OptimisationEngine.run() expects from
    a progress object, but instead of emitting WebSocket messages, writes
    progress updates to the JobRegistry (and thus to the database).
    """

    def __init__(self, job_registry: "JobRegistry", job_id: str) -> None:
        self._registry = job_registry
        self._job_id = job_id
        self._time_limit_seconds = 10  # default; set from config if needed
        self._start_time: float = 0.0

    @property
    def time_limit_seconds(self) -> int:
        """The time limit in seconds for percentage calculation."""
        return self._time_limit_seconds

    @property
    def time_limit_was_clamped(self) -> bool:
        """Whether the time limit was clamped (always False for background jobs)."""
        return False

    async def start_distance_matrix_phase(self, total_pairs: int) -> None:
        """No-op for background jobs (no WebSocket to emit to)."""
        pass

    async def tick_distance_matrix(self, elapsed_seconds: int) -> None:
        """No-op for background jobs."""
        pass

    async def complete_distance_matrix(self, elapsed_seconds: int) -> None:
        """No-op for background jobs."""
        pass

    async def fail_distance_matrix(self, elapsed_seconds: int, error: str) -> None:
        """No-op for background jobs."""
        pass

    async def start_solver_phase(self) -> None:
        """Record solver start time."""
        self._start_time = time.monotonic()

    async def emit_solver_tick(self, elapsed_seconds: int) -> None:
        """Update progress in the registry."""
        percentage = min(100, math.floor(elapsed_seconds / self._time_limit_seconds * 100))
        await self._registry.update_progress(
            self._job_id, elapsed_seconds, percentage, 0, None
        )

    async def on_solution_found(self, solutions_found: int, best_score: float) -> None:
        """Update progress with new solution info."""
        elapsed = int(time.monotonic() - self._start_time) if self._start_time else 0
        percentage = min(100, math.floor(elapsed / self._time_limit_seconds * 100))
        await self._registry.update_progress(
            self._job_id, elapsed, percentage, solutions_found, best_score
        )

    async def complete_solver_phase(
        self, elapsed_seconds: int, solutions_found: int, best_score: float | None
    ) -> None:
        """Update progress to 100% complete."""
        await self._registry.update_progress(
            self._job_id, elapsed_seconds, 100, solutions_found, best_score
        )

    async def fail_solver_phase(self, elapsed_seconds: int, error: str) -> None:
        """No-op — error handling is done in _execute_job."""
        pass

    async def stop(self) -> None:
        """No-op cleanup."""
        pass


# --- JobRegistry ---


class JobRegistry:
    """Manages background optimisation job lifecycle."""

    def __init__(self) -> None:
        self._active_task: asyncio.Task | None = None
        self._active_job_id: str | None = None
        self._subscribers: list[asyncio.Queue] = []
        self._notification_buffer: list[tuple[str, dict]] = []
        self._fingerprint_service = FingerprintService()

    async def create_job(self, visit_ids: list[int] | None = None) -> str:
        """Create a new optimisation job.

        Checks for an active job, computes data fingerprint, inserts a new
        record into the database, and launches the background execution task.

        Args:
            visit_ids: Optional list of visit IDs to optimise. None means all.

        Returns:
            The UUID v4 identifier of the created job.

        Raises:
            JobConflictError: If a queued or running job already exists.
        """
        # Check for active job
        active = await self.check_active_job()
        if active.active:
            raise JobConflictError(active.job_id)

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Compute data fingerprint
        fingerprint = await self._fingerprint_service.compute()

        # Serialize visit_ids
        visit_ids_json = json.dumps(visit_ids if visit_ids is not None else [])

        # Timestamp
        now = datetime.now(timezone.utc).isoformat()

        # Insert into database
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO optimisation_jobs (
                    id, status, visit_ids,
                    fingerprint_carers, fingerprint_visits,
                    fingerprint_patients, fingerprint_constraints,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    "queued",
                    visit_ids_json,
                    fingerprint.carers_max,
                    fingerprint.visits_max,
                    fingerprint.patients_max,
                    fingerprint.constraints_max,
                    now,
                ),
            )
            await db.commit()

        # Cleanup old jobs
        await self.cleanup_old_jobs()

        # Launch background task
        self._active_job_id = job_id
        self._active_task = asyncio.create_task(self._execute_job(job_id, visit_ids))

        return job_id

    async def get_job(self, job_id: str) -> dict | None:
        """Get full job row from DB.

        Args:
            job_id: The UUID of the job to retrieve.

        Returns:
            A dict of the job row, or None if not found.
        """
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM optimisation_jobs WHERE id = ?", (job_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            # Convert sqlite3.Row to dict
            return dict(row)

    async def get_job_progress(self, job_id: str) -> JobProgress | None:
        """Build JobProgress from DB row.

        Args:
            job_id: The UUID of the job.

        Returns:
            A JobProgress model, or None if the job is not found.
        """
        row = await self.get_job(job_id)
        if row is None:
            return None

        # Parse stale_tables from JSON
        stale_tables = None
        if row.get("stale_tables"):
            stale_tables = json.loads(row["stale_tables"])

        return JobProgress(
            job_id=row["id"],
            status=row["status"],
            elapsed_seconds=row["elapsed_seconds"],
            percentage_complete=row["percentage_complete"],
            solutions_found=row["solutions_found"],
            current_best_score=row["current_best_score"],
            is_stale=bool(row["is_stale"]),
            stale_tables=stale_tables,
        )

    async def list_jobs(self) -> list[JobSummary]:
        """List all jobs ordered by created_at DESC.

        Returns:
            A list of JobSummary models for all retained jobs.
        """
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM optimisation_jobs ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()

        summaries = []
        for row in rows:
            row_dict = dict(row)
            # Compute visit_count from the stored JSON array
            visit_ids_json = row_dict.get("visit_ids", "[]")
            try:
                visit_ids = json.loads(visit_ids_json) if visit_ids_json else []
            except (json.JSONDecodeError, TypeError):
                visit_ids = []

            summaries.append(
                JobSummary(
                    job_id=row_dict["id"],
                    status=row_dict["status"],
                    created_at=row_dict["created_at"],
                    started_at=row_dict.get("started_at"),
                    completed_at=row_dict.get("completed_at"),
                    is_stale=bool(row_dict["is_stale"]),
                    visit_count=len(visit_ids),
                )
            )
        return summaries

    async def check_active_job(self) -> ActiveJobInfo:
        """Return ActiveJobInfo with active=True if a queued/running job exists.

        Returns:
            ActiveJobInfo indicating whether an active job exists.
        """
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, status FROM optimisation_jobs WHERE status IN ('queued', 'running') LIMIT 1"
            )
            row = await cursor.fetchone()

        if row is None:
            return ActiveJobInfo(active=False)

        row_dict = dict(row)
        return ActiveJobInfo(
            active=True, job_id=row_dict["id"], status=row_dict["status"]
        )

    async def update_progress(
        self,
        job_id: str,
        elapsed_seconds: int,
        percentage_complete: int,
        solutions_found: int,
        current_best_score: float | None,
    ) -> None:
        """Update progress columns in DB for a running job.

        Args:
            job_id: The UUID of the job to update.
            elapsed_seconds: Total elapsed seconds.
            percentage_complete: Completion percentage (0-100).
            solutions_found: Number of solutions found so far.
            current_best_score: Current best objective score, or None.
        """
        async with get_db() as db:
            await db.execute(
                """
                UPDATE optimisation_jobs
                SET elapsed_seconds = ?,
                    percentage_complete = ?,
                    solutions_found = ?,
                    current_best_score = ?
                WHERE id = ?
                """,
                (
                    elapsed_seconds,
                    percentage_complete,
                    solutions_found,
                    current_best_score,
                    job_id,
                ),
            )
            await db.commit()

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel an active job.

        Verifies the job exists and is queued/running, cancels the asyncio
        task if running, updates the status to 'cancelled', and clears
        internal references.

        Args:
            job_id: The UUID of the job to cancel.

        Returns:
            True on successful cancellation.

        Raises:
            JobNotFoundError: If the job doesn't exist.
            JobNotActiveError: If the job is not in a cancellable state.
        """
        row = await self.get_job(job_id)
        if row is None:
            raise JobNotFoundError(f"Job not found: {job_id}")

        if row["status"] not in ("queued", "running"):
            raise JobNotActiveError(row["status"])

        # Cancel the asyncio task if this is the active job
        if self._active_task and self._active_job_id == job_id:
            self._active_task.cancel()

        # Update status in DB
        now = datetime.now(timezone.utc).isoformat()
        async with get_db() as db:
            await db.execute(
                """
                UPDATE optimisation_jobs
                SET status = 'cancelled', cancelled_at = ?
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                (now, job_id),
            )
            await db.commit()

        # Clear active references
        if self._active_job_id == job_id:
            self._active_task = None
            self._active_job_id = None

        return True

    async def cleanup_old_jobs(self) -> None:
        """Remove oldest jobs beyond 20-job limit.

        Preserves:
        - Jobs less than 24 hours old (by completed_at)
        - Jobs with status queued or running
        Removes the oldest jobs (by completed_at) that exceed the 20-job limit.
        """
        async with get_db() as db:
            # Get all jobs that are candidates for removal:
            # - Not queued or running
            # - Completed more than 24 hours ago
            # Ordered by completed_at ascending (oldest first)
            cursor = await db.execute(
                """
                SELECT id FROM optimisation_jobs
                WHERE status NOT IN ('queued', 'running')
                  AND completed_at IS NOT NULL
                  AND datetime(completed_at) < datetime('now', '-24 hours')
                ORDER BY completed_at ASC
                """
            )
            old_removable = await cursor.fetchall()

            # Count total jobs
            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM optimisation_jobs"
            )
            total_count_row = await count_cursor.fetchone()
            total_count = total_count_row[0] if total_count_row else 0

            # Only remove if we exceed the 20-job limit
            if total_count > 20:
                excess = total_count - 20
                # Remove at most 'excess' jobs from the removable set
                to_remove = [dict(r)["id"] for r in old_removable[:excess]]
                if to_remove:
                    placeholders = ",".join("?" for _ in to_remove)
                    await db.execute(
                        f"DELETE FROM optimisation_jobs WHERE id IN ({placeholders})",
                        to_remove,
                    )
                    await db.commit()

    async def notify_subscribers(self, event: dict) -> None:
        """Push an event to all SSE subscriber queues and add to replay buffer.

        Args:
            event: The event dict to send to subscribers.
        """
        # Add to replay buffer (bounded: last 10 events, max 5 min old)
        now = datetime.now(timezone.utc).isoformat()
        self._notification_buffer.append((now, event))
        # Trim to last 10
        if len(self._notification_buffer) > 10:
            self._notification_buffer = self._notification_buffer[-10:]
        # Remove entries older than 5 minutes
        cutoff = datetime.now(timezone.utc)
        self._notification_buffer = [
            (ts, ev)
            for ts, ev in self._notification_buffer
            if (cutoff - datetime.fromisoformat(ts)).total_seconds() <= 300
        ]

        # Push to all subscriber queues
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop events for full queues rather than blocking
                pass

    def subscribe(self) -> asyncio.Queue:
        """Register a new SSE subscriber and return their queue.

        Returns:
            An asyncio.Queue that will receive notification events.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue.

        Args:
            queue: The subscriber queue to remove.
        """
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    # --- Background task execution ---

    async def _execute_job(self, job_id: str, visit_ids: list[int] | None) -> None:
        """Background coroutine that runs the full optimisation pipeline.

        Steps:
        1. Update status to "running"
        2. Fetch source data (carers, visits, patients, constraints)
        3. Build travel matrix via GoogleMapsClient
        4. Run OptimisationEngine with JobProgressAdapter
        5. On success: compare fingerprints, store result, set completed/stale
        6. On failure: store error, set failed
        7. On cancellation: set cancelled
        8. Emit SSE notification on completion/failure/stale
        """
        now = datetime.now(timezone.utc).isoformat()

        try:
            # 1. Update status to "running"
            async with get_db() as db:
                await db.execute(
                    "UPDATE optimisation_jobs SET status = 'running', started_at = ? WHERE id = ?",
                    (now, job_id),
                )
                await db.commit()

            # 2. Fetch source data
            from backend.app.db.repositories import (
                get_carers,
                get_constraints,
                get_patients,
                get_visits,
            )

            carers = await get_carers()
            patients = await get_patients()
            visits = await get_visits()
            constraints = await get_constraints()

            # Filter visits if specific IDs provided
            if visit_ids:
                visit_id_set = set(visit_ids)
                visits = [v for v in visits if v.id in visit_id_set]

            if not visits:
                raise ValueError("No visits available for optimisation")
            if not carers:
                raise ValueError("No carers available for optimisation")

            # 3. Build travel matrix
            from backend.app.services.maps_client import GoogleMapsClient

            maps_client = GoogleMapsClient()
            patient_map = {p.id: p for p in patients}
            carer_locations = [(c.home_lat, c.home_lng) for c in carers]
            visit_locations = [
                (patient_map[v.patient_id].lat, patient_map[v.patient_id].lng)
                for v in visits
            ]
            all_locations = carer_locations + visit_locations

            travel_matrix = await maps_client.get_distance_matrix(
                origins=all_locations,
                destinations=all_locations,
            )

            # 4. Run optimiser with progress adapter
            from backend.app.services.optimiser import OptimisationEngine

            adapter = JobProgressAdapter(self, job_id)
            engine = OptimisationEngine()

            # No-op callbacks for step/progress (background job doesn't animate)
            async def noop_step(payload: dict) -> None:
                pass

            async def noop_progress(payload: dict) -> None:
                pass

            result = await engine.run(
                carers=carers,
                visits=visits,
                patients=patients,
                constraints=constraints,
                travel_matrix=travel_matrix,
                on_step=noop_step,
                on_progress=noop_progress,
                progress=adapter,
            )

            # 5. On success: compare fingerprints, store result
            current_fingerprint = await self._fingerprint_service.compute()

            # Retrieve creation fingerprint from the job row
            job_row = await self.get_job(job_id)
            creation_fingerprint = DataFingerprint(
                carers_max=job_row["fingerprint_carers"],
                visits_max=job_row["fingerprint_visits"],
                patients_max=job_row["fingerprint_patients"],
                constraints_max=job_row["fingerprint_constraints"],
            )

            is_different, table_diffs = current_fingerprint.differs_from(creation_fingerprint)
            final_status = "stale" if is_different else "completed"

            completed_at = datetime.now(timezone.utc).isoformat()
            result_json = result.model_dump_json()

            async with get_db() as db:
                await db.execute(
                    """
                    UPDATE optimisation_jobs
                    SET status = ?,
                        completed_at = ?,
                        percentage_complete = 100,
                        result_json = ?,
                        is_stale = ?,
                        stale_tables = ?
                    WHERE id = ?
                    """,
                    (
                        final_status,
                        completed_at,
                        result_json,
                        1 if is_different else 0,
                        json.dumps(table_diffs) if is_different else None,
                        job_id,
                    ),
                )
                await db.commit()

            # Notify subscribers
            event_type = "job_stale" if is_different else "job_completed"
            message = (
                "Optimisation complete — results may be outdated"
                if is_different
                else "Optimisation complete"
            )
            await self.notify_subscribers(
                {
                    "event_type": event_type,
                    "job_id": job_id,
                    "message": message,
                }
            )

        except asyncio.CancelledError:
            # Handle cancellation
            cancelled_at = datetime.now(timezone.utc).isoformat()
            async with get_db() as db:
                await db.execute(
                    "UPDATE optimisation_jobs SET status = 'cancelled', cancelled_at = ? WHERE id = ? AND status IN ('queued', 'running')",
                    (cancelled_at, job_id),
                )
                await db.commit()
            raise

        except Exception as e:
            # Handle errors
            error_msg = str(e)[:1000]
            failed_at = datetime.now(timezone.utc).isoformat()
            async with get_db() as db:
                await db.execute(
                    "UPDATE optimisation_jobs SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?",
                    (error_msg, failed_at, job_id),
                )
                await db.commit()

            await self.notify_subscribers(
                {
                    "event_type": "job_failed",
                    "job_id": job_id,
                    "message": "Optimisation failed",
                    "error_summary": error_msg[:200],
                }
            )

        finally:
            if self._active_job_id == job_id:
                self._active_task = None
                self._active_job_id = None


# --- Module-level utility for staleness re-check ---


async def check_and_mark_stale_jobs() -> None:
    """Re-check fingerprints for completed jobs and mark stale if data changed.

    Should be called as a background task after source data modifications
    (carers, visits, patients, constraints).
    """
    fingerprint_service = FingerprintService()
    current_fingerprint = await fingerprint_service.compute()

    async with get_db() as db:
        # Find all jobs with status 'completed' (not already stale/failed/cancelled)
        cursor = await db.execute(
            "SELECT id, fingerprint_carers, fingerprint_visits, fingerprint_patients, fingerprint_constraints FROM optimisation_jobs WHERE status = 'completed'"
        )
        rows = await cursor.fetchall()

    for row in rows:
        row_dict = dict(row)
        creation_fingerprint = DataFingerprint(
            carers_max=row_dict["fingerprint_carers"],
            visits_max=row_dict["fingerprint_visits"],
            patients_max=row_dict["fingerprint_patients"],
            constraints_max=row_dict["fingerprint_constraints"],
        )

        is_different, table_diffs = current_fingerprint.differs_from(creation_fingerprint)
        if is_different:
            async with get_db() as db:
                await db.execute(
                    """
                    UPDATE optimisation_jobs
                    SET status = 'stale', is_stale = 1, stale_tables = ?
                    WHERE id = ? AND status = 'completed'
                    """,
                    (json.dumps(table_diffs), row_dict["id"]),
                )
                await db.commit()
