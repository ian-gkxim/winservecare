# Implementation Plan: AI Care Operations Optimiser

## Overview

This plan implements a full-stack prototype for domiciliary care route optimisation. The system uses a FastAPI + Python backend with Google OR-Tools for VRP solving, and a React + Tailwind CSS frontend with Google Maps for animated visualisation. Implementation is ordered: foundational infrastructure → data layer → optimisation engine → API endpoints → frontend components → integration and wiring.

## Tasks

- [x] 1. Project setup and infrastructure
  - [x] 1.1 Initialise project structure with monorepo layout
    - Create top-level directory structure: `backend/`, `frontend/`, `data/`, `scripts/`
    - Backend: `backend/app/`, `backend/app/models/`, `backend/app/routes/`, `backend/app/services/`, `backend/app/db/`, `backend/tests/`
    - Frontend: `frontend/src/`, `frontend/src/components/`, `frontend/src/pages/`, `frontend/src/hooks/`, `frontend/src/types/`, `frontend/src/services/`
    - Create `package.json` at root with combined start script launching both backend and frontend
    - Create `README.md` documenting Node.js and Python version requirements
    - _Requirements: 15.1, 15.2, 15.7_

  - [x] 1.2 Set up backend Python project with FastAPI and dependencies
    - Create `backend/requirements.txt` with pinned versions: fastapi, uvicorn, pydantic, ortools, googlemaps, aiosqlite, httpx, pytest, hypothesis, pytest-asyncio
    - Create `backend/app/__init__.py` and `backend/app/main.py` with FastAPI app instance, CORS config, and lifespan handler
    - Configure Uvicorn to serve on port 8000
    - _Requirements: 15.1, 15.2_

  - [x] 1.3 Set up frontend React project with Vite and Tailwind CSS
    - Initialise Vite + React + TypeScript project in `frontend/`
    - Install and configure Tailwind CSS
    - Install dependencies: react-router-dom, @googlemaps/js-api-loader, axios
    - Configure Vite proxy to forward `/api` and `/ws` to backend port 8000
    - _Requirements: 15.1, 15.3_

  - [x] 1.4 Create shared TypeScript type definitions
    - Create `frontend/src/types/index.ts` with all TypeScript interfaces from design: Carer, Patient, Visit, KPIMetrics, Route, RouteStop, AnimationStep, StepData, Recommendation, Scenario, Exception
    - _Requirements: 1.1, 3.5, 9.1, 10.1_

- [x] 2. Database layer and mock data
  - [x] 2.1 Implement SQLite database schema and initialisation
    - Create `backend/app/db/schema.sql` with all CREATE TABLE statements from design (carers, patients, visits, skills, constraints, scenarios, exceptions, config)
    - Create `backend/app/db/database.py` with async connection management and schema initialisation on first start
    - Implement "initialise only if tables don't exist" logic to preserve edits on subsequent starts
    - _Requirements: 7.4, 7.5, 15.3_

  - [x] 2.2 Create Pydantic data models for all entities
    - Create `backend/app/models/` with separate files: `carer.py`, `patient.py`, `visit.py`, `skill.py`, `constraint.py`, `scenario.py`, `exception.py`, `config.py`, `optimisation.py`
    - Implement all Pydantic models from design including validation constraints (Field ge/le, min_length, max_length)
    - _Requirements: 11.4, 12.5, 12.6_

  - [x] 2.3 Implement data access layer (CRUD operations)
    - Create `backend/app/db/repositories.py` with async functions: get_carers, update_carer, get_patients, update_patient, get_visits, cancel_visit, get_skills, create_skill, get_constraints, update_constraint, get_scenarios, create_scenario, get_scenario, compare_scenarios, get_exceptions, resolve_exception, get_config, update_config, get_kpis
    - Implement proper error handling for not-found and constraint violations
    - _Requirements: 11.1, 11.2, 11.3, 12.1, 12.7, 10.1, 13.1_

  - [x] 2.4 Create mock data seed script
    - Create `backend/app/db/seed.py` with 5 carers (UK locations, varied skills, 6-10 max hours), 10+ patients (UK addresses, priorities, continuity scores), 20 visits (15-90 min duration, time windows, required skills)
    - Ensure mock data exercises all 7 hard constraints (skill matching, medication, time windows, max hours, breaks, travel feasibility, no overlaps)
    - Include at least one scenario that demonstrates infeasibility
    - _Requirements: 7.1, 7.2, 7.3, 7.6_

  - [ ]* 2.5 Write property tests for data validation (Properties 16, 17)
    - **Property 16: Name Validation** — Test that scenario/skill names are accepted iff trimmed length is 1-100 and unique
    - **Property 17: Entity Edit Validation** — Test that carer updates reject invalid max_working_hours and empty names; patient updates reject invalid priority
    - **Validates: Requirements 10.1, 10.2, 11.4, 12.5, 12.6**

- [ ] 3. Optimisation engine core
  - [x] 3.1 Implement Google Maps client service
    - Create `backend/app/services/maps_client.py` with `GoogleMapsClient` class
    - Implement `get_distance_matrix()` that calls Google Distance Matrix API with driving mode and 30-second timeout
    - Handle API errors, partial failures (invalid pairs), and timeout scenarios
    - Return `TravelTimeMatrix` Pydantic model with durations and distances
    - _Requirements: 8.1, 8.4, 8.5_

  - [x] 3.2 Implement OR-Tools VRP model builder
    - Create `backend/app/services/optimiser.py` with `OptimisationEngine` class
    - Implement `build_model()` that constructs OR-Tools RoutingModel with:
      - Vehicle (carer) definitions with capacity constraints
      - Time window constraints per visit node
      - Skill-matching dimension (hard constraint)
      - Maximum working hours dimension per vehicle
      - Break scheduling for continuous work limits
      - No-overlap constraint (disjunction)
    - Configure search parameters with time limit of 10 seconds
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 3.3 Implement route extraction and solution processing
    - Implement `extract_routes()` to convert OR-Tools Assignment to list of Route models with ordered stops, travel times, mileage, and cost
    - Implement infeasibility detection for unassigned visits with reasons
    - Calculate objective function as weighted sum per design spec
    - _Requirements: 3.4, 3.5, 3.6, 4.8_

  - [x] 3.4 Implement optimisation orchestrator with step callbacks
    - Implement `run()` method that orchestrates: fetch data → get travel matrix → build model → solve → extract routes
    - Emit 8 animation steps via `on_step` callback matching the design sequence
    - Emit progress updates via `on_progress` callback with step number, name, and current score
    - Handle solver timeout (return best solution found or abort)
    - Generate recommendations and warnings from solution analysis
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 16.1, 16.2_

  - [x] 3.5 Implement recommendation and warning generation
    - Create `backend/app/services/recommendations.py`
    - Generate "approaching hours limit" warning when carer hours >= 80% of max
    - Generate "limited flexibility" warning when visit starts within 15 min of window edge
    - Generate improvement recommendations ordered by impact (max 10)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 3.6 Write property tests for constraint enforcement (Properties 4-8)
    - **Property 4: Skill Matching** — Every assignment has carer skills ⊇ visit required skills
    - **Property 5: Time Windows** — Every visit starts within window and completes before window end
    - **Property 6: Max Working Hours** — No carer exceeds their max_working_hours
    - **Property 7: Mandatory Breaks** — No continuous stretch exceeds max_continuous_hours without break
    - **Property 8: No Overlapping Visits** — No carer has overlapping visit intervals
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7**

  - [ ]* 3.7 Write property tests for optimiser output (Properties 2, 3, 9, 10)
    - **Property 2: Objective Function Calculation** — Weighted sum matches configured coefficients
    - **Property 3: Solution Quality** — Output score <= baseline score when feasible
    - **Property 9: Route Output Completeness** — Routes contain all required fields in chronological order
    - **Property 10: Infeasibility Detection** — Unassignable visits are identified with reasons
    - **Validates: Requirements 3.1, 3.4, 3.5, 3.6**

  - [ ]* 3.8 Write property tests for recommendations (Properties 13, 14, 15)
    - **Property 13: Recommendations Ordering** — Sorted by impact descending, max 10 items
    - **Property 14: Carer Hours Warning** — Warning iff hours >= 80% of max
    - **Property 15: Visit Window Edge Warning** — Warning iff start within 15 min of window edge
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [ ]* 3.9 Write property test for disabled constraint exclusion (Property 19)
    - **Property 19: Disabled Constraint Exclusion** — Disabled constraints are not enforced while others remain active
    - **Validates: Requirements 12.3, 12.4**

- [x] 4. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Backend REST API endpoints
  - [x] 5.1 Implement carer and patient CRUD endpoints
    - Create `backend/app/routes/carers.py` with GET /api/carers, PUT /api/carers/{id}
    - Create `backend/app/routes/patients.py` with GET /api/patients, PUT /api/patients/{id}
    - Implement input validation returning field-level errors for invalid data
    - Return confirmation on successful edit
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 5.2 Implement visit, skill, and constraint endpoints
    - Create `backend/app/routes/visits.py` with GET /api/visits, DELETE /api/visits/{id}
    - Create `backend/app/routes/skills.py` with GET /api/skills, POST /api/skills
    - Create `backend/app/routes/constraints.py` with GET /api/constraints, PUT /api/constraints/{id}
    - Visit deletion triggers re-optimisation via background task
    - Skill creation validates unique name 1-100 chars
    - _Requirements: 6.1, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [x] 5.3 Implement scenario and exception endpoints
    - Create `backend/app/routes/scenarios.py` with GET /api/scenarios, POST /api/scenarios, GET /api/scenarios/{id}, GET /api/scenarios/compare
    - Create `backend/app/routes/exceptions.py` with GET /api/exceptions, PUT /api/exceptions/{id}/resolve
    - Scenario creation validates unique name; comparison requires 2+ scenarios
    - Exception resolution is idempotent (already-resolved returns message)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 5.4 Implement KPI, reports, and config endpoints
    - Create `backend/app/routes/kpis.py` with GET /api/kpis
    - Create `backend/app/routes/reports.py` with GET /api/reports/latest
    - Create `backend/app/routes/config.py` with GET /api/config, PUT /api/config
    - KPIs return formatted metrics; reports return before/after with differences; config validates non-empty API key
    - _Requirements: 1.1, 1.4, 14.1, 14.4, 15.5, 15.6_

  - [x] 5.5 Implement WebSocket optimisation endpoint
    - Create `backend/app/routes/websocket.py` with /ws/optimise endpoint
    - Handle client messages: start, pause, resume
    - Emit server messages: step, progress, complete, error
    - Wire to OptimisationEngine with step/progress callbacks that send WebSocket frames
    - Handle disconnects gracefully with auto-reconnect support
    - _Requirements: 2.1, 2.9, 2.10, 2.11, 2.12, 3.7, 16.1, 16.2, 16.3, 16.4_

  - [ ]* 5.6 Write property tests for savings and diff calculations (Properties 11, 12)
    - **Property 11: Savings Calculation** — savings = current - proposed; percentage = ((current - proposed) / current) * 100 when current > 0
    - **Property 12: Assignment Diff Detection** — Diff returns exactly visits where carer_id differs between two sets
    - **Validates: Requirements 5.2, 5.3, 5.4, 10.4**

  - [ ]* 5.7 Write property tests for skill usage count and exception ordering (Properties 18, 20)
    - **Property 18: Skill Usage Count** — Count equals carers with skill + visits requiring skill
    - **Property 20: Exception Ordering** — Exceptions displayed in descending timestamp order
    - **Validates: Requirements 12.1, 13.2**

- [x] 6. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Frontend shared components and layout
  - [x] 7.1 Implement application shell and navigation
    - Create `frontend/src/App.tsx` with React Router setup and all routes from design
    - Create `frontend/src/components/NavSidebar.tsx` with navigation links to all pages
    - Create `frontend/src/components/ErrorBanner.tsx`, `ConfirmationToast.tsx`, `LoadingPlaceholder.tsx`
    - Set up global error boundary component
    - _Requirements: 15.3_

  - [x] 7.2 Implement reusable DataTable and EditModal components
    - Create `frontend/src/components/DataTable.tsx` with sortable columns, row selection
    - Create `frontend/src/components/EditModal.tsx` with dynamic form fields, validation, submit/cancel
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 7.3 Create API service layer and WebSocket hook
    - Create `frontend/src/services/api.ts` with Axios instance and all REST endpoint functions
    - Create `frontend/src/hooks/useWebSocket.ts` with connect, disconnect, message handling, auto-reconnect (3 attempts, exponential backoff)
    - Create `frontend/src/hooks/useOptimisation.ts` combining WebSocket + state management for optimisation flow
    - _Requirements: 2.1, 8.4, 16.1_

- [ ] 8. Frontend Dashboard page
  - [x] 8.1 Implement KPI Ribbon component
    - Create `frontend/src/components/KPIRibbon.tsx` displaying 6 metrics with labels
    - Integer metrics (Total Visits, Carers Available) as whole numbers
    - Decimal metrics (Travel Hours, Mileage, Overtime) with 1 decimal place
    - Continuity Score as integer percentage
    - Show placeholder indicators when data unavailable
    - Update within 2 seconds of optimisation completion
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 8.2 Write property test for KPI formatting (Property 1)
    - **Property 1: KPI Formatting Invariant** — Integer metrics display as whole numbers, decimal metrics with exactly 1 decimal place, continuity as integer percentage
    - Use Vitest + fast-check
    - **Validates: Requirements 1.3**

  - [x] 8.3 Implement Animated Map component
    - Create `frontend/src/components/AnimatedMap.tsx` with Google Maps JS API integration
    - Implement 8-step animation rendering: locations → matrix → assignments → pruning → evaluation → improvement → solution → route animation
    - Each step uses distinct visual styles (marker types, line colours, animations)
    - Auto-advance between steps with 1-3 second delay
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.11, 8.2, 8.3_

  - [x] 8.4 Implement Map Controls and Progress Panel
    - Create `frontend/src/components/MapControls.tsx` with pause/resume, step indicator (1-8), step name
    - Create `frontend/src/components/ProgressPanel.tsx` showing current step, objective score updating in real-time
    - Create `frontend/src/components/CompletionNotification.tsx` with final score, dismissible
    - Handle error states: display failure reason with last known score
    - Retain map state when paused
    - _Requirements: 2.9, 2.10, 2.12, 16.1, 16.2, 16.3, 16.4_

  - [x] 8.5 Implement Schedule Comparison component
    - Create `frontend/src/components/ScheduleComparison.tsx` with side-by-side current vs proposed
    - Show each carer's visits in chronological order
    - Display savings: travel hours, mileage, overtime as absolute and percentage
    - Highlight visits with changed carer assignment
    - Show total cost difference
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 8.6 Implement Recommendations Panel
    - Create `frontend/src/components/RecommendationsPanel.tsx`
    - Display up to 10 recommendations ordered by impact
    - Each item shows title and description (max 200 chars)
    - Visually distinguish warnings from recommendations (colour/icon)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 8.7 Assemble Dashboard page
    - Create `frontend/src/pages/DashboardPage.tsx` composing KPIRibbon, AnimatedMap, MapControls, ScheduleComparison, RecommendationsPanel, ProgressPanel
    - Wire useOptimisation hook for state management
    - Add "Run Optimisation" button triggering WebSocket flow
    - _Requirements: 1.1, 2.1, 5.1, 9.1, 16.1_

- [x] 9. Frontend CRUD and management pages
  - [x] 9.1 Implement Carers and Patients pages
    - Create `frontend/src/pages/CarersPage.tsx` with DataTable (name, home location, skills, max hours, break rules) and edit modal
    - Create `frontend/src/pages/PatientsPage.tsx` with DataTable (address, preferences, priority, continuity score read-only) and edit modal
    - Validate edits client-side before submission; display confirmation on success
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [x] 9.2 Implement Skills and Constraints pages
    - Create `frontend/src/pages/SkillsPage.tsx` with skill list (name, usage count), add new skill form
    - Create `frontend/src/pages/ConstraintsPage.tsx` with constraint list (name, description, enabled toggle)
    - Validate unique skill name 1-100 chars; show error for duplicates/empty
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [x] 9.3 Implement Exceptions page
    - Create `frontend/src/pages/ExceptionsPage.tsx` with exceptions list ordered by timestamp descending
    - Display timestamp, description, affected entity, resolution status
    - Acknowledge button marks resolved without page reload
    - Handle already-resolved case; show empty state message
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 9.4 Implement Scenarios page
    - Create `frontend/src/pages/ScenariosPage.tsx` with saved scenarios list and compare view
    - Save scenario prompts for name (1-100 chars), validates uniqueness
    - Side-by-side comparison of two scenarios: travel, mileage, overtime, continuity with diffs
    - Highlight visits with different carer assignments
    - Disable compare when < 2 scenarios exist
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 9.5 Implement Reports and Configuration pages
    - Create `frontend/src/pages/ReportsPage.tsx` with latest optimisation summary (before/after, absolute and percentage differences), print-friendly CSS
    - Create `frontend/src/pages/ConfigPage.tsx` with Google Maps API key input, validation for empty, persist across restarts
    - Reports show empty state if no optimisation completed
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 15.5, 15.6_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Integration, cancellation flow, and final wiring
  - [x] 11.1 Implement visit cancellation and re-optimisation flow
    - Wire DELETE /api/visits/{id} to trigger automatic re-optimisation
    - Frontend: add cancel button on visit list/schedule, confirm action
    - After re-optimisation: update KPIs, replay animation, show updated schedule comparison
    - Ensure re-optimisation completes within 10 seconds
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 11.2 Wire exception logging to optimisation engine
    - On infeasible assignments, log exception to DB with timestamp, description, constraint names, affected entity
    - Exceptions appear on Exceptions page in real-time
    - _Requirements: 13.1_

  - [x] 11.3 Create startup scripts and README
    - Create root `package.json` with `npm run install:all` (installs backend + frontend deps) and `npm run start` (launches uvicorn + vite concurrently)
    - Write `README.md` with prerequisites (Node.js 18+, Python 3.11+), install command, start command, configuration instructions
    - Ensure startup completes within 30 seconds and frontend loads without error
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.7_

  - [ ]* 11.4 Write integration tests for end-to-end flows
    - Test full optimisation WebSocket flow with mocked Google Maps
    - Test visit cancellation → re-optimisation cycle
    - Test scenario save → compare flow
    - Test carer edit → optimisation uses updated data
    - _Requirements: 3.1, 6.1, 10.1, 11.5_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- Backend uses Python (FastAPI, OR-Tools, Hypothesis for property tests, pytest)
- Frontend uses TypeScript (React, Vite, Vitest + fast-check for property tests)
- Google Maps API key must be configured before optimisation can run

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.4"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4"] },
    { "id": 4, "tasks": ["2.5", "3.1", "3.2"] },
    { "id": 5, "tasks": ["3.3", "3.4", "3.5"] },
    { "id": 6, "tasks": ["3.6", "3.7", "3.8", "3.9"] },
    { "id": 7, "tasks": ["5.1", "5.2", "5.3", "5.4"] },
    { "id": 8, "tasks": ["5.5", "5.6", "5.7"] },
    { "id": 9, "tasks": ["7.1", "7.2", "7.3"] },
    { "id": 10, "tasks": ["8.1", "8.3", "8.4", "8.5", "8.6"] },
    { "id": 11, "tasks": ["8.2", "8.7"] },
    { "id": 12, "tasks": ["9.1", "9.2", "9.3", "9.4", "9.5"] },
    { "id": 13, "tasks": ["11.1", "11.2", "11.3"] },
    { "id": 14, "tasks": ["11.4"] }
  ]
}
```
