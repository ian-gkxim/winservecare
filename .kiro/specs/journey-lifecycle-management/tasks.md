# Implementation Plan: Journey Lifecycle Management

## Overview

This plan implements the Journey Lifecycle Management feature by building up from the database schema layer through the repository, service, and API route layers, with property-based tests validating correctness at each stage. The implementation follows the existing project patterns: async SQLite via aiosqlite, Pydantic models, repository functions with `get_db()`, and FastAPI routers.

## Tasks

- [x] 1. Database schema and Pydantic models
  - [x] 1.1 Add journey tables to the database schema
    - Append the `journey_plans`, `journeys`, and `actual_journeys` table definitions (with indexes) to `backend/app/db/schema.sql`
    - Include all CHECK constraints, foreign keys, and UNIQUE constraints as specified in the design
    - _Requirements: 1.1, 1.5, 4.1, 6.1_

  - [x] 1.2 Create journey Pydantic models
    - Create `backend/app/models/journey.py` with all enums (`JourneyStatus`, `PlanCreationReason`, `MatchStatus`) and Pydantic models (`JourneyCreate`, `JourneyUpdate`, `JourneyModel`, `JourneyPlanModel`, `ActualJourneyCreate`, `ActualJourneyModel`, `VarianceModel`, `ComparisonEntry`, `ComparisonResult`, `DaySummary`, `JourneyFilters`, `PaginatedResult`, `DeleteConfirmation`, `ErrorResponse`)
    - _Requirements: 1.1, 1.5, 2.2, 4.1, 5.2, 5.3, 5.4, 8.5_

- [x] 2. Repository layer
  - [x] 2.1 Implement journey plan repository functions
    - Create `backend/app/db/journey_repository.py` with async CRUD functions: `create_journey_plan`, `get_journey_plan`, `list_journey_plans`, `get_latest_plan_version`, `archive_journey_plan`, `get_archived_plans`
    - Follow the existing pattern in `backend/app/db/repositories.py` using `get_db()` context manager and `aiosqlite.Row`
    - _Requirements: 1.1, 1.6, 3.1, 3.3, 6.1, 6.3_

  - [x] 2.2 Implement journey repository functions
    - Add functions to `backend/app/db/journey_repository.py`: `create_journey`, `get_journey`, `update_journey_status`, `get_journeys_by_plan`, `query_journeys` (with filters and pagination), `get_journeys_by_carer`
    - _Requirements: 1.5, 2.2, 2.3, 7.1, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 2.3 Implement actual journey repository functions
    - Add functions to `backend/app/db/journey_repository.py`: `create_actual_journey`, `get_actual_journeys_by_day`, `get_actual_journey_by_journey_id`, `find_matching_planned_journey`
    - _Requirements: 4.1, 4.6, 5.1_

  - [x]* 2.4 Write property tests for plan creation round-trip
    - **Property 1: Journey plan creation round-trip**
    - **Validates: Requirements 1.1, 1.5**

  - [x]* 2.5 Write property tests for plan versioning
    - **Property 4: Plan versioning increments sequentially**
    - **Validates: Requirements 1.6, 6.1**

- [x] 3. Checkpoint - Ensure repository layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Service layer — plan creation and modification
  - [x] 4.1 Implement plan creation logic in journey service
    - Create `backend/app/services/journey_service.py` with the `JourneyService` class
    - Implement `create_plan` (validates operating day, persists plan) and `create_plan_from_optimiser` (converts RouteModel list to journeys)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [x] 4.2 Implement journey modification logic
    - Implement `modify_journey` in `JourneyService`: validates state transitions, enforces field editability rules by status, creates new plan version, marks original journey as amended
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 4.3 Implement plan deletion logic
    - Implement `delete_plan` in `JourneyService`: validates no active journeys, validates not past date, validates not today's only plan, performs soft-delete with archive timestamp
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x]* 4.4 Write property tests for operating day validation
    - **Property 3: Operating day date validation**
    - **Validates: Requirements 1.3, 1.4**

  - [x]* 4.5 Write property tests for modification state rules
    - **Property 5: Modifications always create new versions preserving prior state**
    - **Property 6: Planned journey field editability**
    - **Property 7: In-progress journey restricts editable fields**
    - **Property 8: Terminal states reject modification**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**

  - [x]* 4.6 Write property tests for deletion guard
    - **Property 9: Deletion guard — no active journeys**
    - **Property 10: Soft-delete archives with timestamp**
    - **Validates: Requirements 3.1, 3.2, 3.3**

- [x] 5. Service layer — actual journey reception and state transitions
  - [x] 5.1 Implement actual journey reception
    - Implement `receive_actual` in `JourneyService`: validates input, matches to planned journey using carer + operating day + 60-min departure window, creates actual journey record, triggers state transition
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_

  - [x] 5.2 Implement journey cancellation logic
    - Implement `cancel_journey` in `JourneyService`: validates current status, sets status to cancelled with timestamp, creates new plan version, handles visit unassignment for in-progress journeys
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x]* 5.3 Write property tests for actual journey data
    - **Property 11: Actual journey data persistence round-trip**
    - **Property 12: State transition — departure triggers in_progress**
    - **Property 13: State transition — arrival triggers completed**
    - **Property 14: Actual journey validation rejects invalid data**
    - **Property 15: Actual journey matching selects closest planned departure**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.5, 4.6**

  - [x]* 5.4 Write property tests for cancellation
    - **Property 21: Cancellation of planned journey**
    - **Property 22: Cancellation of in-progress journey unassigns visits**
    - **Property 23: Terminal states reject cancellation**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

- [x] 6. Checkpoint - Ensure service layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Service layer — comparison, history, and query
  - [x] 7.1 Implement plan vs actual comparison
    - Implement `get_comparison` in `JourneyService`: pairs planned journeys with actuals, calculates variance (departure/arrival in minutes, distance in miles), groups by carer, orders by departure time, handles unmatched entries
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 7.2 Implement historical plan retrieval
    - Implement `get_history` and `get_date_range_summary` in `JourneyService`: returns all versions in chronological order, validates date range (max 90 days), computes summary stats per day
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 7.3 Implement journey query and filtering
    - Implement `query_journeys` in `JourneyService`: applies filters (operating_day, carer_id, status), validates filter values, uses latest plan version per day, supports pagination, orders by departure descending for carer queries
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x]* 7.4 Write property tests for comparison and variance
    - **Property 16: Variance calculation correctness**
    - **Property 17: Comparison includes unmatched entries with null variances**
    - **Property 18: Comparison results grouped by carer and ordered by departure**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

  - [x]* 7.5 Write property tests for history and date range
    - **Property 19: History returns versions in chronological order**
    - **Property 20: Date range validation for historical queries**
    - **Validates: Requirements 6.3, 6.6**

  - [x]* 7.6 Write property tests for query and filtering
    - **Property 24: Query filter intersection semantics**
    - **Property 25: Carer query ordering**
    - **Property 26: Pagination correctness**
    - **Property 27: Invalid filter rejection**
    - **Validates: Requirements 8.2, 8.3, 8.4, 8.5, 8.6**

- [x] 8. Checkpoint - Ensure comparison, history, and query tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. API routes layer
  - [x] 9.1 Implement journey plan CRUD routes
    - Create `backend/app/routes/journeys.py` with FastAPI router
    - Implement: `POST /api/journey-plans`, `GET /api/journey-plans`, `GET /api/journey-plans/{plan_id}`, `DELETE /api/journey-plans/{plan_id}`
    - Wire to `JourneyService` methods with proper error handling (422, 404, 409)
    - _Requirements: 1.1, 1.3, 1.4, 3.1, 3.2, 3.4, 3.5, 3.6_

  - [x] 9.2 Implement journey modification and cancellation routes
    - Add routes: `PUT /api/journey-plans/{plan_id}/journeys/{journey_id}`, `POST /api/journeys/{journey_id}/cancel`
    - Handle HTTP 409 for terminal state conflicts, 404 for not found, 422 for validation errors
    - _Requirements: 2.1, 2.4, 2.5, 7.1, 7.3, 7.4, 7.5_

  - [x] 9.3 Implement actual journey and comparison routes
    - Add routes: `POST /api/actual-journeys`, `GET /api/journey-comparison/{operating_day}`, `GET /api/journey-history/{operating_day}`, `GET /api/journey-history`, `GET /api/journeys`
    - Support query parameters for plan_version, date range (start/end), and pagination (page/page_size)
    - _Requirements: 4.1, 4.5, 5.1, 5.6, 5.7, 6.3, 6.5, 6.6, 8.1, 8.5_

  - [x] 9.4 Register journey router in the application
    - Import and include the journeys router in `backend/app/main.py`
    - _Requirements: 1.1_

  - [x]* 9.5 Write property test for optimiser route conversion
    - **Property 2: Optimiser route conversion produces ordered planned journeys**
    - **Validates: Requirements 1.2**

- [x] 10. Checkpoint - Ensure all route tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Integration and final wiring
  - [x] 11.1 Write integration tests for end-to-end flows
    - Create `backend/tests/test_routes_journeys.py` with tests covering: create plan → modify → receive actuals → compare, deletion flow, cancellation flow, query/filter flow, pagination
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 7.1, 8.1_

  - [x] 11.2 Write unit tests for service layer edge cases
    - Create `backend/tests/test_journey_service.py` with tests for: 4-hour overdue timeout (Req 4.7), unmatched actual creates exception entry (Req 4.4), empty comparison message (Req 5.6), specific plan version comparison (Req 5.7), today's only plan deletion rejected (Req 3.4), empty query results (Req 8.7)
    - _Requirements: 3.4, 4.4, 4.7, 5.6, 5.7, 8.7_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (27 properties total)
- Unit tests validate specific examples and edge cases
- The implementation uses Python with the existing tech stack: FastAPI, aiosqlite, Pydantic, pytest, Hypothesis
- All new files follow the established project patterns (async functions, `get_db()` context manager, `aiosqlite.Row`)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 2, "tasks": ["2.4", "2.5"] },
    { "id": 3, "tasks": ["4.1", "4.2", "4.3"] },
    { "id": 4, "tasks": ["4.4", "4.5", "4.6", "5.1", "5.2"] },
    { "id": 5, "tasks": ["5.3", "5.4"] },
    { "id": 6, "tasks": ["7.1", "7.2", "7.3"] },
    { "id": 7, "tasks": ["7.4", "7.5", "7.6"] },
    { "id": 8, "tasks": ["9.1", "9.2", "9.3"] },
    { "id": 9, "tasks": ["9.4", "9.5"] },
    { "id": 10, "tasks": ["11.1", "11.2"] }
  ]
}
```
