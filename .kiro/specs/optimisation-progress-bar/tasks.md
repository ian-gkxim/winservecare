# Implementation Plan: Optimisation Progress Bar

## Overview

Add fine-grained progress reporting to the WinServeCare optimisation pipeline covering both the distance matrix retrieval phase and the OR-Tools solver search phase. The implementation introduces a `ProgressService` that emits structured `solver_progress` WebSocket messages, moves the solver into a background thread for non-blocking execution, and uses OR-Tools `SolverSolutionCallback` to relay intermediate solutions back to the async event loop.

## Tasks

- [x] 1. Create ProgressService and supporting data structures
  - [x] 1.1 Create `backend/app/services/progress.py` with `ProgressService` class
    - Define `SolverPhaseState` and `DistanceMatrixPhaseState` dataclasses
    - Implement `_clamp_time_limit()` helper function
    - Implement `__init__` accepting `OptimisationSession` and `time_limit_seconds`
    - Implement `start_distance_matrix_phase()`, `tick_distance_matrix()`, `complete_distance_matrix()`, `fail_distance_matrix()`
    - Implement `start_solver_phase()`, `emit_solver_tick()`, `on_solution_found()`, `complete_solver_phase()`, `fail_solver_phase()`
    - Implement `stop()` to cancel ticker tasks and release resources
    - All emission methods must check `session.disconnected` before sending
    - Failed emissions must log a warning and continue without propagating
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.5, 7.1, 7.2, 7.4_

  - [ ]* 1.2 Write unit tests for `ProgressService` in `backend/tests/test_progress_service.py`
    - Test initial state after construction
    - Test `start_distance_matrix_phase` emits correct message format
    - Test `complete_distance_matrix` emits terminal message with status "complete"
    - Test `fail_distance_matrix` emits message with status "failed" and truncated error
    - Test `start_solver_phase` emits first solver message with `time_limit_seconds`
    - Test `on_solution_found` increments `solutions_found` and updates `current_best_score`
    - Test `complete_solver_phase` emits message with `percentage_complete: 100`
    - Test no-solution edge case emits `solutions_found: 0`
    - Test `_clamp_time_limit` clamps values outside [1, 3600]
    - Test failed emission does not propagate exception
    - _Requirements: 1.2, 1.3, 1.4, 2.2, 2.4, 3.1, 3.3, 3.4, 4.4, 4.5, 6.5, 7.2, 7.4_

- [x] 2. Implement SolverSolutionCallback and background thread execution
  - [x] 2.1 Add `SolutionEvent` dataclass and `SolverSolutionCallback` class to `backend/app/services/optimiser.py`
    - Define `SolutionEvent` dataclass with `solutions_found`, `objective_value`, `wall_time_seconds`
    - Implement `SolverSolutionCallback` extending OR-Tools callback
    - Callback must push `SolutionEvent` to a `queue.Queue` on each improved solution
    - Track solution count and start time using `time.monotonic()`
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.2 Refactor `OptimisationEngine.run()` to execute solver in background thread
    - Extract the `model.routing.SolveWithParameters(model.search_parameters)` call into a private `_solve_blocking()` method
    - Add `run_solver_in_background()` async method that uses `loop.run_in_executor(None, ...)` to run solver in thread pool
    - Poll `queue.Queue` for `SolutionEvent` objects in async loop with `asyncio.sleep(1.0)` intervals
    - Drain remaining events from queue after solver future completes
    - Accept `ProgressService` parameter and call `start_solver_phase()`, `emit_solver_tick()`, `on_solution_found()`, `complete_solver_phase()`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 1.2, 2.3_

  - [ ]* 2.3 Write property test for percentage calculation invariant
    - **Property 1: Percentage Calculation Invariant**
    - Generate random `elapsed_seconds` (0-7200) and `time_limit_seconds` (1-3600)
    - Verify `percentage_complete = min(100, floor(elapsed / time_limit × 100))`
    - Verify final message always has `percentage_complete = 100` on completion
    - **Validates: Requirements 1.3, 1.4**

  - [ ]* 2.4 Write property test for solution event round-trip
    - **Property 2: Solution Event Round-Trip**
    - Generate random sequences of N solution events (0 ≤ N ≤ 50)
    - Verify emitted `solutions_found` equals N
    - Verify `current_best_score` matches the last solution's objective value
    - Each callback must increment count by exactly 1
    - **Validates: Requirements 2.1, 2.2**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add distance matrix progress wrapper
  - [x] 4.1 Create `fetch_matrix_with_progress()` helper in `backend/app/services/progress.py`
    - Wrap the existing `GoogleMapsClient.get_distance_matrix()` call
    - Use `asyncio.create_task()` for the matrix fetch
    - Emit heartbeat ticks every ≤2 seconds while waiting via `asyncio.sleep(2.0)` loop
    - Call `progress.complete_distance_matrix()` on success
    - Call `progress.fail_distance_matrix()` with error truncated to 500 chars on `MapsAPIError`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 4.2 Write property test for error description truncation
    - **Property 5: Error Description Truncation**
    - Generate random error strings of length 0 to 2000
    - Verify emitted error description is at most 500 characters
    - Verify emitted error is a prefix of the original error string
    - **Validates: Requirements 3.4**

  - [ ]* 4.3 Write property test for phase ordering
    - **Property 4: Phase Ordering**
    - Generate random optimisation message streams with both phases
    - Verify all "distance_matrix" messages precede all "solver" messages
    - Verify exactly one terminal distance_matrix message (status "complete" or "failed") appears before first solver message
    - **Validates: Requirements 3.5, 4.6**

- [x] 5. Integrate ProgressService into WebSocket handler
  - [x] 5.1 Modify `_run_optimisation()` in `backend/app/routes/websocket.py`
    - Import `ProgressService` and `fetch_matrix_with_progress`
    - Create `ProgressService` instance with the session and time_limit from the engine config
    - Replace direct `maps_client.get_distance_matrix()` call with `fetch_matrix_with_progress()`
    - Pass `ProgressService` to `engine.run()` for solver phase progress
    - Call `progress.stop()` in finally block to clean up ticker tasks
    - Preserve existing `on_step` and `on_progress` callbacks unchanged
    - _Requirements: 4.1, 5.1, 6.1, 6.2, 6.3, 6.4_

  - [ ]* 5.2 Write property test for message schema invariant
    - **Property 3: Message Schema Invariant**
    - Generate random valid progress states for both phases
    - Build solver_progress messages from those states
    - Verify all required fields present with correct types and ranges
    - Verify phase "solver" messages include `time_limit_seconds`, `percentage_complete`, `solutions_found`, `current_best_score`
    - Verify phase "distance_matrix" messages include `total_pairs`, `pairs_completed`, `status`
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

  - [ ]* 5.3 Write property test for backward-compatible stream
    - **Property 6: Backward-Compatible Stream**
    - Generate random optimisation runs producing message streams
    - Filter out all messages where `type == "solver_progress"`
    - Verify remaining sequence is identical in order and structure to pre-existing protocol
    - **Validates: Requirements 6.2**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Resilience and time-limit edge cases
  - [x] 7.1 Add resilience handling for failed progress emissions in `ProgressService`
    - Wrap all `session.send_json()` calls in try/except
    - Log warning on failure, do not propagate exception
    - Continue emitting subsequent messages after a failed emission
    - _Requirements: 6.5_

  - [x] 7.2 Add time limit clamping logic and warning field
    - Implement clamping in `__init__` for values outside [1, 3600]
    - Include `"warning": "time_limit clamped to minimum 1s"` or `"time_limit clamped to maximum 3600s"` in first solver message when clamped
    - Handle `time_limit = 0` by clamping to 1 (prevents division by zero)
    - _Requirements: 7.2, 7.4_

  - [ ]* 7.3 Write property test for resilience on progress failure
    - **Property 7: Resilience on Progress Failure**
    - Inject random emission failures at various points in the progress stream
    - Verify subsequent messages continue to emit without interruption
    - Verify existing message stream (step/progress) is unaffected
    - **Validates: Requirements 6.5**

  - [ ]* 7.4 Write property test for time limit consistency
    - **Property 8: Time Limit Consistency**
    - Generate random valid `time_limit_seconds` values in [1, 3600]
    - Verify first solver phase message reports exactly that value
    - **Validates: Requirements 7.2**

  - [ ]* 7.5 Write property test for time limit clamping
    - **Property 9: Time Limit Clamping**
    - Generate random out-of-range values (≤0, >3600)
    - Verify emitted `time_limit_seconds` is clamped to nearest bound
    - Verify warning field is present in the message
    - **Validates: Requirements 7.4**

- [x] 8. Integration tests and final wiring
  - [x] 8.1 Verify existing step messages are preserved in `backend/tests/test_websocket.py`
    - Add test case that runs full optimisation and verifies all 8 step messages and progress messages still arrive
    - Verify `solver_progress` messages coexist without disrupting existing messages
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 8.2 Write integration test for full optimisation with progress in `backend/tests/test_websocket.py`
    - Test end-to-end WebSocket flow verifying both step and solver_progress messages appear
    - Verify distance_matrix phase messages appear before solver phase messages
    - Verify solver_progress messages contain all required fields
    - _Requirements: 4.1, 4.6, 5.2_

  - [ ]* 8.3 Write integration test for client disconnect during solver phase
    - Simulate client disconnect during solver background execution
    - Verify no resource leaks (ticker tasks cancelled, thread completes)
    - Verify `progress.stop()` is called
    - _Requirements: 5.4_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with `asyncio`, `queue.Queue` for thread-safe communication, and Hypothesis for property-based testing
- All property-based tests should be placed in `backend/tests/test_progress_properties.py`
- The OR-Tools solver time limit is currently set to 10 seconds in `build_model()` via `search_parameters.time_limit.FromSeconds(10)`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "4.1"] },
    { "id": 3, "tasks": ["2.3", "2.4", "4.2", "4.3", "7.1", "7.2"] },
    { "id": 4, "tasks": ["5.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "7.3", "7.4", "7.5"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3"] }
  ]
}
```
