# Requirements Document

## Introduction

The AI Care Operations Optimiser is an AI-native operations layer that augments existing domiciliary care rostering systems. The MVP delivers a single compelling capability: optimising daily care visit routes for a small fleet of carers while explaining the optimisation reasoning through an animated map visualisation. The system operates with mock data (5 carers, 20 visits) for a single operating day, managed by a single administrator without authentication.

## Glossary

- **Optimiser**: The backend service that computes optimal visit assignments and routes using Google OR-Tools Vehicle Routing Problem (VRP) solver
- **Carer**: A domiciliary care worker who travels between patient locations to deliver care visits
- **Patient**: A person receiving domiciliary care at their home address
- **Visit**: A scheduled care activity with a specific duration, time window, and required skill, assigned to a Carer at a Patient location
- **Route**: An ordered sequence of Visits assigned to a single Carer for the operating day, including travel segments between stops
- **Travel_Time_Matrix**: A matrix of travel durations between all location pairs, retrieved from the Google Maps Distance Matrix API
- **Hard_Constraint**: A rule that must never be violated in any valid solution (e.g., competency requirements, time windows)
- **Objective_Function**: A weighted combination of cost and quality factors that the Optimiser minimises or maximises to rank solutions
- **Continuity_Score**: A metric measuring how consistently the same Carer is assigned to a Patient over time
- **Dashboard**: The main screen displaying KPIs, the animated map, recommendations, and schedule comparisons
- **Animated_Map**: A Google Maps visualisation that steps through the optimisation process and animates final routes
- **KPI_Ribbon**: A horizontal strip of key performance indicators displayed at the top of the Dashboard
- **Schedule_Comparison**: A side-by-side view of the current schedule, proposed schedule, and calculated savings
- **Scenario**: A named optimisation run with a specific set of inputs (e.g., a cancellation scenario)
- **Administrator**: The single user of the system who triggers optimisation runs and views results
- **Mock_Data_Store**: A SQLite database pre-populated with fictional Carers, Patients, Visits, and constraints

## Requirements

### Requirement 1: Dashboard KPI Display

**User Story:** As an Administrator, I want to see key operational metrics at a glance on the Dashboard, so that I can understand the current state of the care schedule.

#### Acceptance Criteria

1. WHEN the Dashboard is loaded, THE KPI_Ribbon SHALL display the following metrics: Total Visits (integer count), Carers Available (integer count), Travel Hours (decimal to 1 place, in hours), Mileage (decimal to 1 place, in miles), Overtime (decimal to 1 place, in hours), and Continuity Score (percentage, 0–100%)
2. WHEN an optimisation run completes, THE KPI_Ribbon SHALL update all metric values within 2 seconds to reflect the proposed optimised schedule
3. THE KPI_Ribbon SHALL display each metric with a text label above or beside the numeric value, where integer metrics show whole numbers and decimal metrics show exactly one decimal place
4. IF metric data is unavailable when the Dashboard is loaded, THEN THE KPI_Ribbon SHALL display a placeholder indicator in place of the numeric value for each affected metric

### Requirement 2: Animated Optimisation Visualisation

**User Story:** As an Administrator, I want to watch the optimisation process unfold on an animated map, so that I can understand how the AI arrives at its solution without needing technical expertise.

#### Acceptance Criteria

1. WHEN the Administrator triggers an optimisation run, THE Animated_Map SHALL display Step 1 by plotting all Carer home locations and Patient locations on the map using distinct marker styles for Carers and Patients
2. WHEN Step 1 completes, THE Animated_Map SHALL display Step 2 by showing the Travel_Time_Matrix request to Google Maps and indicating the number of origin-destination pairs being calculated
3. WHEN Step 2 completes, THE Animated_Map SHALL display Step 3 by drawing a feasible assignment graph connecting Carers to eligible Visits with visible connecting lines between each Carer marker and their eligible Visit markers
4. WHEN Step 3 completes, THE Animated_Map SHALL display Step 4 by removing edges that violate Hard_Constraints and changing rejected assignment lines to a visually distinct colour with a strikethrough or fade-out animation before removal
5. WHEN Step 4 completes, THE Animated_Map SHALL display Step 5 by animating up to 10 alternative route evaluations, drawing each candidate route on the map one at a time before advancing
6. WHEN Step 5 completes, THE Animated_Map SHALL display Step 6 by showing iterative improvements to the Objective_Function score, displaying the numeric score value updating with each improvement iteration
7. WHEN Step 6 completes, THE Animated_Map SHALL display Step 7 by presenting the winning solution with final route assignments and the final Objective_Function score
8. WHEN Step 7 completes, THE Animated_Map SHALL display Step 8 by animating each Carer following their final Route one Carer at a time in sequence on the map
9. THE Animated_Map SHALL display a progress indicator showing the current step number (1–8), step name, and a visual marker distinguishing completed steps from remaining steps
10. THE Animated_Map SHALL allow the Administrator to pause and resume the animation at any step, and WHILE paused, THE Animated_Map SHALL retain all currently displayed map elements and the progress indicator in their last rendered state
11. THE Animated_Map SHALL auto-advance from one step to the next after a visible transition delay of between 1 and 3 seconds, without requiring manual intervention from the Administrator
12. IF the optimisation process fails or returns an error during any step, THEN THE Animated_Map SHALL halt the animation at the current step, display an error message indicating which step failed and the nature of the failure, and retain all previously rendered steps on the map

### Requirement 3: Route Optimisation Engine

**User Story:** As an Administrator, I want to run the route optimiser against the current schedule, so that I can find a more efficient set of routes that satisfy all constraints.

#### Acceptance Criteria

1. WHEN the Administrator triggers an optimisation run, THE Optimiser SHALL compute an assignment of Visits to Carers that minimises the Objective_Function value relative to the current schedule's Objective_Function value
2. WHEN the Administrator triggers an optimisation run with up to 5 Carers and 20 Visits, THE Optimiser SHALL complete the optimisation computation and return results within 10 seconds
3. WHILE computing an optimisation run, THE Optimiser SHALL respect all Hard_Constraints: required competency match between Visit and Carer, medication competency match between Visit and Carer, Visit start time within the defined time window (no earlier than window start and no later than window end), Carer total scheduled time not exceeding 10 hours per day, a minimum 30-minute break for any Carer working more than 6 consecutive hours, travel time between consecutive Visits not exceeding the available gap between them, and no overlapping Visit assignments to a single Carer
4. THE Objective_Function SHALL be a weighted sum that minimises total travel time, total mileage, and total overtime hours while maximising continuity of care (proportion of Visits assigned to the Patient's usual Carer), patient preference satisfaction (proportion of Visits assigned to a preferred Carer), workload balance (minimising the difference between the most-loaded and least-loaded Carer's scheduled hours), and visit punctuality (proportion of Visits starting within 15 minutes of the preferred time)
5. WHEN the Optimiser completes successfully, THE Optimiser SHALL produce a set of Routes where each Route contains the ordered sequence of Visits for a single Carer, the calculated travel time between each consecutive Visit pair, the total mileage for the Route, and the total cost for the Route
6. IF the Optimiser cannot find a feasible solution satisfying all Hard_Constraints, THEN THE Optimiser SHALL return a response identifying each unsatisfiable constraint, the specific Visits and Carers involved in the conflict, and a reason indicating why the constraint could not be met
7. IF the Google Maps Distance Matrix API is unavailable or returns an error during an optimisation run, THEN THE Optimiser SHALL abort the computation and return an error indication stating that travel time data could not be retrieved

### Requirement 4: Hard Constraint Enforcement

**User Story:** As an Administrator, I want the optimiser to never violate mandatory rules, so that patient safety and legal requirements are always met.

#### Acceptance Criteria

1. THE Optimiser SHALL assign a Visit only to a Carer who possesses every skill listed in that Visit's required skill field
2. THE Optimiser SHALL assign medication-related Visits only to a Carer who holds the medication competency skill, where a Visit is classified as medication-related if its required skill includes medication competency
3. THE Optimiser SHALL schedule each Visit so that the Visit start time falls within the Patient's specified time window and the Visit completes (start time plus duration) no later than the end of that time window
4. THE Optimiser SHALL not assign a Carer more total working hours than the Carer's defined maximum, where working hours includes the sum of all assigned Visit durations plus all travel times between consecutive Visits
5. THE Optimiser SHALL schedule mandatory breaks for each Carer such that a Carer does not work continuously for longer than the maximum continuous working period defined in the Carer's break rules, and each break lasts at least the minimum break duration defined in the Carer's break rules
6. THE Optimiser SHALL not assign a Visit to a Carer when the travel time from the Carer's previous Visit location (or home location if first Visit) means the Carer cannot arrive before the end of the Visit's time window
7. THE Optimiser SHALL not assign two Visits to the same Carer whose scheduled time periods (start time to start time plus duration) overlap in any part
8. IF no feasible assignment exists for a Visit that satisfies all Hard_Constraints, THEN THE Optimiser SHALL leave that Visit unassigned and include it in the infeasibility explanation returned to the Administrator

### Requirement 5: Schedule Comparison

**User Story:** As an Administrator, I want to compare the current schedule with the optimised proposal side by side, so that I can clearly see the improvements and savings.

#### Acceptance Criteria

1. WHEN an optimisation run completes, THE Dashboard SHALL display the current schedule and proposed schedule in a side-by-side comparison view, showing each Carer's assigned Visits in chronological order
2. THE Schedule_Comparison SHALL show the savings between the current and proposed schedules in terms of travel hours, mileage, and overtime, displaying both absolute differences and percentage reductions
3. THE Schedule_Comparison SHALL visually highlight Visits that changed Carer assignment between the current and proposed schedules using a distinct colour or indicator
4. THE Schedule_Comparison SHALL display a total cost difference between the two schedules, where cost is calculated as the sum of travel hours cost, mileage cost, and overtime cost

### Requirement 6: Cancellation Scenario Re-optimisation

**User Story:** As an Administrator, I want to simulate a visit cancellation and re-run the optimiser, so that I can see how the schedule adapts to unexpected changes.

#### Acceptance Criteria

1. WHEN the Administrator removes a Visit from the schedule, THE system SHALL automatically trigger the Optimiser to re-compute the optimised Routes for the remaining Visits
2. WHEN re-optimisation completes after a cancellation, THE Dashboard SHALL display updated KPI values for Total Visits, Carers Available, Travel Hours, Mileage, Overtime, and Continuity Score reflecting the reduced Visit count
3. WHEN re-optimisation completes after a cancellation, THE Animated_Map SHALL replay the optimisation steps for the revised schedule
4. WHEN a single Visit is cancelled, THE Optimiser SHALL complete re-optimisation within 10 seconds
5. WHEN re-optimisation completes after a cancellation, THE Schedule_Comparison SHALL display the pre-cancellation schedule alongside the new optimised schedule

### Requirement 7: Mock Data Management

**User Story:** As an Administrator, I want the system pre-loaded with realistic mock data, so that I can demonstrate optimisation capabilities without connecting to live systems.

#### Acceptance Criteria

1. THE Mock_Data_Store SHALL contain data for 5 Carers, each with a name, home location (latitude and longitude within a UK geographic area), set of at least 2 skills, maximum working hours between 6 and 10 hours, and break rules specifying maximum continuous work period and minimum break duration
2. THE Mock_Data_Store SHALL contain data for 20 Visits, each with a duration between 15 and 90 minutes, a time window of at least the Visit duration in length, at least one required skill, and an assigned Patient
3. THE Mock_Data_Store SHALL contain data for at least 10 Patients, each with a valid UK address, at least one care preference, a priority level of low, medium, or high, and a Continuity_Score between 0 and 100
4. THE Mock_Data_Store SHALL be initialised automatically on first application start without manual intervention, and on subsequent starts THE system SHALL use the existing data without overwriting any Administrator edits
5. WHEN the application starts, THE system SHALL load all mock data from the Mock_Data_Store into memory for use by the Optimiser within the 30-second startup window
6. THE mock data SHALL include at least one scenario that exercises each of the 7 Hard_Constraints to verify they are enforceable

### Requirement 8: Google Maps Integration

**User Story:** As an Administrator, I want the system to use real-world travel data from Google Maps, so that route optimisation is based on accurate distances and travel times.

#### Acceptance Criteria

1. WHEN the Optimiser runs, THE system SHALL request a Travel_Time_Matrix from the Google Maps Distance Matrix API for all Carer and Patient locations using the driving travel mode, with a request timeout of 30 seconds per API call
2. THE Animated_Map SHALL render using the Google Maps JavaScript API with interactive pan and zoom controls
3. THE Animated_Map SHALL display Carer Routes as polylines on the Google Maps base layer
4. IF the Google Maps API returns an error or the request times out after 30 seconds, THEN THE system SHALL display an error message indicating the nature of the failure to the Administrator and halt the optimisation run
5. IF the Google Maps Distance Matrix API returns a result where one or more origin-destination pairs have no valid travel time, THEN THE system SHALL halt the optimisation run and display an error message identifying which location pairs could not be resolved

### Requirement 9: Recommendations and Warnings

**User Story:** As an Administrator, I want to see AI-generated recommendations and warnings, so that I can understand potential issues and improvement opportunities.

#### Acceptance Criteria

1. WHEN an optimisation run completes, THE Dashboard SHALL display a list of recommendations in the right panel, showing up to 10 recommendations ordered by impact
2. WHEN a Carer's scheduled working hours reach 80% or more of their maximum, THE Dashboard SHALL display a warning in the right panel indicating the Carer is approaching the working hours limit
3. WHEN a Visit's scheduled start time is within 15 minutes of the edge of its time window, THE Dashboard SHALL display a warning indicating the Visit has limited schedule flexibility
4. THE Dashboard SHALL display each recommendation with a title and a description of no more than 200 characters explaining the reasoning
5. THE Dashboard SHALL visually distinguish warnings from recommendations using different colour or icon styling

### Requirement 10: Scenario Comparison

**User Story:** As an Administrator, I want to compare multiple optimisation scenarios side by side, so that I can evaluate the impact of different decisions.

#### Acceptance Criteria

1. WHEN the Administrator saves an optimisation result, THE system SHALL prompt for a Scenario name between 1 and 100 characters and store the result including total travel hours, total mileage, total overtime hours, Continuity_Score, and all Visit-to-Carer assignments as a named Scenario in SQLite
2. IF the Administrator enters a Scenario name that already exists, THEN THE system SHALL display an error message indicating the name is taken and allow the Administrator to enter a different name without losing the optimisation result
3. WHEN the Administrator selects two Scenarios from the stored list, THE system SHALL display a side-by-side comparison showing each Scenario's travel hours, mileage, overtime, and Continuity_Score with the absolute numeric difference for each metric
4. WHEN the comparison is displayed, THE system SHALL list all Visits where the assigned Carer differs between the two Scenarios, visually distinguishing them from Visits with identical assignments
5. IF fewer than two Scenarios are stored, THEN THE system SHALL disable the comparison action and display a message indicating that at least two saved Scenarios are required

### Requirement 11: Carer and Patient Management Screens

**User Story:** As an Administrator, I want to view and edit Carer and Patient details, so that I can adjust the mock data used in optimisation.

#### Acceptance Criteria

1. THE system SHALL provide a Carers screen listing all Carers in a table with columns for: name, home location, skills, maximum working hours, and break rules
2. THE system SHALL provide a Patients screen listing all Patients in a table with columns for: address, preferences, priority level, and Continuity_Score
3. WHEN the Administrator submits an edit to a Carer or Patient record, THE system SHALL validate the input and persist the change to the Mock_Data_Store within 2 seconds
4. IF the Administrator submits an edit with invalid data (empty required field, maximum working hours outside 1–24 range, or priority level outside the defined set), THEN THE system SHALL reject the change, retain the previous value, and display an error message indicating which field failed validation
5. WHEN the system successfully persists an edit to a Carer or Patient record, THE system SHALL display a confirmation message and THE system SHALL use the updated data in all subsequent optimisation runs
6. THE system SHALL display Continuity_Score on the Patients screen as a read-only value since it is computed from optimisation history

### Requirement 12: Skills and Constraints Configuration

**User Story:** As an Administrator, I want to manage skills and constraints, so that I can configure what rules the optimiser must follow.

#### Acceptance Criteria

1. THE system SHALL provide a Skills screen listing all care competencies stored in the Mock_Data_Store, displaying each skill's name and the count of Carers and Visits currently assigned to that skill
2. THE system SHALL provide a Constraints screen listing all 7 Hard_Constraints with their name, description, and status (enabled or disabled), with all constraints enabled by default
3. WHEN the Administrator disables a Hard_Constraint, THE Optimiser SHALL exclude that constraint from subsequent optimisation runs until the Administrator re-enables it
4. WHEN the Administrator enables a previously disabled Hard_Constraint, THE Optimiser SHALL enforce that constraint in subsequent optimisation runs
5. WHEN the Administrator adds a new skill by providing a unique name of 1 to 100 characters, THE system SHALL persist the skill to the Mock_Data_Store and make it available for assignment to Carers and Visits
6. IF the Administrator attempts to add a skill with a name that already exists or an empty name, THEN THE system SHALL reject the addition and display an error message indicating the validation failure
7. WHEN the Administrator changes a skill or constraint configuration, THE system SHALL persist the change to the Mock_Data_Store

### Requirement 13: Exception Handling Screen

**User Story:** As an Administrator, I want to view and manage exceptions that occur during optimisation, so that I can understand and resolve issues.

#### Acceptance Criteria

1. IF the Optimiser encounters an infeasible assignment during optimisation, THEN THE system SHALL log the exception with the timestamp of occurrence, a description of the conflict, the names of the conflicting constraints, and the affected Carer or Visit identifier
2. THE system SHALL provide an Exceptions screen listing all logged exceptions ordered by timestamp descending (most recent first), displaying for each entry: timestamp, description, affected Carer or Visit, and resolution status (unresolved or resolved)
3. WHEN the Administrator acknowledges an unresolved exception, THE system SHALL mark the exception as resolved and display the updated resolution status without requiring a page reload
4. IF the Administrator attempts to acknowledge an exception that is already resolved, THEN THE system SHALL display a message indicating the exception has already been resolved and take no further action
5. IF no exceptions have been logged, THEN THE system SHALL display the Exceptions screen with a message indicating no exceptions are recorded

### Requirement 14: Reports Screen

**User Story:** As an Administrator, I want to generate summary reports of optimisation results, so that I can share outcomes with stakeholders.

#### Acceptance Criteria

1. THE system SHALL provide a Reports screen with summary statistics from the most recent optimisation run, including total travel time saved, mileage saved, overtime reduced, Continuity_Score change, and number of Visits reassigned
2. THE Reports screen SHALL display metrics as before and after values with calculated differences shown as both absolute values and percentage changes
3. WHEN the Administrator requests a report, THE system SHALL present the report data in a print-friendly format that renders cleanly when the browser print function is invoked, with no navigation or interactive elements visible in the printed output
4. IF no optimisation run has been completed, THEN THE Reports screen SHALL display a message indicating that no optimisation results are available

### Requirement 15: Application Setup and Installation

**User Story:** As an Administrator, I want to install and start the prototype in minutes, so that I can begin demonstrating capabilities without complex setup.

#### Acceptance Criteria

1. THE system SHALL be installable using a single command that installs all dependencies for both the frontend and backend, completing within 5 minutes on a standard broadband connection (10 Mbps or greater)
2. THE system SHALL start both the FastAPI backend and React frontend with a single start command
3. WHEN the system starts, THE system SHALL be ready to accept optimisation requests within 30 seconds, indicated by the frontend loading without error when accessed in a browser
4. IF the install or start command fails, THEN THE system SHALL display an error message indicating the cause of failure in the terminal output
5. THE system SHALL provide a Configuration screen accessible from the frontend navigation for setting the Google Maps API key, persisting the key value across application restarts
6. IF the Google Maps API key field is submitted empty, THEN THE system SHALL display a validation message indicating that the key is required
7. THE system SHALL document the required runtime prerequisites (Node.js version, Python version) in a README file at the project root

### Requirement 16: Optimisation Progress Feedback

**User Story:** As an Administrator, I want to see real-time progress during optimisation, so that I know the system is working and how far along it is.

#### Acceptance Criteria

1. WHILE the Optimiser is running, THE Dashboard SHALL display a progress indicator in the right panel showing the current optimisation step number, step name, and total number of steps, consistent with the 8-step animation sequence defined in the Animated_Map
2. WHILE the Optimiser is running, THE Dashboard SHALL display the current Objective_Function score, updating at least once per second whenever the solver finds an improved intermediate solution
3. WHEN the Optimiser completes, THE Dashboard SHALL display a completion notification with the final Objective_Function score, and the notification SHALL remain visible until the Administrator dismisses it or navigates away from the Dashboard
4. IF the Optimiser fails or encounters an error during execution, THEN THE Dashboard SHALL replace the progress indicator with an error notification indicating the failure reason, and SHALL display the last known Objective_Function score if any intermediate solutions were found
