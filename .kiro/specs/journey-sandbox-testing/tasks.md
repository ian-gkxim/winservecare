# Implementation Plan: Journey Sandbox Testing

## Overview

This plan implements the Journey Sandbox Testing feature incrementally, starting with the backend feedback infrastructure (schema, repository, service, routes), then building out the frontend layer (types, API service extensions, components, page assembly). Each step builds on the previous, ensuring no orphaned code.

## Tasks

- [x] 1. Backend: Database schema and feedback repository
  - [x] 1.1 Add journey_feedback table to schema and initialise
    - Add the `journey_feedback` table DDL (with indexes and unique constraint) to `backend/app/db/schema.sql`
    - Ensure `init_db()` picks up the new table on next startup
    - _Requirements: 10.3_

  - [x] 1.2 Create feedback_repository.py with CRUD operations
    - Create `backend/app/db/feedback_repository.py`
    - Implement `insert_feedback(data) -> dict` — INSERT and return the created row
    - Implement `get_feedback_by_journey(journey_id) -> dict | None` — SELECT by journey_id
    - Implement `feedback_exists(journey_id, carer_id) -> bool` — check UNIQUE constraint before insert
    - Follow existing repository patterns (async functions, `get_db()` from database module)
    - _Requirements: 10.3, 10.5_

  - [ ]* 1.3 Write unit tests for feedback_repository
    - Test insert and retrieval round-trip
    - Test duplicate detection returns True
    - Test get for non-existent journey returns None
    - Located in `backend/tests/test_feedback_repository.py`
    - _Requirements: 10.3, 10.5_

- [x] 2. Backend: Pydantic models and FeedbackService
  - [x] 2.1 Add feedback Pydantic models to journey.py
    - Add `FeedbackRating` enum, `JourneyFeedbackCreate` model, and `JourneyFeedbackModel` to `backend/app/models/journey.py`
    - `JourneyFeedbackCreate`: journey_id (int), carer_id (int), rating (FeedbackRating), comment (Optional[str], max_length=300), submitted_at (datetime)
    - `JourneyFeedbackModel`: id, journey_id, carer_id, rating, comment, submitted_at, created_at
    - _Requirements: 10.1, 10.3_

  - [x] 2.2 Create FeedbackService with validation logic
    - Create `backend/app/services/feedback_service.py`
    - Implement `submit_feedback(data: JourneyFeedbackCreate) -> JourneyFeedbackModel` with validations:
      - Journey must exist (422 if not)
      - Journey must have status `completed` (422 if not)
      - No duplicate feedback for same journey+carer (409 if exists)
    - Implement `get_feedback(journey_id: int) -> JourneyFeedbackModel | None`
    - Use `journey_repository` to check journey existence/status and `feedback_repository` for persistence
    - _Requirements: 10.1, 10.2, 10.4, 10.5_

  - [ ]* 2.3 Write unit tests for FeedbackService
    - Test submit with valid completed journey succeeds
    - Test submit with non-existent journey raises appropriate error
    - Test submit with non-completed journey raises appropriate error
    - Test duplicate submission raises conflict error
    - Located in `backend/tests/test_feedback_service.py`
    - _Requirements: 10.1, 10.2, 10.5_

- [x] 3. Backend: Feedback API routes
  - [x] 3.1 Add POST and GET feedback endpoints to journeys.py
    - Add `POST /api/journey-feedback` endpoint to `backend/app/routes/journeys.py`
      - Accept `JourneyFeedbackCreate` body, return `JourneyFeedbackModel` with 201 status
      - Handle ValueError → 422, duplicate → 409
    - Add `GET /api/journey-feedback/{journey_id}` endpoint
      - Return feedback or 404 if none exists
    - Follow existing route patterns (HTTPException for errors, typed responses)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 3.2 Write integration tests for feedback routes
    - Test full flow: create plan → complete journey → submit feedback → get feedback
    - Test 422 for non-existent journey
    - Test 422 for non-completed journey
    - Test 409 for duplicate feedback
    - Test 404 for GET with no feedback
    - Located in `backend/tests/test_routes_feedback.py`
    - _Requirements: 10.1, 10.2, 10.4, 10.5_

  - [ ]* 3.3 Write property-based tests for feedback API (Properties 7-10)
    - **Property 7: Feedback API Payload Validation**
    - **Property 8: Completed-Only Feedback Eligibility**
    - **Property 9: Feedback Persistence Round-Trip**
    - **Property 10: Duplicate Feedback Rejection**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**
    - Use Hypothesis with `@settings(max_examples=100)`
    - Create generators: `st_feedback_rating()`, `st_comment()`, `st_invalid_comment()`, `st_journey_status()`, `st_feedback_create()`, `st_utc_timestamp()`
    - Located in `backend/tests/test_feedback_properties.py`

- [x] 4. Checkpoint - Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Frontend: TypeScript types and API service extensions
  - [x] 5.1 Create sandbox TypeScript types
    - Create `frontend/src/types/sandbox.ts`
    - Define: `FeedbackRating`, `JourneyFeedbackCreate`, `JourneyFeedback`, `JourneyPlanCreate`, `JourneyCreateEntry`, `JourneyUpdate`, `ActualJourneyCreate`, `JourneyQueryParams`, `QuickSubmitConfig`
    - _Requirements: 2.1, 4.1, 5.1, 10.1_

  - [x] 5.2 Extend api.ts with journey sandbox and feedback functions
    - Add to `frontend/src/services/api.ts`:
      - `submitJourneyFeedback(data)` — POST /journey-feedback
      - `getJourneyFeedback(journeyId)` — GET /journey-feedback/{id}
      - `createJourneyPlan(data)` — POST /journey-plans
      - `listJourneyPlans(params)` — GET /journey-plans
      - `getJourneyPlan(planId)` — GET /journey-plans/{id}
      - `modifyJourney(planId, journeyId, update)` — PUT /journey-plans/{id}/journeys/{id}
      - `deleteJourneyPlan(planId)` — DELETE /journey-plans/{id}
      - `cancelJourney(journeyId)` — POST /journeys/{id}/cancel
      - `submitActualJourney(data)` — POST /actual-journeys
      - `getJourneyComparison(operatingDay, planVersion?)` — GET /journey-comparison/{day}
      - `getJourneyHistory(operatingDay)` — GET /journey-history/{day}
      - `getJourneyHistoryRange(start, end)` — GET /journey-history
      - `queryJourneys(params)` — GET /journeys
    - _Requirements: 2.1, 4.2, 5.3, 6.1, 8.1, 10.1_

  - [ ]* 5.3 Write unit tests for new API service functions
    - Mock axios and verify correct URL, method, and params for each function
    - Located in `frontend/src/services/api.test.ts` (extend existing)
    - _Requirements: 2.1, 10.1_

- [x] 6. Frontend: StatusTimeline component
  - [x] 6.1 Create StatusTimeline component
    - Create `frontend/src/components/sandbox/StatusTimeline.tsx`
    - Accept props: `journeyId`, `isOpen`, `onClose`
    - Fetch journey history and render chronological status transitions
    - Each transition shows: previous status, new status, timestamp, trigger source
    - Colour-coded badges: blue=planned, yellow=in_progress, green=completed, red=cancelled, orange=overdue, grey=amended
    - Render as a slide-over or modal panel
    - _Requirements: 7.1, 7.2, 7.4_

  - [ ]* 6.2 Write tests for StatusTimeline (including Property 6)
    - **Property 6: Status Timeline Completeness and Colour Mapping**
    - **Validates: Requirements 7.2, 7.4**
    - Use fast-check with `numRuns: 100` to generate random transition lists and verify all four fields rendered with correct colour mapping
    - Located in `frontend/src/components/sandbox/StatusTimeline.test.tsx`

- [x] 7. Frontend: PlanBuilder panel
  - [x] 7.1 Create PlanBuilder component
    - Create `frontend/src/components/sandbox/PlanBuilder.tsx`
    - Plan creation form: operating day (default tomorrow), creation reason (default initial_creation), journey rows
    - Each journey row: carer dropdown (fetched from /api/carers), origin lat/lng/label, destination lat/lng/label, departure, arrival, distance
    - "Add Journey" / "Remove" buttons, running journey count in header
    - Inline validation: operating day ≥ today, arrival > departure per row
    - Plan list: selectable list showing operating day, version, reason
    - Plan detail: tabular view of journeys with modify/cancel/delete actions
    - Confirmation dialog on delete, error alerts from API
    - Callback props: `onPlanCreated`, `onJourneySelected`
    - _Requirements: 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 7.2 Write tests for PlanBuilder (including Properties 1-2)
    - **Property 1: Operating Day Validation**
    - **Validates: Requirements 3.2**
    - **Property 2: Departure-Arrival Time Ordering**
    - **Validates: Requirements 3.3**
    - Use fast-check with `numRuns: 100` for date/time validation functions
    - Test form defaults (tomorrow's date, initial_creation)
    - Test add/remove journey rows
    - Located in `frontend/src/components/sandbox/PlanBuilder.test.tsx`

- [x] 8. Frontend: CarerSimulationPanel
  - [x] 8.1 Create CarerSimulationPanel component
    - Create `frontend/src/components/sandbox/CarerSimulationPanel.tsx`
    - Actual journey form: carer (default first available), operating day (default today), actual departure, actual arrival, actual distance, route coordinates (optional)
    - Display match status and matched journey ID on submission
    - Inline field-level error display for 4xx responses
    - "Quick Submit" button: generates random data (departure ±30min of now, arrival 15-60min later, distance 1-20 miles)
    - Feedback prompt after matched journey: thumbs_up/neutral/thumbs_down + optional comment (max 300 chars)
    - Soft prompt on thumbs_down without comment
    - Skip feedback dismisses prompt
    - Session feedback history list
    - Mobile-responsive: single-column at ≤480px, 44x44px tap targets
    - Callback props: `onActualSubmitted`, `onFeedbackSubmitted`
    - _Requirements: 1.2, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 8.2 Write tests for CarerSimulationPanel (including Properties 3-4)
    - **Property 3: Quick Submit Data Bounds**
    - **Validates: Requirements 4.5**
    - **Property 4: Comment Length Validation**
    - **Validates: Requirements 5.2, 10.1**
    - Use fast-check with `numRuns: 100`
    - Test feedback prompt appears on matched journey
    - Test skip feedback dismisses
    - Test thumbs-down soft prompt
    - Located in `frontend/src/components/sandbox/CarerSimulationPanel.test.tsx`

- [x] 9. Frontend: ComparisonView panel
  - [x] 9.1 Create ComparisonView component
    - Create `frontend/src/components/sandbox/ComparisonView.tsx`
    - Operating day selector + plan version dropdown
    - Display entries grouped by carer: planned departure/arrival, actual departure/arrival, departure variance (colour-coded: green=on-time/early, red=late), arrival variance, distance variance
    - "Unstarted" entries with dashed border/muted colours
    - "Unplanned" entries with highlighted border
    - Refresh button (re-fetches without page reload)
    - Empty state message when no data
    - Click on journey entry opens StatusTimeline
    - Callback prop: `onJourneySelected`
    - _Requirements: 1.2, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1_

  - [ ]* 9.2 Write tests for ComparisonView (including Property 5)
    - **Property 5: Variance Colour Coding**
    - **Validates: Requirements 6.2**
    - Use fast-check with `numRuns: 100` to verify colour mapping for random variance values
    - Test unstarted/unplanned visual indicators
    - Test refresh button triggers re-fetch
    - Test no data message
    - Located in `frontend/src/components/sandbox/ComparisonView.test.tsx`

- [x] 10. Checkpoint - Components complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Frontend: JourneySandboxPage assembly and routing
  - [x] 11.1 Create JourneySandboxPage with three-panel layout
    - Create `frontend/src/pages/JourneySandboxPage.tsx`
    - Compose PlanBuilder, CarerSimulationPanel, and ComparisonView in responsive layout
    - Desktop: three panels side-by-side or two-over-one grid
    - Mobile (≤768px): stack vertically in order PlanBuilder → CarerSimulation → ComparisonView
    - Sandbox banner: "Sandbox Mode – operations affect the live database"
    - "Reset Test Data" button with confirmation dialog (user types operating day to confirm)
    - Handle reset errors (display blocking journey IDs)
    - Wire shared state: plan creation refreshes comparison, actual submission refreshes comparison, journey selection opens timeline
    - StatusTimeline modal/slide-over controlled by page state
    - Plan version history browser: vertical timeline of versions for selected day, highlight current, mark archived
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3, 9.4_

  - [x] 11.2 Add route and navigation entry for JourneySandboxPage
    - Add route `/journey-sandbox` to `frontend/src/App.tsx` router
    - Add "Journey Sandbox" link to `frontend/src/components/NavSidebar.tsx`
    - _Requirements: 1.1_

  - [ ]* 11.3 Write page-level tests for JourneySandboxPage
    - Test three panels render
    - Test sandbox banner text
    - Test reset confirmation dialog
    - Test empty state instructions
    - Test responsive stacking at ≤768px
    - Located in `frontend/src/pages/JourneySandboxPage.test.tsx`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 9.2, 9.3_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (Properties 1-10)
- Unit tests validate specific examples and edge cases
- Backend uses Python (FastAPI, aiosqlite, Pydantic, Hypothesis for PBT)
- Frontend uses TypeScript (React, Vite, Vitest, React Testing Library, fast-check for PBT)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "5.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["1.3", "2.2", "5.2"] },
    { "id": 3, "tasks": ["2.3", "3.1", "5.3"] },
    { "id": 4, "tasks": ["3.2", "3.3", "6.1"] },
    { "id": 5, "tasks": ["6.2", "7.1"] },
    { "id": 6, "tasks": ["7.2", "8.1"] },
    { "id": 7, "tasks": ["8.2", "9.1"] },
    { "id": 8, "tasks": ["9.2", "11.1"] },
    { "id": 9, "tasks": ["11.2"] },
    { "id": 10, "tasks": ["11.3"] }
  ]
}
```
