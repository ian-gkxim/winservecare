# Implementation Plan: Care Contracts & Visit Generation

## Overview

This plan implements contract-based visit generation by building up from the database schema through the data access layer, visit generation engine, API routes, and frontend components. The implementation follows established project patterns: async SQLite via aiosqlite, Pydantic models, repository functions with `get_db()`, FastAPI routers registered in `main.py`, and React + Tailwind pages with NavSidebar navigation.

## Tasks

- [x] 1. Database schema and Pydantic models
  - [x] 1.1 Add care_contracts and visit_slots tables to the database schema
    - Append `care_contracts` and `visit_slots` CREATE TABLE statements to `backend/app/db/schema.sql`
    - Add ALTER TABLE statements for `visits` table: `target_date TEXT` and `contract_id INTEGER REFERENCES care_contracts(id)` columns
    - Widen the existing `duration_minutes` CHECK constraint on `visits` from `<= 90` to `<= 120`
    - Include all CHECK constraints, UNIQUE constraints, foreign keys, and ON DELETE CASCADE as specified in the design
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [x] 1.2 Create care contract Pydantic models
    - Create `backend/app/models/contract.py` with enums (`VisitFrequency`, `DayOfWeek`) and Pydantic models (`VisitSlotModel`, `VisitSlotCreate`, `CareContractModel`, `CareContractCreate`, `GenerateVisitsRequest`, `GenerateVisitsResponse`)
    - Update `backend/app/models/visit.py` to add `target_date: Optional[str] = None` and `contract_id: Optional[int] = None` fields to `VisitModel`, and widen `duration_minutes` to `Field(ge=15, le=120)`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 6.5_

  - [x] 1.3 Create frontend TypeScript types
    - Create `frontend/src/types/contracts.ts` with TypeScript interfaces: `VisitFrequency`, `DayOfWeek`, `VisitSlot`, `CareContract`, `CareContractCreate`, `GenerateVisitsResponse`
    - Update the existing Visit type to include `targetDate` and `contractId` fields
    - _Requirements: 1.1, 1.4, 4.2_

- [x] 2. Repository layer — contracts and visits
  - [x] 2.1 Implement contract repository functions
    - Create `backend/app/db/contract_repository.py` with async CRUD functions: `get_contract_by_patient`, `create_or_update_contract`, `delete_contract`, `get_all_contracts`
    - Follow the existing pattern in `backend/app/db/repositories.py` using `get_db()` context manager and `aiosqlite.Row`
    - Handle JSON serialisation for `days_of_week`, `excluded_dates`, and `required_skills` fields
    - Insert/update `visit_slots` within the same transaction as the parent contract
    - _Requirements: 5.8, 5.10_

  - [x] 2.2 Extend visit repository functions
    - Add functions to `backend/app/db/repositories.py` or a new `backend/app/db/visit_repository.py`: `get_visits_by_date(target_date)`, `insert_generated_visits(visits)`, `delete_visits_by_date(target_date)`, `cancel_visit_by_id(visit_id)` (returns updated model)
    - The `get_visits_by_date` function should join with patients table to include patient name
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

  - [ ]* 2.3 Write property test for contract persistence round-trip
    - **Property 3: Contract Persistence Round-Trip**
    - **Validates: Requirements 5.8**

- [x] 3. Visit generation engine
  - [x] 3.1 Implement visit generation service
    - Create `backend/app/services/visit_generator.py` with the `VisitGenerator` class
    - Implement `check_frequency(frequency, start_date, target_date, days_of_week)` as a pure function
    - Implement `is_contract_eligible(contract, target_date)` combining active-date, end-date, excluded-date, and frequency checks
    - Implement `generate_visits(target_date)` that fetches contracts, evaluates eligibility, deletes previous visits for date, inserts new visits within a transaction, and returns `GenerateVisitsResponse`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [ ]* 3.2 Write property test for frequency rule correctness
    - **Property 4: Frequency Rule Correctness**
    - **Validates: Requirements 2.3, 2.4, 2.5, 2.6, 2.7**

  - [ ]* 3.3 Write property test for eligibility determination
    - **Property 5: Eligibility Determination**
    - **Validates: Requirements 2.2**

  - [ ]* 3.4 Write property test for visit generation output
    - **Property 6: Visit Generation Output Correctness**
    - **Validates: Requirements 2.1, 2.8, 6.5**

  - [ ]* 3.5 Write property test for generation replaces previous visits
    - **Property 9: Generation Replaces Previous Visits**
    - **Validates: Requirements 4.4, 4.5**

- [x] 4. Checkpoint - Ensure backend model and service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. API routes — contracts and visit generation
  - [x] 5.1 Implement contracts API routes
    - Create `backend/app/routes/contracts.py` with FastAPI router (prefix `/api/patients`)
    - Implement: `GET /api/patients/{patient_id}/contract`, `PUT /api/patients/{patient_id}/contract`, `DELETE /api/patients/{patient_id}/contract`
    - Add validation: slot count must equal visits_per_day, earliest_start < latest_start, end_date >= start_date, referenced skills must exist
    - Return proper HTTP status codes (200, 204, 404, 422)
    - _Requirements: 1.8, 5.8, 5.9_

  - [x] 5.2 Extend visits API routes
    - Extend `backend/app/routes/visits.py` with new endpoints:
    - `GET /api/visits?target_date=YYYY-MM-DD` — list visits for a date
    - `POST /api/visits/generate` — generate visits for target date (validates not past date)
    - `POST /api/visits/regenerate` — reset cancelled + regenerate for target date
    - `PATCH /api/visits/{visit_id}/cancel` — cancel a single visit (returns updated model)
    - _Requirements: 3.2, 4.3, 4.4, 4.5_

  - [x] 5.3 Register contracts router in main.py
    - Import and include the contracts router in `backend/app/main.py`
    - _Requirements: 5.1_

  - [ ]* 5.4 Write property test for contract validation
    - **Property 1: Contract Validation Invariant**
    - **Validates: Requirements 1.1, 1.2, 1.6, 1.8, 5.9**

  - [ ]* 5.5 Write property test for visit slot validation
    - **Property 2: Visit Slot Validation**
    - **Validates: Requirements 1.4, 5.9**

  - [ ]* 5.6 Write property test for past date validation
    - **Property 8: Past Date Validation**
    - **Validates: Requirements 3.2**

  - [ ]* 5.7 Write property test for cancel state transition
    - **Property 10: Cancel State Transition**
    - **Validates: Requirements 4.3**

  - [ ]* 5.8 Write property test for visit count derivation
    - **Property 11: Visit Count Derivation**
    - **Validates: Requirements 4.7**

- [x] 6. Checkpoint - Ensure all backend API tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Mock data seeding
  - [x] 7.1 Seed care contracts for all 12 patients
    - Extend `backend/app/db/seed.py` to add contract seeding after the existing visits seeding
    - Create contracts for all 12 patients with varied frequencies: at least 2 daily, 2 weekdays_only, 3 specific_days (different day combos), 2 alternate_days, 2 weekly
    - Vary visits_per_day: at least 3 patients with 1, 4 with 2, 3 with 3, 2 with 4 visits/day
    - Visit slots spanning different times: ≥4 morning (before 09:00), ≥4 midday (11:00–14:00), ≥4 evening (after 16:00)
    - All contracts: start_date 2025-01-01, end_date null, excluded_dates with UK 2025 bank holidays
    - Only reference skills from the existing SKILLS list
    - Make seeding idempotent (check if `care_contracts` table has data before inserting)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [x] 8. Frontend — Visits page
  - [x] 8.1 Create VisitsPage component
    - Create `frontend/src/pages/VisitsPage.tsx` with:
    - Date picker defaulting to today (weekday) or next Monday (weekend)
    - Table displaying generated visits: patient name, visit label, time window, duration, required skills, status badge
    - "Generate Visits" and "Regenerate" buttons
    - Cancel button per visit row
    - Scheduled/cancelled count summary
    - Empty state when no visits exist for the selected date
    - _Requirements: 3.1, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 8.2 Add Visits route to App.tsx and NavSidebar
    - Add `/visits` route to `frontend/src/App.tsx` pointing to `VisitsPage`
    - Add "Visits" nav item (icon: 📅) to `NavSidebar.tsx` between "Patients" and "Skills"
    - _Requirements: 4.1_

  - [ ]* 8.3 Write property test for default date calculation
    - **Property 7: Default Date Calculation**
    - **Validates: Requirements 3.1**

- [x] 9. Frontend — Contract form in Patient edit
  - [x] 9.1 Create ContractForm component
    - Create `frontend/src/components/ContractForm.tsx` with:
    - Frequency selector dropdown (daily, weekdays_only, specific_days, alternate_days, weekly)
    - Day-of-week checkboxes (shown only when specific_days selected, requires ≥1 selection)
    - Visit slots section: add/remove slots (1–4), each with label, earliest_start, latest_start, duration_minutes, required_skills multi-select
    - Start date (required) and end date (optional) date fields
    - Excluded dates field with add/remove capability
    - Client-side validation mirroring backend rules
    - Pre-populate fields when editing an existing contract
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.9, 5.10_

  - [x] 9.2 Integrate ContractForm into PatientsPage
    - Add the ContractForm section below existing patient fields in `frontend/src/pages/PatientsPage.tsx`
    - Fetch existing contract on patient edit (GET /api/patients/{id}/contract)
    - Submit contract on save (PUT /api/patients/{id}/contract)
    - Display success/error toast notifications
    - _Requirements: 5.1, 5.8_

- [x] 10. Frontend — Dashboard integration
  - [x] 10.1 Add date picker to DashboardPage
    - Add a date picker to `frontend/src/pages/DashboardPage.tsx` above the "Run Optimisation" button
    - Default to today (weekday) or next Monday (weekend)
    - Validate selected date is not in the past
    - On date change, trigger visit generation for that date (POST /api/visits/generate) if visits don't already exist
    - Pass `targetDate` in the WebSocket optimisation start message
    - Display message when no scheduled visits exist for the date
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 6.1, 6.2, 6.3, 6.4_

- [x] 11. Checkpoint - Ensure frontend builds and all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Integration and final wiring
  - [x] 12.1 Write backend integration tests
    - Create `backend/tests/test_contracts_visits.py` with tests covering:
    - Full contract CRUD lifecycle (create → read → update → delete)
    - Visit generation end-to-end (create contracts → generate for date → verify visits in DB)
    - Regeneration resets cancelled visits
    - Cancellation flow (cancel visit → verify status → verify other visits unchanged)
    - Seed data verification (all 12 patients have contracts after init)
    - Idempotent seeding (restart does not overwrite modified contracts)
    - _Requirements: 1.1, 2.1, 4.3, 4.4, 4.5, 7.1, 7.7_

  - [x] 12.2 Wire optimiser to use generated visits for target date
    - Update `backend/app/routes/websocket.py` or optimiser integration to filter visits by `target_date` and `is_cancelled = False` when a target date is provided in the optimisation start message
    - Ensure backward compatibility: if no target_date provided, use all non-cancelled visits (existing behaviour)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (11 properties total)
- Unit tests validate specific examples and edge cases
- The backend uses Python with: FastAPI, aiosqlite, Pydantic, pytest, Hypothesis
- The frontend uses TypeScript with: React, Tailwind CSS, Vite
- All new backend files follow the established patterns (async functions, `get_db()` context manager, `aiosqlite.Row`)
- Frontend components follow the existing pattern of pages in `frontend/src/pages/` and shared components in `frontend/src/components/`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5"] },
    { "id": 4, "tasks": ["5.1", "5.2", "5.3"] },
    { "id": 5, "tasks": ["5.4", "5.5", "5.6", "5.7", "5.8"] },
    { "id": 6, "tasks": ["7.1"] },
    { "id": 7, "tasks": ["8.1", "8.2", "9.1"] },
    { "id": 8, "tasks": ["8.3", "9.2", "10.1"] },
    { "id": 9, "tasks": ["12.1", "12.2"] }
  ]
}
```
