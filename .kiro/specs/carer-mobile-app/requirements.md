# Requirements Document

## Introduction

The Carer Mobile App is a cross-platform mobile application (iOS and Android) for care workers in the WinServeCare scheduling optimisation system. The app provides carers with a view of their scheduled visits and implements a multi-signal reporting system that combines GPS location tracking, contextual questions, and proactive user input to keep the backend informed of real-time job status. The server uses these three signal types to maintain an accurate picture of visit progress, making educated inferences when explicit confirmation is unavailable.

## Glossary

- **Mobile_App**: The cross-platform mobile application installed on carers' devices (iOS and Android)
- **Backend**: The existing WinServeCare Python/FastAPI server that manages carers, patients, visits, and optimisation
- **Carer**: A care worker who travels to patient addresses to deliver scheduled visits
- **Visit**: A scheduled care appointment at a patient address with a defined time window and duration
- **Job_Schedule**: The ordered list of visits assigned to a carer for a given day
- **GPS_Signal**: A location report containing the carer's latitude, longitude, accuracy, and timestamp
- **Status_Inference_Engine**: The server-side component that combines GPS, question responses, and proactive inputs to determine visit status
- **Contextual_Question**: A timely prompt presented to the carer based on their current context (location, time, schedule state)
- **Proactive_Input**: A voluntary status report initiated by the carer without a system prompt
- **Geofence**: A virtual geographic boundary around a patient address used to detect proximity
- **Visit_Status**: The current state of a visit (e.g., pending, travelling, arrived, in_progress, completed, delayed, missed)
- **Signal**: Any data point sent from the Mobile_App to the Backend (GPS coordinates, question answer, or proactive input)

## Requirements

### Requirement 1: Carer Authentication

**User Story:** As a carer, I want to securely log in to the mobile app, so that I can access my personal schedule and report on my visits.

#### Acceptance Criteria

1. WHEN a carer provides valid credentials (identifier and password), THE Mobile_App SHALL authenticate the carer against the Backend and grant access to the app within 10 seconds of submission
2. WHEN a carer provides invalid credentials, THE Mobile_App SHALL display an error message indicating that the credentials are incorrect, remain on the login screen, and retain the entered identifier
3. WHILE the carer is authenticated, THE Mobile_App SHALL include a valid authentication token in all requests to the Backend
4. WHEN the authentication token is within 5 minutes of expiry, THE Mobile_App SHALL attempt a silent token refresh against the Backend; IF the silent refresh fails, THEN THE Mobile_App SHALL prompt the carer to re-authenticate
5. IF the Mobile_App loses network connectivity during authentication, THEN THE Mobile_App SHALL display an offline notification and retry authentication automatically when connectivity is restored, up to 3 retry attempts within 5 minutes before requiring the carer to manually re-initiate login
6. IF a carer provides invalid credentials 5 consecutive times, THEN THE Mobile_App SHALL disable the login control for 60 seconds and display a message indicating the temporary lockout duration
7. IF the Backend does not respond to an authentication request within 15 seconds, THEN THE Mobile_App SHALL display an error message indicating a connection timeout and allow the carer to retry

### Requirement 2: Job Schedule Display

**User Story:** As a carer, I want to view my upcoming visits for the day, so that I can plan my route and manage my time effectively.

#### Acceptance Criteria

1. WHEN the carer opens the schedule view, THE Mobile_App SHALL retrieve the carer's assigned visits for the current day from the Backend and display them within 5 seconds
2. THE Mobile_App SHALL display each visit in the schedule list with the patient name, address, scheduled time window (start and end), expected duration in minutes, and required skills
3. THE Mobile_App SHALL order visits chronologically by their scheduled time window start time
4. WHEN a visit assignment changes on the Backend, THE Mobile_App SHALL update the schedule view within 60 seconds
5. WHILE the Mobile_App has no network connectivity, THE Mobile_App SHALL display the most recently cached schedule with a persistently visible offline indicator that remains on screen until connectivity is restored
6. WHEN the carer taps a visit in the schedule, THE Mobile_App SHALL display the full visit details including patient name, full address, scheduled time window, expected duration, required skills, patient preferences, and an option to open the patient address in the device's native maps application for navigation
7. IF the Backend request for the schedule fails due to a network or server error, THEN THE Mobile_App SHALL display a retrieval error message indicating the failure reason and offer a manual retry option
8. WHEN the carer has no visits assigned for the current day, THE Mobile_App SHALL display an empty state message indicating that no visits are scheduled for today

### Requirement 3: GPS Location Tracking

**User Story:** As a system operator, I want the app to track carer GPS coordinates, so that the server can infer proximity to job sites and estimate arrival and departure times.

#### Acceptance Criteria

1. WHILE the carer is authenticated and has granted location permission, THE Mobile_App SHALL collect GPS coordinates at a regular interval of no more than 60 seconds
2. WHEN the Mobile_App collects a GPS_Signal, THE Mobile_App SHALL transmit it to the Backend within 10 seconds of collection, including latitude, longitude, accuracy in metres, and UTC timestamp
3. WHEN the carer enters within 100 metres of a scheduled visit address, THE Mobile_App SHALL increase GPS reporting frequency to no more than 15 seconds, and SHALL revert to the standard 60-second interval when the carer moves beyond 150 metres from that address
4. IF the device GPS accuracy exceeds 50 metres, THEN THE Mobile_App SHALL flag the GPS_Signal with a low-accuracy indicator
5. WHILE the Mobile_App has no network connectivity, THE Mobile_App SHALL buffer GPS_Signals locally and transmit them in chronological order when connectivity is restored
6. WHEN the carer denies location permission, THE Mobile_App SHALL notify the carer that GPS-based status reporting is unavailable and SHALL continue operating without GPS collection, geofence-based frequency changes, or proximity-based contextual questions

### Requirement 4: Contextual Questions

**User Story:** As a system operator, I want the app to ask carers timely questions at appropriate moments, so that the server receives explicit confirmation of visit status transitions.

#### Acceptance Criteria

1. WHEN the Backend determines a contextual question is appropriate based on the carer's current state, THE Backend SHALL send a question payload to the Mobile_App containing: question text, question type, response options (if applicable), and the associated visit identifier
2. WHEN the Mobile_App receives a Contextual_Question, THE Mobile_App SHALL display the question as a notification that does not obscure the current screen content or require immediate interaction, within 5 seconds of receipt
3. WHEN the carer responds to a Contextual_Question, THE Mobile_App SHALL transmit the response to the Backend within 10 seconds, including the question identifier, selected answer, and UTC timestamp of the response
4. IF the carer does not respond to a Contextual_Question within 5 minutes, THEN THE Mobile_App SHALL dismiss the question and notify the Backend of the timeout with the question identifier and timeout timestamp
5. THE Mobile_App SHALL support exactly three question types: yes/no confirmation, single-choice selection (maximum 5 options), and free-text input (maximum 300 characters)
6. WHILE the carer is driving (GPS speed exceeds 10 km/h), THE Mobile_App SHALL suppress new Contextual_Questions and queue them (maximum 10 queued questions) for display when the carer's GPS speed remains at or below 10 km/h for at least 30 consecutive seconds
7. IF the Mobile_App has no network connectivity when a carer responds to a Contextual_Question, THEN THE Mobile_App SHALL buffer the response locally and transmit it when connectivity is restored with the original response timestamp

### Requirement 5: Proactive Input

**User Story:** As a carer, I want to voluntarily report status changes, issues, or delays at any time, so that the system stays informed without me waiting for a prompt.

#### Acceptance Criteria

1. THE Mobile_App SHALL provide a persistent, accessible control for carers to initiate a Proactive_Input at any point during their shift, reachable within 2 taps from any screen
2. THE Mobile_App SHALL offer predefined proactive input options including: arrived at visit, visit started, visit completed, running late, issue encountered, and visit cannot be completed
3. WHEN the carer selects a predefined Proactive_Input option, THE Mobile_App SHALL allow the carer to add an optional free-text note of up to 500 characters
4. WHEN the carer submits a Proactive_Input, THE Mobile_App SHALL transmit the input type, associated visit identifier, optional note, GPS coordinates, and UTC timestamp to the Backend within 10 seconds
5. WHILE the Mobile_App has no network connectivity, THE Mobile_App SHALL store Proactive_Inputs locally and transmit them when connectivity is restored with their original timestamps
6. WHEN the carer submits a Proactive_Input, THE Mobile_App SHALL display a confirmation that the input was recorded
7. IF GPS coordinates are unavailable when a Proactive_Input is submitted, THEN THE Mobile_App SHALL transmit the input without coordinates and flag it as location-unavailable

### Requirement 6: Server-Side Status Inference

**User Story:** As a system operator, I want the server to combine GPS, question responses, and proactive inputs to maintain an accurate picture of visit status, so that the scheduling system reflects real-world progress.

#### Acceptance Criteria

1. WHEN the Status_Inference_Engine receives a new Signal, THE Status_Inference_Engine SHALL re-evaluate the visit status for all visits assigned to the carer that are not in a terminal state (completed, missed, or cancelled) within 30 seconds
2. WHEN GPS_Signals indicate a carer has been within the Geofence of a patient address for more than 5 minutes and no Proactive_Input or Contextual_Question response indicating a different status has been received for that visit, THE Status_Inference_Engine SHALL infer the visit status as in_progress
3. WHEN GPS_Signals indicate a carer has remained outside the Geofence of a patient address for more than 2 minutes after being present for a duration consistent with the scheduled visit duration (within 50% tolerance), THE Status_Inference_Engine SHALL infer the visit status as completed
4. WHEN a Proactive_Input or Contextual_Question response explicitly confirms a visit status, THE Status_Inference_Engine SHALL set the visit status to the confirmed value and assign a confidence score of 100, overriding any GPS-based inference
5. IF conflicting signals are received for the same visit within a 10-minute window (e.g., GPS suggests departure but no completion signal, or GPS indicates presence at a different patient address while a visit is marked in_progress), THEN THE Status_Inference_Engine SHALL mark the visit status as uncertain and trigger a Contextual_Question to the carer
6. THE Status_Inference_Engine SHALL assign a confidence score between 0 and 100 to each inferred visit status
7. WHEN the confidence score for a visit status falls below 60, THE Status_Inference_Engine SHALL trigger a Contextual_Question to request explicit confirmation from the carer, limited to no more than 1 question per visit within any 10-minute period
8. IF no Signal is received from a carer's Mobile_App for more than 15 minutes while the carer has a non-terminal visit, THEN THE Status_Inference_Engine SHALL reduce the confidence score of the current inferred status by 20 points and trigger a Contextual_Question to the carer

### Requirement 7: Visit Status Lifecycle

**User Story:** As a system operator, I want visits to follow a defined status lifecycle, so that transitions are predictable and auditable.

#### Acceptance Criteria

1. THE Backend SHALL support the following Visit_Status values: pending, travelling, arrived, in_progress, completed, delayed, missed, and cancelled
2. THE Status_Inference_Engine SHALL only permit the following status transitions: pending → travelling, travelling → arrived, arrived → in_progress, in_progress → completed, pending → delayed, travelling → delayed, delayed → travelling, pending → missed, pending → cancelled, travelling → cancelled, arrived → cancelled, in_progress → cancelled, and delayed → cancelled
3. WHEN a visit remains in pending or delayed status and 30 minutes have elapsed after the scheduled time window end, THE Status_Inference_Engine SHALL transition the visit status to missed
4. WHEN the carer reports running late via Proactive_Input and the visit status is pending or travelling, THE Status_Inference_Engine SHALL transition the visit status to delayed
5. THE Backend SHALL record each status transition with the previous status, the new status, the triggering signal type, a UTC timestamp, and the confidence score for audit purposes
6. IF the Status_Inference_Engine receives a signal that would result in a transition not listed in the valid transitions, THEN THE Status_Inference_Engine SHALL reject the transition, retain the current visit status unchanged, and log the rejected transition attempt with the visit identifier, attempted target status, and UTC timestamp
7. WHEN the carer resumes travel after a delay is resolved (GPS movement detected away from current location or carer submits a Proactive_Input indicating resumed travel), THE Status_Inference_Engine SHALL transition the visit status from delayed to travelling

### Requirement 8: Offline Resilience

**User Story:** As a carer, I want the app to continue functioning when I lose network connectivity, so that I can still view my schedule and report on visits.

#### Acceptance Criteria

1. WHILE the Mobile_App has no network connectivity, THE Mobile_App SHALL allow the carer to view the most recently cached schedule for the current day and submit Proactive_Inputs, and SHALL display a visible offline indicator
2. WHEN network connectivity is restored, THE Mobile_App SHALL begin synchronising all buffered Signals to the Backend in chronological order within 30 seconds of detecting connectivity
3. THE Mobile_App SHALL retain buffered data for a minimum of 24 hours without network connectivity and SHALL support buffering at least 1000 Signals before indicating to the carer that buffer capacity is approaching its limit
4. WHEN the Mobile_App synchronises buffered Signals, THE Mobile_App SHALL include the original capture timestamp for each Signal so the Backend can process them in correct temporal order
5. IF buffered Signal synchronisation fails, THEN THE Mobile_App SHALL retry with exponential backoff starting at 30 seconds up to 5 attempts before alerting the carer, and SHALL retain all buffered Signals regardless of retry outcome until synchronisation succeeds or the carer manually clears them
6. IF the Mobile_App buffer reaches maximum capacity while offline, THEN THE Mobile_App SHALL continue retaining all existing buffered Signals and SHALL notify the carer that new Signals cannot be stored until connectivity is restored

### Requirement 9: Push Notifications

**User Story:** As a carer, I want to receive timely notifications about schedule changes and contextual questions, so that I stay informed without constantly checking the app.

#### Acceptance Criteria

1. WHEN a visit is added, removed, or rescheduled on the Backend, THE Backend SHALL send a push notification to the affected carer's Mobile_App within 10 seconds of the change
2. WHEN a Contextual_Question is triggered and the Mobile_App is in the background, THE Backend SHALL deliver the question as a push notification that displays the question text
3. WHEN the carer taps a push notification, THE Mobile_App SHALL navigate to the relevant screen (schedule view for schedule changes, or question prompt for contextual questions)
4. IF push notification delivery fails, THEN THE Backend SHALL retry delivery up to 3 times with 30-second intervals before marking the notification as undelivered
5. WHEN the carer denies push notification permission, THE Mobile_App SHALL display an in-app banner for schedule changes and contextual questions when the app is next opened
6. THE Backend SHALL limit push notifications to no more than 10 per hour per carer to prevent notification fatigue during busy shifts

### Requirement 10: Battery and Data Efficiency

**User Story:** As a carer, I want the app to use my phone's battery and data allowance efficiently, so that my device remains usable throughout my shift.

#### Acceptance Criteria

1. WHILE the carer has no visits scheduled within the next 2 hours, THE Mobile_App SHALL reduce GPS collection frequency to no more than once every 5 minutes
2. WHEN 3 or more GPS_Signals are buffered and pending transmission, THE Mobile_App SHALL batch them into a single transmission rather than sending each signal individually
3. IF the device battery level falls below 15%, THEN THE Mobile_App SHALL reduce GPS collection frequency to no more than once every 5 minutes and display a persistent in-app indicator informing the carer that power-saving mode is active
4. THE Mobile_App SHALL use less than 50 MB of mobile data per 8-hour shift when the carer completes up to 12 visits with GPS tracking active and Contextual_Questions answered at normal frequency
5. WHEN the device battery level returns above 20%, THE Mobile_App SHALL resume the standard GPS collection frequency defined by the carer's current schedule context
