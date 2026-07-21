# Implementation Plan: Background Optimisation Jobs

## Overview

This plan converts the optimisation solver from a WebSocket-bound flow into a persistent background job system using SQLite storage, REST API endpoints, SSE notifications, and data fingerprinting for staleness detection. Each task builds incrementally, starting with the data layer and progressing through services, routes, and integration with the existing optimiser.

## Tasks

- [x] 1. Database schema and migration
  - [x] 1.1 Add optimisation_jobs table to schema.sql
    - Add the `optimisation_jobs` table with all columns from the design (id, status, visit_ids, fingerprint columns, progress columns, result_json, error_message, staleness fields, timestamps, cancelled_at)
    - Add CHECK constraint for status enum (queued, running, completed, failed, stale, cancelled)
    - Add indexes on status and created_at
    - _Requirements: 1.1, 1.2, 7.1_

  - [x] 1.2 Update database.py to apply the new schema on startup
    - The existing `init_db()` uses `CREATE TABLE IF NOT EXISTS` via `executescript`, so the new table will be picked up automatically
    - Verify the schema.sql changes are applied correctly on app start
    - _Requirements: 1.2_

- [x] 2. Pydantic models for job API
  - [x] 2.1 Create backend/app/models/job.py with all request/response models
    - Implement `JobCreateRequest` (visit_ids: list[int] | None)
    - Implement `JobCreateResponse` (job_id: str)
    - Implement `JobProgress` (job_id, status, elapsed_seconds, percentage_complete with Field(ge=0, le=100), solutions_found, current_best_score, is_stale, stale_tables)
    - Implement `JobSummary` (job_id, status, created_at, started_at, completed_at, is_stale, visit_count)
    - Implement `ActiveJobInfo` (active: bool, job_id, status)
    - Implement `JobNotificationEvent` (event_type, job_id, message, error_summary)
    - _Requirements: 2.1, 4.4, 7.1_

  - [ ]* 2.2 Write property test for progress response field validity
    - **Property 4: Progress response contains all required fields with valid ranges**
    - **Validates: Requirements 2.1, 4.4**

- [x] 3. FingerprintService implementation
  - [x] 3.1 Create backend/app/services/fingerprint.py
    - Implement `DataFingerprint` dataclass with carers_max, visits_max, patients_max, constraints_max (str | None)
    - Implement `differs_from(self, other: DataFingerprint) -> tuple[bool, dict[str, bool]]` method
    - Implement `FingerprintService` class with `async def compute(self) -> DataFingerprint` using a single transaction to SELECT MAX(updated_at) from each source table
    - Handle empty tables (NULL result) correctly
    - _Requirements: 4.1, 4.2_

  - [ ]* 3.2 Write property test for fingerprint computation
    - **Property 5: Fingerprint correctly captures max(updated_at) per source table**
    - **Validates: Requirements 4.1**

  - [ ]* 3.3 Write property test for fingerprint comparison
    - **Property 6: Staleness detection on fingerprint divergence**
    - **Validates: Requirements 4.2, 4.3, 5.4**

- [x] 4. Checkpoint - Ensure data layer and models pass tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. JobRegistry service (core lifecycle management)
  - [x] 5.1 Create backend/app/services/job_registry.py with JobRegistry class
    - Implement `create_job(visit_ids)` — check for active job (raise JobConflictError if exists), compute fingerprint, INSERT into optimisation_jobs with status=queued, return UUID v4
    - Implement `get_job(job_id)` — SELECT from optimisation_jobs by id
    - Implement `get_job_progress(job_id)` — return JobProgress from DB row
    - Implement `list_jobs()` — SELECT all jobs ordered by created_at DESC
    - Implement `check_active_job()` — query for jobs with status queued/running
    - Implement `update_progress(job_id, progress)` — UPDATE progress columns in DB
    - Implement `cancel_job(job_id)` — set status=cancelled, task.cancel(), honour completion race
    - Implement `cleanup_old_jobs()` — remove oldest beyond 20-job limit, retain jobs < 24h old
    - Store asyncio.Task reference per active job for cancellation support
    - Implement SSE subscriber management (asyncio.Queue per client, notify method)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 5.2 Write property test for job creation record validity
    - **Property 1: Job creation produces a valid record**
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 5.3 Write property test for single active job invariant
    - **Property 10: Single active job invariant with conflict enforcement**
    - **Validates: Requirements 7.4, 7.5**

  - [ ]* 5.4 Write property test for cleanup invariants
    - **Property 9: Cleanup retains at most 20 jobs and preserves recent jobs**
    - **Validates: Requirements 7.2, 7.3**

  - [ ]* 5.5 Write property test for cancellation transition
    - **Property 11: Cancellation transitions job to "cancelled" with no stored results**
    - **Validates: Requirements 7.6**

- [x] 6. Background task execution runner
  - [x] 6.1 Implement _execute_job coroutine in job_registry.py
    - Update status to "running" with started_at timestamp
    - Fetch source data (carers, visits, patients, constraints) from repositories
    - Build travel matrix via GoogleMapsClient with progress reporting
    - Run OptimisationEngine with JobProgressAdapter
    - On success: recompute fingerprint, compare with creation fingerprint, set status to completed or stale
    - On failure: store error_message (truncated to 1000 chars), set status to failed
    - On asyncio.CancelledError: set status to cancelled, clean up
    - Emit SSE notification on completion/failure/stale
    - Call cleanup_old_jobs after job finishes
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 4.2, 4.3_

  - [ ]* 6.2 Write property test for error string truncation
    - **Property 3: Error and notification strings are truncated to their respective limits**
    - **Validates: Requirements 1.5, 3.2**

  - [ ]* 6.3 Write property test for completion stores valid result
    - **Property 2: Completion stores a valid OptimisationResult**
    - **Validates: Requirements 1.4**

- [x] 7. JobProgressAdapter bridging ProgressService to JobRegistry
  - [x] 7.1 Create JobProgressAdapter class in backend/app/services/job_registry.py
    - Implement the same interface as ProgressService emit methods (start_solver_phase, emit_solver_tick, on_solution_found, complete_solver_phase, fail_solver_phase)
    - Write progress updates to JobRegistry via update_progress (percentage_complete, elapsed_seconds, solutions_found, current_best_score)
    - Bridge distance matrix phase progress as well
    - _Requirements: 2.1, 2.3_

- [x] 8. Checkpoint - Ensure services layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. REST API endpoints
  - [x] 9.1 Create backend/app/routes/jobs.py with POST /api/jobs endpoint
    - Accept JobCreateRequest body
    - Call job_registry.create_job(visit_ids)
    - Return 202 Accepted with JobCreateResponse
    - Handle JobConflictError → 409 with active_job_id
    - Handle no visits available → 422
    - _Requirements: 1.1, 7.4, 7.5_

  - [x] 9.2 Add GET /api/jobs endpoint for job listing
    - Call job_registry.list_jobs()
    - Return 200 with list of JobSummary ordered by created_at descending
    - _Requirements: 7.1_

  - [x] 9.3 Add GET /api/jobs/active endpoint for edit guard
    - Call job_registry.check_active_job()
    - Return 200 with ActiveJobInfo (active: bool, job_id if active)
    - _Requirements: 6.1, 6.5_

  - [x] 9.4 Add GET /api/jobs/{job_id}/progress endpoint
    - Call job_registry.get_job_progress(job_id)
    - Return 200 with JobProgress or 404 if not found
    - _Requirements: 2.1, 2.2_

  - [x] 9.5 Add DELETE /api/jobs/{job_id} endpoint for cancellation
    - Call job_registry.cancel_job(job_id)
    - Return 200 on success, 404 if not found, 409 if already completed/failed
    - _Requirements: 7.6_

  - [ ]* 9.6 Write property test for active job check
    - **Property 7: Active job check accurately reflects registry state**
    - **Validates: Requirements 6.1, 6.5**

  - [ ]* 9.7 Write property test for job list ordering
    - **Property 8: Job list is ordered by creation timestamp descending**
    - **Validates: Requirements 7.1**

- [x] 10. SSE notification endpoint
  - [x] 10.1 Add GET /api/jobs/notifications SSE endpoint in backend/app/routes/jobs.py
    - Use FastAPI StreamingResponse with content_type text/event-stream
    - Register client with asyncio.Queue in JobRegistry subscriber set
    - Send heartbeat comment (`: heartbeat\n\n`) every 15 seconds
    - Support Last-Event-ID header for replay from bounded buffer (last 10 events, max 5 min old)
    - Clean up subscriber queue on client disconnect
    - Format events as `event: job_status\ndata: {JSON}\n\n`
    - _Requirements: 3.1, 3.2, 3.6_

- [x] 11. Register jobs router in main.py
  - [x] 11.1 Wire jobs router into FastAPI application
    - Import and include the jobs router in backend/app/main.py
    - Initialize JobRegistry as application state (lifespan or startup event)
    - Inject JobRegistry dependency into route handlers
    - _Requirements: 1.1, 2.1_

- [x] 12. Checkpoint - Ensure API endpoints tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Integration with existing optimiser
  - [x] 13.1 Integrate OptimisationEngine with JobProgressAdapter in _execute_job
    - Modify the _execute_job runner to create a JobProgressAdapter instance
    - Pass the adapter as the `progress` parameter to OptimisationEngine.run()
    - Implement lightweight on_step and on_progress callbacks that are no-ops (background job doesn't need animation steps)
    - _Requirements: 1.3, 1.4, 2.3_

  - [x] 13.2 Add deprecation notice to WebSocket endpoint
    - Add a deprecation log warning on WebSocket connection
    - Include a `deprecated: true` field in the WebSocket accept/handshake response headers or initial message
    - Add code comment documenting the migration path to REST endpoints
    - _Requirements: Design decision — WebSocket deprecation path_

- [x] 14. Post-completion staleness detection
  - [x] 14.1 Implement staleness re-check on source data modification
    - Add a utility function that recomputes fingerprints for completed jobs and marks them stale if data changed
    - This can be called as a background task triggered after source data writes (carers, visits, patients, constraints endpoints)
    - Update stale_tables JSON and is_stale flag
    - Emit SSE notification for staleness transition
    - _Requirements: 5.4, 4.3_

- [ ] 15. Unit and integration tests
  - [ ]* 15.1 Write unit tests for JobRegistry (backend/tests/test_job_registry.py)
    - Test valid state transitions (queued→running→completed, queued→cancelled, running→failed, running→stale)
    - Test invalid transitions are rejected (completed→running, failed→queued)
    - Test single active job enforcement
    - Test cleanup logic preserves recent jobs
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 7.2, 7.3, 7.4_

  - [ ]* 15.2 Write unit tests for FingerprintService (backend/tests/test_fingerprint.py)
    - Test fingerprint with populated tables returns correct max timestamps
    - Test fingerprint with empty tables returns None values
    - Test differs_from correctly identifies changed tables
    - _Requirements: 4.1, 4.2_

  - [ ]* 15.3 Write route integration tests (backend/tests/test_jobs_routes.py)
    - Test POST /api/jobs returns 202 with job_id
    - Test POST /api/jobs returns 409 when active job exists
    - Test GET /api/jobs/{id}/progress returns 200 with valid schema
    - Test GET /api/jobs/{id}/progress returns 404 for unknown job
    - Test GET /api/jobs returns list ordered descending
    - Test GET /api/jobs/active returns correct state
    - Test DELETE /api/jobs/{id} cancels active job
    - Test SSE endpoint delivers notification on job completion
    - _Requirements: 1.1, 2.1, 2.2, 7.1, 7.5, 7.6_

- [x] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (Properties 1–11)
- Unit tests validate specific examples and edge cases
- The design uses Python (FastAPI, Pydantic, aiosqlite, Hypothesis) throughout — no language selection needed
- The existing ProgressService is coupled to WebSocket sessions; the JobProgressAdapter decouples it for background execution
- SSE is chosen over WebSocket for notifications as it's lighter weight for one-way server→client push

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.1"] },
    { "id": 2, "tasks": ["3.2", "3.3", "5.1"] },
    { "id": 3, "tasks": ["5.2", "5.3", "5.4", "5.5", "6.1"] },
    { "id": 4, "tasks": ["6.2", "6.3", "7.1"] },
    { "id": 5, "tasks": ["9.1", "9.2", "9.3", "9.4", "9.5"] },
    { "id": 6, "tasks": ["9.6", "9.7", "10.1", "11.1"] },
    { "id": 7, "tasks": ["13.1", "13.2", "14.1"] },
    { "id": 8, "tasks": ["15.1", "15.2", "15.3"] }
  ]
}
```
