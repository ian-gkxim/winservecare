# Requirements Document

## Introduction

The Background Optimisation Jobs feature decouples the optimisation solver from the WebSocket page connection, allowing optimisation to run as a persistent background job that survives page navigation. It adds in-app notifications when jobs complete, the ability to check progress from any page, and data staleness detection that warns when source data changes invalidate running or completed optimisation results.

## Glossary

- **Background_Job**: A server-side optimisation task that executes independently of the client's WebSocket or page lifecycle, identified by a unique job identifier
- **Job_Registry**: The backend store (in-memory or SQLite) that tracks all active and recently completed Background_Jobs with their status, progress, and results
- **Job_Status**: The current state of a Background_Job, one of: queued, running, completed, failed, or stale
- **Notification_Service**: The component responsible for delivering in-app alerts to the Administrator when a Background_Job completes or fails
- **Toast_Notification**: A non-modal, temporary alert displayed in the application UI regardless of which page the Administrator is viewing
- **Data_Fingerprint**: A hash or timestamp-based identifier representing the state of solver-input data (carers, visits, patients, constraints) at a specific point in time
- **Staleness_Indicator**: A visual marker on optimisation results indicating that source data has changed since the Background_Job started
- **Edit_Guard**: A confirmation prompt shown to the Administrator before allowing modifications to solver-input data while a Background_Job is running
- **Optimiser**: The backend service that computes optimal visit assignments and routes using the OR-Tools VRP solver
- **Administrator**: The single user of the system who triggers optimisation runs and views results
- **Source_Data**: The set of database tables (carers, visits, patients, constraints) that serve as input to the Optimiser

## Requirements

### Requirement 1: Background Job Lifecycle

**User Story:** As an Administrator, I want optimisation to run as a persistent background job, so that I can navigate freely in the application without losing the optimisation results.

#### Acceptance Criteria

1. WHEN the Administrator triggers an optimisation run, THE system SHALL create a Background_Job with a unique identifier (UUID v4) and return the job identifier to the client within 1 second via an HTTP 202 Accepted response, without requiring the client to maintain a WebSocket connection for the duration of the computation
2. WHEN a Background_Job is created, THE Job_Registry SHALL record the job identifier, creation timestamp (UTC ISO 8601), Job_Status of "queued", the Data_Fingerprint of Source_Data at the time of creation, and the list of visit IDs included in the optimisation
3. WHEN the Optimiser begins processing a Background_Job, THE Job_Registry SHALL update the Job_Status from "queued" to "running" and record the start timestamp (UTC ISO 8601) within 1 second of execution beginning
4. WHEN the Optimiser completes a Background_Job successfully, THE Job_Registry SHALL update the Job_Status to "completed", store the full OptimisationResult as a JSON blob, and record the completion timestamp (UTC ISO 8601)
5. IF the Optimiser encounters an unrecoverable error during a Background_Job, THEN THE Job_Registry SHALL update the Job_Status to "failed", store the error description (maximum 1000 characters), and record the failure timestamp
6. WHILE a Background_Job has Job_Status of "running", THE system SHALL continue processing the optimisation regardless of whether the Administrator's browser tab is open, closed, or navigated to a different page — the background task runs in the server process independently of any client connection

### Requirement 2: Job Progress Polling

**User Story:** As an Administrator, I want to check the progress of a running optimisation at any time, so that I know how far along it is without staying on a specific page.

#### Acceptance Criteria

1. THE system SHALL expose a REST endpoint `GET /api/jobs/{job_id}/progress` that accepts a job identifier and returns the current job status (one of: "queued", "running", "completed", "failed", "stale"), elapsed time in seconds (integer), percentage complete (0–100, integer), solutions found count (integer, 0 or greater), and current best objective score (numeric or null if no solution found yet)
2. IF the Administrator requests progress for a job identifier that does not correspond to any current or recent optimisation run, THEN THE system SHALL return an HTTP 404 response indicating the job was not found
3. WHEN the Administrator navigates to the optimisation page while a Background_Job is running, THE Dashboard SHALL poll the progress endpoint every 2 seconds and display the percentage complete, elapsed time, and current best score
4. WHEN the Administrator navigates away from the optimisation page and returns while a Background_Job is still running, THE Dashboard SHALL resume polling and displaying progress from the job's current state without restarting the job or losing previously reported progress
5. WHEN a Background_Job completes while the Administrator is viewing the optimisation page, THE Dashboard SHALL display the final results within 2 seconds of the next poll detecting completion, including the animated map visualisation and schedule comparison

### Requirement 3: Completion Notifications

**User Story:** As an Administrator, I want to receive an in-app notification when optimisation completes, so that I know results are ready regardless of which page I am viewing.

#### Acceptance Criteria

1. WHEN a Background_Job transitions to Job_Status "completed" and the Administrator is not on the optimisation page, THE Notification_Service SHALL display a Toast_Notification containing the text "Optimisation complete" and a link to view the results
2. WHEN a Background_Job transitions to Job_Status "failed" and the Administrator is not on the optimisation page, THE Notification_Service SHALL display a Toast_Notification containing the text "Optimisation failed" and a description of no more than 200 characters indicating the reason for the failure
3. WHEN the Administrator clicks the results link in a completion Toast_Notification, THE system SHALL navigate the Administrator to the optimisation page and display the completed results
4. THE Toast_Notification SHALL remain visible for a minimum of 10 seconds and SHALL auto-dismiss after 30 seconds, and SHALL be manually dismissible by the Administrator at any time before the auto-dismiss timeout
5. WHILE the Administrator is on the optimisation page, WHEN a Background_Job completes, THE system SHALL update the page with results directly and SHALL NOT display a Toast_Notification
6. IF the notification delivery connection is lost while the Administrator is viewing any page, THEN THE system SHALL attempt to reconnect at intervals of 5 seconds for up to 3 attempts, and upon reconnection SHALL deliver any notifications for jobs that completed during the disconnection period
7. IF multiple notifications arrive while existing Toast_Notifications are still visible, THEN THE Notification_Service SHALL stack them vertically displaying up to 3 Toast_Notifications simultaneously, with the most recent notification on top

### Requirement 4: Data Fingerprinting

**User Story:** As an Administrator, I want the system to track whether source data has changed since an optimisation started, so that I can trust that results reflect current data.

#### Acceptance Criteria

1. WHEN a Background_Job is created, THE system SHALL compute a Data_Fingerprint by recording the maximum updated_at timestamp from each Source_Data table (carers, visits, patients, constraints) in a single database transaction, where a table with no rows contributes a NULL timestamp to the fingerprint
2. WHEN a Background_Job transitions to Job_Status "completed", THE system SHALL recompute the current Data_Fingerprint and compare each table's maximum updated_at timestamp against the corresponding value recorded at job creation; the fingerprints differ if any single table's current timestamp is different from (or transitions between NULL and non-NULL relative to) its creation-time value
3. IF the current Data_Fingerprint differs from the creation Data_Fingerprint when a Background_Job completes, THEN THE Job_Registry SHALL update the Job_Status to "stale" instead of "completed"
4. THE system SHALL include in the job status response a boolean field `is_stale` indicating whether the Data_Fingerprint has changed since job creation, and an object `stale_tables` listing each Source_Data table name with a boolean indicating whether that specific table's timestamp differs, so the frontend can display the Staleness_Indicator with per-table detail

### Requirement 5: Stale Results Display

**User Story:** As an Administrator, I want to see a clear warning when optimisation results are based on outdated data, so that I do not make decisions using invalid recommendations.

#### Acceptance Criteria

1. WHEN the Administrator views results of a Background_Job with Job_Status "stale", THE Dashboard SHALL display a Staleness_Indicator banner above the results stating "Results based on outdated data — source data was modified after this optimisation started"
2. WHEN the Administrator views stale results, THE Dashboard SHALL display a "Re-run optimisation" button adjacent to the Staleness_Indicator banner
3. WHEN the Administrator clicks "Re-run optimisation" on stale results, THE system SHALL create a new Background_Job using the current Source_Data, navigate to the Dashboard progress view for the new job, and disable the "Re-run optimisation" button until the new job completes or fails
4. WHEN Source_Data is modified after a Background_Job has completed with Job_Status "completed", THE Job_Registry SHALL update the Job_Status to "stale" within 5 seconds of the modification being persisted
5. IF the re-run Background_Job triggered from stale results fails, THEN THE Dashboard SHALL display an error notification indicating the failure reason and SHALL retain the original stale results with the Staleness_Indicator banner still visible

### Requirement 6: Edit Guards During Running Jobs

**User Story:** As an Administrator, I want to be warned before editing solver-input data while optimisation is running, so that I do not accidentally invalidate an in-progress computation.

#### Acceptance Criteria

1. WHILE a Background_Job has Job_Status "running", WHEN the Administrator attempts to save an edit to any Source_Data record (carer, visit, patient, or constraint), THE system SHALL query the backend for current job status and, if confirmed running, display a modal Edit_Guard confirmation dialog before persisting the change
2. THE Edit_Guard dialog SHALL display the message "A running optimisation uses this data. Saving changes will mark its results as outdated. Continue?" with "Continue" and "Cancel" action buttons
3. WHEN the Administrator selects "Continue" on the Edit_Guard dialog, THE system SHALL persist the edit within 2 seconds and, if the Background_Job still has Job_Status "running" at the time of persistence, THE system SHALL mark the Background_Job's Data_Fingerprint as invalidated
4. WHEN the Administrator selects "Cancel" on the Edit_Guard dialog, THE system SHALL discard the pending edit, close the dialog, and return focus to the edit form with all field values restored to their state immediately before the save attempt
5. WHILE no Background_Job has Job_Status "running", THE system SHALL allow edits to Source_Data without displaying an Edit_Guard dialog
6. IF the backend job-status check fails or does not respond within 5 seconds when the Administrator attempts to save, THEN THE system SHALL proceed with the save without displaying the Edit_Guard dialog and SHALL log the status-check failure for diagnostic purposes

### Requirement 7: Job History and Cleanup

**User Story:** As an Administrator, I want to see a history of recent optimisation jobs, so that I can review past runs and their outcomes.

#### Acceptance Criteria

1. THE system SHALL expose a REST endpoint `GET /api/jobs` that returns a list of Background_Jobs ordered by creation timestamp descending, including for each job: identifier, creation timestamp, Job_Status, completion timestamp (if applicable), and a stale flag indicating whether any Source_Data has been modified since the job's completion timestamp
2. THE Job_Registry SHALL retain completed and failed Background_Jobs for at least 24 hours after their completion timestamp
3. WHEN a new Background_Job is created and the Job_Registry contains more than 20 retained jobs, THE system SHALL remove the oldest jobs beyond the 20-job limit (ordered by completion timestamp ascending), deleting their stored JSON result blobs
4. THE system SHALL allow only one Background_Job with Job_Status "queued" or "running" at a time
5. IF the Administrator triggers a new optimisation while a Background_Job with Job_Status "queued" or "running" already exists, THEN THE system SHALL reject the request and return an HTTP 409 Conflict response indicating that an optimisation is already in progress, including the identifier of the active job
6. WHEN the Administrator cancels an active Background_Job via `DELETE /api/jobs/{job_id}`, THE system SHALL set its Job_Status to "cancelled", halt any in-progress computation within 5 seconds, retain the job in the Job_Registry with no stored results, and return HTTP 200 confirming the cancellation
