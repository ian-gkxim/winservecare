# Implementation Plan: Carer Mobile App

## Overview

This implementation plan covers the full Carer Mobile App feature: backend database extensions, authentication and signal APIs, the Status Inference Engine, Question Engine, Notification Service, and the React Native/Expo mobile application with GPS tracking, offline buffer, proactive input, and push notifications. Tasks are ordered with backend infrastructure first, then the inference engine, then mobile app components, with property-based tests woven in close to their related implementation.

## Tasks

- [x] 1. Database schema extensions and backend infrastructure
  - [x] 1.1 Add new database tables for carer mobile app
    - Extend `backend/app/db/schema.sql` with new tables: `carer_auth`, `gps_signals`, `contextual_questions`, `proactive_inputs`, `visit_status`, `visit_status_transitions`, `push_notifications`
    - Add all indexes defined in the design document
    - Update `backend/app/db/database.py` `init_db()` to execute the new schema
    - _Requirements: 1.1, 3.2, 4.1, 5.4, 6.6, 7.5, 9.4_

  - [x] 1.2 Create Pydantic models for mobile app domain
    - Create `backend/app/models/mobile.py` with all models: `GPSSignal`, `GPSBatch`, `QuestionResponse`, `ProactiveInput`, `VisitStatus` enum, `VisitStatusResponse`, `LoginRequest`, `TokenResponse`, `DeviceTokenRequest`, `MobileVisitSummary`, `MobileVisitDetail`, `ContextualQuestionPayload`
    - Define `VALID_TRANSITIONS` map as specified in the design
    - _Requirements: 7.1, 7.2, 5.3, 6.6_

  - [x] 1.3 Create mobile app repository layer
    - Create `backend/app/db/mobile_repository.py` with CRUD operations for: `carer_auth`, `gps_signals`, `contextual_questions`, `proactive_inputs`, `visit_status`, `visit_status_transitions`, `push_notifications`
    - Implement methods for querying current visit status (`is_current = 1`), fetching pending questions, and retrieving carer schedule
    - _Requirements: 2.1, 3.2, 6.1, 7.5_

- [x] 2. Backend authentication service
  - [x] 2.1 Implement JWT auth endpoints
    - Create `backend/app/services/auth_service.py` with JWT token creation (access 15min, refresh 7d), password hashing (bcrypt), and token validation
    - Create `backend/app/routes/mobile_auth.py` with endpoints: `POST /api/mobile/auth/login`, `POST /api/mobile/auth/refresh`, `POST /api/mobile/auth/device-token`
    - Implement rate limiting: 5 failed attempts → 60s lockout
    - Register router in `backend/app/main.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [ ]* 2.2 Write property test for lockout mechanism
    - **Property 18: Lockout activates after 5 consecutive failures**
    - **Validates: Requirements 1.6**

- [x] 3. Backend signal ingestion API
  - [x] 3.1 Implement signal ingestion endpoints
    - Create `backend/app/routes/mobile_signals.py` with endpoints: `POST /api/mobile/signals/gps` (batch support), `POST /api/mobile/signals/question`, `POST /api/mobile/signals/proactive`
    - Validate signal schemas, timestamps, and field constraints
    - Implement idempotent handling (deduplicate by carer_id + captured_at + signal_type)
    - Dispatch validated signals to the Status Inference Engine
    - Register router in `backend/app/main.py`
    - _Requirements: 3.2, 3.4, 4.3, 5.4, 5.7_

  - [ ]* 3.2 Write property test for GPS low-accuracy flag
    - **Property 2: GPS low-accuracy flag is set correctly**
    - **Validates: Requirements 3.4**

  - [ ]* 3.3 Write property test for proactive input note length validation
    - **Property 20: Proactive input note length validation**
    - **Validates: Requirements 5.3**

  - [ ]* 3.4 Write property test for location-unavailable flag
    - **Property 21: Location-unavailable flag**
    - **Validates: Requirements 5.7**

- [x] 4. Backend schedule and visit status endpoints
  - [x] 4.1 Implement mobile schedule and status endpoints
    - Create `backend/app/routes/mobile_schedule.py` with endpoints: `GET /api/mobile/schedule`, `GET /api/mobile/schedule/{visit_id}`, `GET /api/mobile/visits/{visit_id}/status`
    - Return visits sorted chronologically by window_start
    - Include current visit status and confidence score in responses
    - Register router in `backend/app/main.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.6_

  - [ ]* 4.2 Write property test for schedule chronological ordering
    - **Property 5: Schedule display is sorted chronologically**
    - **Validates: Requirements 2.3**

- [x] 5. Checkpoint - Backend API foundation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Status Inference Engine implementation
  - [x] 6.1 Implement core Status Inference Engine
    - Create `backend/app/services/status_inference.py` with the `StatusInferenceEngine` class
    - Implement signal priority evaluation: explicit confirmation (confidence 100) > GPS with time correlation (confidence 60-85) > time-based inference (decaying confidence)
    - Implement geofence calculations: entry at 100m, exit at 150m (hysteresis), in-progress threshold at 5min continuous presence, completion threshold at departure after duration ±50%
    - Implement confidence decay: -20 points per 15min silence on non-terminal visits
    - Implement conflict detection: conflicting signals within 10min → uncertain + trigger question
    - Enforce valid transitions from `VALID_TRANSITIONS` map; reject and log invalid transitions
    - Record audit trail in `visit_status_transitions` table for every successful transition
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ]* 6.2 Write property test for valid state transitions
    - **Property 1: Visit status transitions are valid**
    - **Validates: Requirements 7.2, 7.6**

  - [ ]* 6.3 Write property test for explicit signal override
    - **Property 6: Explicit signals override GPS inference with confidence 100**
    - **Validates: Requirements 6.4**

  - [ ]* 6.4 Write property test for geofence presence triggers in_progress
    - **Property 7: Geofence presence duration triggers in_progress inference**
    - **Validates: Requirements 6.2**

  - [ ]* 6.5 Write property test for departure triggers completed
    - **Property 8: Departure after expected duration triggers completed inference**
    - **Validates: Requirements 6.3**

  - [ ]* 6.6 Write property test for confidence score range
    - **Property 9: Confidence score is always in valid range**
    - **Validates: Requirements 6.6**

  - [ ]* 6.7 Write property test for low confidence triggers question with rate limit
    - **Property 10: Low confidence triggers question with rate limiting**
    - **Validates: Requirements 6.7**

  - [ ]* 6.8 Write property test for signal timeout confidence decay
    - **Property 11: Signal timeout causes confidence decay**
    - **Validates: Requirements 6.8**

  - [ ]* 6.9 Write property test for conflicting signals
    - **Property 12: Conflicting signals trigger uncertain status and question**
    - **Validates: Requirements 6.5**

  - [ ]* 6.10 Write property test for missed transition at timeout
    - **Property 13: Missed transition at timeout threshold**
    - **Validates: Requirements 7.3**

  - [ ]* 6.11 Write property test for running late transitions
    - **Property 14: Running late signal transitions to delayed only from valid states**
    - **Validates: Requirements 7.4**

  - [ ]* 6.12 Write property test for audit trail completeness
    - **Property 15: Transition audit records contain all required fields**
    - **Validates: Requirements 7.5**

  - [ ]* 6.13 Write property test for non-terminal visit re-evaluation
    - **Property 22: Non-terminal visits re-evaluated on signal receipt**
    - **Validates: Requirements 6.1**

- [x] 7. Question Engine and Notification Service
  - [x] 7.1 Implement Question Engine
    - Create `backend/app/services/question_engine.py` with logic to determine appropriate questions based on carer context (visit state, confidence level, time since last question)
    - Enforce rate limit: max 1 question per visit per 10 minutes
    - Manage question lifecycle: sent → answered/timed_out/suppressed
    - Create `backend/app/routes/mobile_questions.py` with endpoints: `GET /api/mobile/questions/pending`, `POST /api/mobile/questions/{id}/timeout`
    - Register router in `backend/app/main.py`
    - _Requirements: 4.1, 4.4, 6.7_

  - [x] 7.2 Implement Notification Service
    - Create `backend/app/services/notification_service.py` wrapping FCM/APNs delivery
    - Implement retry logic: 3 attempts, 30s intervals, mark undelivered after exhaustion
    - Implement rate limit: max 10 notifications/hour/carer (sliding window)
    - Track delivery status in `push_notifications` table
    - _Requirements: 9.1, 9.2, 9.4, 9.6_

  - [ ]* 7.3 Write property test for push notification rate limit
    - **Property 16: Push notification rate limit**
    - **Validates: Requirements 9.6**

- [x] 8. Checkpoint - Backend services complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Mobile app project setup (React Native / Expo)
  - [x] 9.1 Initialise React Native Expo project
    - Create `mobile/` directory with Expo TypeScript template
    - Install core dependencies: `expo-location`, `react-native-background-geolocation`, `expo-sqlite`, `expo-notifications`, `expo-secure-store`, `@react-navigation/native`
    - Configure `app.json` / `app.config.ts` with iOS and Android permissions for location (always), notifications, and background modes
    - Set up project structure: `src/services/`, `src/screens/`, `src/components/`, `src/store/`, `src/types/`, `src/utils/`
    - _Requirements: 3.1, 9.3_

  - [x] 9.2 Create TypeScript type definitions and API client
    - Create `mobile/src/types/` with interfaces matching backend Pydantic models: `GPSSignal`, `GPSBatch`, `QuestionResponse`, `ProactiveInput`, `VisitStatus`, `MobileVisitSummary`, `MobileVisitDetail`, `ContextualQuestionPayload`
    - Create `mobile/src/services/apiClient.ts` with Axios-based HTTP client, automatic token injection, 401 interceptor for refresh flow, and base URL configuration
    - _Requirements: 1.3, 1.4_

- [x] 10. Mobile authentication flow
  - [x] 10.1 Implement mobile auth service and login screen
    - Create `mobile/src/services/authService.ts` with login, refresh, logout, and device token registration
    - Store tokens securely using `expo-secure-store`
    - Implement silent refresh: attempt refresh when token is within 5 minutes of expiry
    - Implement lockout: disable login for 60s after 5 consecutive failures with countdown display
    - Create `mobile/src/screens/LoginScreen.tsx` with identifier/password fields, error messages, offline notification, and timeout handling (15s)
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7_

- [x] 11. Mobile schedule view
  - [x] 11.1 Implement schedule screen with offline caching
    - Create `mobile/src/screens/ScheduleScreen.tsx` displaying today's visits sorted by window_start
    - Display: patient name, address, time window, duration, required skills, current status with confidence indicator
    - Implement pull-to-refresh and auto-refresh (poll every 60s or push-triggered)
    - Cache schedule in local SQLite for offline access
    - Show persistent offline indicator when no connectivity
    - Handle empty state (no visits today)
    - Create `mobile/src/screens/VisitDetailScreen.tsx` with full visit info and "Open in Maps" button
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

- [x] 12. Mobile GPS tracker service
  - [x] 12.1 Implement GPS tracker with adaptive frequency and geofencing
    - Create `mobile/src/services/gpsTracker.ts` using `react-native-background-geolocation`
    - Implement adaptive frequency: 60s standard → 15s within 100m of visit → 5min when no visit within 2h or battery < 15%
    - Implement geofence entry (100m) and exit (150m hysteresis) detection for all scheduled visit addresses
    - Flag low-accuracy signals (accuracy > 50m)
    - Resume standard frequency when battery recovers above 20%
    - Calculate GPS speed for driving detection (used by Question Handler)
    - Pipe all signals to the Offline Buffer
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 10.1, 10.3, 10.5_

  - [ ]* 12.2 Write property test for GPS adaptive frequency
    - **Property 3: GPS frequency adapts to context priority**
    - **Validates: Requirements 3.3, 10.1, 10.3, 10.5**

- [x] 13. Mobile proactive input module
  - [x] 13.1 Implement proactive input UI and service
    - Create `mobile/src/components/ProactiveInputFAB.tsx` — floating action button accessible within 2 taps from any screen
    - Create `mobile/src/screens/ProactiveInputSheet.tsx` with predefined options: arrived, visit started, visit completed, running late, issue encountered, cannot complete
    - Allow optional free-text note (max 500 chars, client-side validation)
    - Attach current GPS coordinates and timestamp; set `location_unavailable` flag if GPS unavailable
    - Show confirmation feedback on submission
    - Pipe submissions to the Offline Buffer
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 14. Mobile question handler
  - [x] 14.1 Implement contextual question display and response
    - Create `mobile/src/services/questionHandler.ts` to process incoming question payloads
    - Create `mobile/src/components/QuestionOverlay.tsx` — non-intrusive notification overlay supporting yes/no, single-choice (max 5 options), and free-text (max 300 chars) types
    - Implement 5-minute timeout with backend notification on expiry
    - Implement driving suppression: suppress when GPS speed > 10 km/h, queue (max 10), display when speed ≤ 10 km/h for 30+ seconds
    - Pipe responses to the Offline Buffer
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 14.2 Write property test for question suppression during driving
    - **Property 19: Question suppression during driving**
    - **Validates: Requirements 4.6**

- [x] 15. Mobile offline buffer and sync queue
  - [x] 15.1 Implement SQLite-backed offline buffer and sync queue
    - Create `mobile/src/services/offlineBuffer.ts` — SQLite-backed FIFO queue for all outbound signals (GPS, question responses, proactive inputs)
    - Enforce chronological sync order by `captured_at` timestamp
    - Implement capacity tracking: 1000+ signals, notify carer when approaching limit
    - Retain data for minimum 24 hours
    - Create `mobile/src/services/syncQueue.ts` — connectivity-aware sync manager
    - Implement exponential backoff: 30s base, max 5 attempts
    - Implement GPS batching: 3+ pending GPS signals → single batch request
    - Trigger sync within 30s of connectivity restoration
    - Preserve original `captured_at` timestamps in all transmitted signals
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 10.2_

  - [ ]* 15.2 Write property test for chronological order preservation
    - **Property 4: Offline buffer preserves chronological order and original timestamps**
    - **Validates: Requirements 3.5, 4.7, 5.5, 8.2, 8.4**

  - [ ]* 15.3 Write property test for GPS batching rule
    - **Property 17: GPS batching rule**
    - **Validates: Requirements 10.2**

- [x] 16. Mobile push notification handler
  - [x] 16.1 Implement push notification registration and handling
    - Create `mobile/src/services/pushNotificationHandler.ts`
    - Register device token with backend on successful auth
    - Route notifications to appropriate handler: schedule update → refresh schedule, question → display QuestionOverlay
    - Implement tap-to-navigate: schedule changes → ScheduleScreen, questions → question prompt
    - Fall back to in-app banners when push permission denied
    - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [x] 17. Integration wiring and end-to-end flow
  - [x] 17.1 Wire all mobile components together
    - Create `mobile/src/App.tsx` with navigation setup (auth flow → main flow)
    - Wire GPS Tracker → Offline Buffer → Sync Queue → Backend Signal API
    - Wire Push Notification Handler → Question Handler / Schedule refresh
    - Wire Proactive Input → Offline Buffer → Sync Queue
    - Ensure auth token is available to all services before starting GPS/sync
    - Add persistent offline indicator component to main navigation
    - _Requirements: 1.3, 3.2, 5.4, 8.1, 9.3_

  - [ ]* 17.2 Write integration tests for end-to-end signal flow
    - Test: mobile signal submission → API ingestion → inference engine → status update
    - Test: offline buffer → connectivity restored → chronological sync → backend processing
    - Test: push notification → question display → response → status update
    - _Requirements: 6.1, 8.2, 9.2_

- [x] 18. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis (Python backend) and fast-check (TypeScript mobile)
- Unit tests validate specific examples and edge cases
- Backend uses Python/FastAPI (existing stack); mobile uses React Native/Expo with TypeScript
- All 22 correctness properties from the design document are covered by property-based test tasks

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "4.1", "9.1"] },
    { "id": 3, "tasks": ["2.2", "3.1", "4.2", "9.2"] },
    { "id": 4, "tasks": ["3.2", "3.3", "3.4", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4", "6.5", "6.6", "6.7", "6.8", "6.9", "6.10", "6.11", "6.12", "6.13", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "10.1"] },
    { "id": 7, "tasks": ["11.1", "12.1"] },
    { "id": 8, "tasks": ["12.2", "13.1", "14.1"] },
    { "id": 9, "tasks": ["14.2", "15.1"] },
    { "id": 10, "tasks": ["15.2", "15.3", "16.1"] },
    { "id": 11, "tasks": ["17.1"] },
    { "id": 12, "tasks": ["17.2"] }
  ]
}
```
