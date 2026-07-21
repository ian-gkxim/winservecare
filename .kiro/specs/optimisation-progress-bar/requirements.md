# Requirements Document

## Introduction

The WinServeCare scheduling optimisation can run for extended periods (10+ minutes in practice) with no feedback to the user beyond coarse-grained phase indicators. This feature adds a fine-grained progress bar that communicates meaningful solver progress — including elapsed time, time remaining, number of improved solutions found, and current best objective score — so the user understands that the system is working and can estimate when it will finish.

The progress reporting covers two distinct long-running phases: the Google Maps distance matrix API call and the OR-Tools solver search. Each phase has different measurable indicators of progress.

## Glossary

- **Progress_Service**: The backend component responsible for tracking and emitting fine-grained progress data during optimisation phases
- **Solver**: The OR-Tools routing solver that performs Guided Local Search to find optimal care visit schedules
- **Solution_Callback**: An OR-Tools mechanism that fires each time the solver discovers an improved solution during search
- **Distance_Matrix_Phase**: The phase where the system fetches travel time data from the Google Maps Distance Matrix API
- **Solver_Phase**: The phase where the OR-Tools solver searches for optimal route assignments
- **Time_Limit**: The configured maximum duration the solver is permitted to search (currently 10 seconds in code)
- **Objective_Score**: A numeric value representing the quality of the current best solution (lower is better for minimisation)
- **WebSocket_Client**: The frontend application connected via the `/ws/optimise` WebSocket endpoint
- **Progress_Message**: A JSON message sent over WebSocket containing fine-grained progress data

## Requirements

### Requirement 1: Solver Phase Elapsed Time Reporting

**User Story:** As a scheduling coordinator, I want to see how much time has elapsed and how much remains during optimisation, so that I know the system is still working and can plan my time accordingly.

#### Acceptance Criteria

1. WHEN the Solver_Phase begins, THE Progress_Service SHALL record the start timestamp and the configured Time_Limit, where Time_Limit is the solver duration in seconds as set in the optimisation engine search parameters (between 1 and 300 seconds inclusive)
2. WHILE the Solver_Phase is active, THE Progress_Service SHALL emit a Progress_Message via WebSocket at intervals no greater than 1 second containing elapsed_seconds (integer, seconds since solver start) and time_limit_seconds (integer, the configured Time_Limit) fields
3. THE Progress_Message SHALL include a percentage_complete field calculated as (elapsed_seconds / time_limit_seconds) × 100, capped at 100, rounded down to the nearest integer
4. WHEN the Solver_Phase completes before the Time_Limit expires (early termination due to finding an optimal solution), THE Progress_Service SHALL emit a final Progress_Message with percentage_complete set to 100 and elapsed_seconds set to the actual elapsed duration at completion
5. IF the Solver_Phase fails or is aborted due to an error, THEN THE Progress_Service SHALL emit a final Progress_Message with the last known elapsed_seconds and percentage_complete values, followed by an error indication including the failure reason, and SHALL cease further Progress_Message emission

### Requirement 2: Solver Intermediate Solution Reporting

**User Story:** As a scheduling coordinator, I want to see how many improved solutions the solver has found during the search, so that I have confidence the system is actively finding better schedules.

#### Acceptance Criteria

1. WHEN the Solver finds an improved solution during search, THE Solution_Callback SHALL capture the solution count and current Objective_Score
2. WHEN a new improved solution is found, THE Progress_Service SHALL emit a Progress_Message containing solutions_found (integer count) and current_best_score (numeric Objective_Score)
3. THE Progress_Service SHALL emit the solution improvement Progress_Message within 500 milliseconds of the Solution_Callback firing
4. IF the Solver completes without finding any solution, THEN THE Progress_Service SHALL emit a Progress_Message with solutions_found set to 0

### Requirement 3: Distance Matrix Phase Progress Reporting

**User Story:** As a scheduling coordinator, I want to see progress during the distance matrix retrieval, so that I understand why optimisation has not started the solver yet.

#### Acceptance Criteria

1. WHEN the Distance_Matrix_Phase begins, THE Progress_Service SHALL emit a Progress_Message via WebSocket identifying the phase as "distance_matrix", indicating the phase has started, and including the total number of location pairs being computed
2. WHILE the Distance_Matrix_Phase is active, THE Progress_Service SHALL emit Progress_Messages at intervals no greater than 2 seconds, each containing the phase identifier "distance_matrix" and the elapsed time in whole seconds since the phase began
3. WHEN the Distance_Matrix_Phase completes successfully, THE Progress_Service SHALL emit a Progress_Message indicating completion with the total elapsed duration expressed in whole seconds
4. IF the Distance_Matrix_Phase fails, THEN THE Progress_Service SHALL emit a Progress_Message indicating failure with the error description (maximum 500 characters) and the elapsed time in whole seconds at the point of failure
5. WHILE the Distance_Matrix_Phase is active, THE Progress_Service SHALL NOT emit any solver-progress or step-advance messages, so that the user can distinguish the distance matrix retrieval wait from the optimisation computation

### Requirement 4: WebSocket Progress Message Format

**User Story:** As a frontend developer, I want a consistent and well-structured progress message format, so that I can render appropriate progress UI components.

#### Acceptance Criteria

1. WHILE an optimisation run is in progress, THE Progress_Service SHALL send progress updates via WebSocket messages with type field set to "solver_progress" at an interval of no less than once every 2 seconds per active phase, coexisting with the existing "step", "progress", "complete", and "error" message types without altering their format or delivery
2. THE Progress_Message SHALL include a phase field with value "distance_matrix" or "solver" to identify the active phase
3. THE Progress_Message SHALL include an elapsed_seconds field as a numeric value (integer, whole seconds since the current phase started, minimum value 0)
4. WHEN the phase is "solver", THE Progress_Message SHALL include: time_limit_seconds (integer, the solver's configured maximum duration in seconds), percentage_complete (numeric, 0 to 100 inclusive, rounded to one decimal place, calculated as elapsed_seconds divided by time_limit_seconds multiplied by 100), solutions_found (integer, count of feasible solutions discovered so far, minimum 0), and current_best_score (numeric, the Objective_Score of the best solution found so far, or null if solutions_found is 0)
5. WHEN the phase is "distance_matrix", THE Progress_Message SHALL include: total_pairs (integer, count of origin-destination pairs to be computed), pairs_completed (integer, count of origin-destination pairs for which travel time has been received, minimum 0, maximum equal to total_pairs), and status field with value "in_progress", "complete", or "failed"
6. IF the status field in a "distance_matrix" phase message transitions from "in_progress" to "complete" or "failed", THEN THE Progress_Service SHALL send exactly one final Progress_Message for that phase with the terminal status before emitting any "solver" phase messages

### Requirement 5: Non-Blocking Solver Execution

**User Story:** As a scheduling coordinator, I want the optimisation to remain responsive and emit progress updates during the solver search, so that the UI does not freeze or appear unresponsive.

#### Acceptance Criteria

1. THE Progress_Service SHALL execute the Solver in a background thread so that the main async event loop remains able to send and receive WebSocket messages with a response latency of no more than 200 milliseconds for any queued Progress_Message
2. WHILE the Solver is running in the background thread, THE Progress_Service SHALL emit at least one Progress_Message over the WebSocket connection every 2 seconds, where each message contains the current elapsed time and the latest Objective_Score if available
3. WHEN the Solver completes in the background thread, THE Progress_Service SHALL signal completion to the main event loop within 500 milliseconds by sending a completion message containing the final Objective_Score and the computed Routes
4. IF the WebSocket_Client disconnects during the Solver_Phase, THEN THE Progress_Service SHALL stop emitting Progress_Messages and allow the solver background processing to terminate within 5 seconds (bounded by the solver's configured time_limit), after which no further resources are held for that session
5. IF the Solver raises an exception in the background thread, THEN THE Progress_Service SHALL send an error message over the WebSocket within 500 milliseconds indicating the step at which the failure occurred and a description of the failure, and SHALL release the background thread resources

### Requirement 6: Backward-Compatible Progress Emission

**User Story:** As a frontend developer, I want the new fine-grained progress to coexist with the existing step-based progress messages, so that existing UI components continue to function without modification.

#### Acceptance Criteria

1. THE Progress_Service SHALL continue to emit existing step-based messages (type "step" and type "progress") at each of the 8 defined pipeline steps (locations plotted, matrix retrieved, feasible assignments, constraint pruning, route evaluation, improvement iterations, winning solution, route animation), preserving the existing payload structure (field names, value types, and value semantics) without modification
2. THE Progress_Service SHALL emit "solver_progress" messages using a message type value distinct from "step", "progress", "complete", and "error", in addition to and not instead of existing progress messages, such that removal of all "solver_progress" messages from the stream produces a message sequence identical to the pre-existing protocol
3. WHEN a WebSocket_Client connects, THE Progress_Service SHALL send both existing step messages and new solver_progress messages on the same connection without requiring client opt-in or any change to the connection handshake
4. WHILE the Optimiser is running, THE Progress_Service SHALL emit existing "step" and "progress" messages with no additional latency introduced by solver_progress emission, such that existing messages arrive within 500 milliseconds of the pipeline event that triggers them regardless of solver_progress activity
5. IF emission of a solver_progress message fails, THEN THE Progress_Service SHALL continue emitting subsequent "step", "progress", and "solver_progress" messages without interruption and without altering the existing message stream

### Requirement 7: Time Limit Configuration Visibility

**User Story:** As a scheduling coordinator, I want to see the configured time limit for the solver so that I understand the expected maximum duration of optimisation.

#### Acceptance Criteria

1. WHEN the Optimiser begins the solver computation, THE Progress_Service SHALL include a time_limit_seconds field as a positive integer in the first Progress_Message emitted for the solver phase
2. THE time_limit_seconds value SHALL equal the Time_Limit parameter passed to the OR-Tools solver's search parameters for that optimisation run, expressed as a whole number of seconds in the range 1 to 3600
3. IF the Time_Limit value used by the Optimiser differs from the value reported in the previous optimisation run, THEN THE Progress_Service SHALL report the updated value in the first Progress_Message of the current run without requiring an application restart
4. IF the configured Time_Limit is outside the valid range of 1 to 3600 seconds, THEN THE Progress_Service SHALL report the value clamped to the nearest bound (1 or 3600) and include a warning indication in the Progress_Message
