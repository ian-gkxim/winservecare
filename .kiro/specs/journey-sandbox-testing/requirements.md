# Requirements Document

## Introduction

The Journey Sandbox Testing feature provides an interactive testing page within the WinServeCare admin dashboard and a companion mobile-friendly carer simulation view. The sandbox page enables administrators to visually exercise the 11 journey lifecycle API endpoints (create plan, list plans, get plan, modify journey, delete plan, cancel journey, receive actuals, compare, history, date-range summary, and query/filter) without using external tools. The carer simulation panel allows testers (or real carers) to submit actual journey data, provide route quality feedback, and report journey status updates through a mobile-optimised interface. A real-time comparison view displays planned vs actual data side-by-side so administrators can validate the journey lifecycle logic interactively.

## Glossary

- **Sandbox_Page**: The admin dashboard page that provides a visual interface for exercising journey lifecycle API endpoints interactively
- **Carer_Simulation_Panel**: A mobile-friendly view (accessible as a sub-panel or separate responsive route) that allows testers or carers to submit actual journey data and feedback
- **Plan_Builder**: The visual form section of the Sandbox_Page used to create, view, modify, and delete journey plans
- **Comparison_View**: The real-time display section that shows planned journeys alongside actual journey data with calculated variances
- **Route_Feedback**: Qualitative feedback from carers about a completed journey segment, including a rating and optional comment
- **Feedback_Rating**: A simple quality indicator (thumbs up, thumbs down, or neutral) submitted by a carer for a completed journey
- **Administrator**: The operations user who accesses the Sandbox_Page to test journey lifecycle operations
- **Carer**: A care worker who uses the Carer_Simulation_Panel to submit actual journey data and route feedback
- **Journey_API**: The existing set of 11 FastAPI endpoints for journey lifecycle management (routes/journeys.py)
- **Operating_Day**: A specific calendar date for which journey plans are created and tracked

## Requirements

### Requirement 1: Sandbox Page Navigation and Layout

**User Story:** As an Administrator, I want to access a dedicated sandbox testing page from the admin dashboard navigation, so that I can interactively test journey lifecycle operations without leaving the application.

#### Acceptance Criteria

1. THE Sandbox_Page SHALL be accessible from the admin dashboard navigation sidebar with a labelled menu item "Journey Sandbox"
2. WHEN the Administrator navigates to the Sandbox_Page, THE Sandbox_Page SHALL display three distinct panel sections: Plan_Builder, Carer_Simulation_Panel, and Comparison_View, arranged in a responsive layout
3. THE Sandbox_Page SHALL render within 3 seconds on initial load and display an empty state for each panel with instructions on how to begin testing
4. WHEN the browser viewport width is 768 pixels or less, THE Sandbox_Page SHALL stack the three panels vertically in the order: Plan_Builder, Carer_Simulation_Panel, Comparison_View

### Requirement 2: Journey Plan Builder Operations

**User Story:** As an Administrator, I want to create, view, modify, and delete journey plans visually, so that I can exercise the plan lifecycle endpoints without writing API calls manually.

#### Acceptance Criteria

1. WHEN the Administrator fills in the plan creation form with an operating day and at least one journey entry (carer, origin, destination, departure time, arrival time, distance), THE Plan_Builder SHALL send a POST request to the Journey_API create plan endpoint and display the created plan with its assigned identifier and version number
2. WHEN the Administrator requests the list of journey plans, THE Plan_Builder SHALL retrieve all non-archived plans from the Journey_API and display them as a selectable list showing operating day, plan version, and creation reason for each entry
3. WHEN the Administrator selects a plan from the list, THE Plan_Builder SHALL retrieve the full plan details including all nested journeys and display them in a tabular format showing carer, origin label, destination label, departure, arrival, distance, and current status
4. WHEN the Administrator edits a journey field within a selected plan and submits the change, THE Plan_Builder SHALL send a PUT request to the Journey_API modify endpoint and display the updated plan version returned by the server
5. WHEN the Administrator clicks the delete action on a plan, THE Plan_Builder SHALL display a confirmation dialog; upon confirmation, THE Plan_Builder SHALL send a DELETE request to the Journey_API and remove the plan from the displayed list, showing the count of journeys removed
6. WHEN the Administrator clicks the cancel action on a specific journey, THE Plan_Builder SHALL send a POST request to the cancel endpoint and update the journey status to cancelled in the displayed plan
7. IF the Journey_API returns a validation or business logic error for any Plan_Builder operation, THEN THE Plan_Builder SHALL display the error message and details from the API response in a visible alert within the Plan_Builder panel without clearing the form data

### Requirement 3: Journey Creation Form Usability

**User Story:** As an Administrator, I want the plan creation form to pre-populate sensible defaults and validate inputs before submission, so that I can create test plans quickly and avoid common errors.

#### Acceptance Criteria

1. WHEN the Administrator opens the plan creation form, THE Plan_Builder SHALL pre-populate the operating day field with tomorrow's date and provide a default creation reason of "initial_creation"
2. THE Plan_Builder SHALL validate that the operating day is today or a future date before allowing form submission and SHALL display an inline validation error if the date is in the past
3. THE Plan_Builder SHALL validate that each journey entry has a planned arrival time strictly after its planned departure time before submission and SHALL display an inline error on the offending journey row if violated
4. THE Plan_Builder SHALL provide an "Add Journey" button that appends a new empty journey row to the form, and a "Remove" button on each row to delete that entry
5. WHEN a journey row carer field is focused, THE Plan_Builder SHALL provide a dropdown of available carers fetched from the existing carers API endpoint
6. THE Plan_Builder SHALL display a running count of journey entries in the form header (e.g., "3 journeys") to provide immediate visibility of form completeness

### Requirement 4: Carer Simulation Panel – Actual Journey Submission

**User Story:** As a Carer (or tester simulating a carer), I want to submit actual journey data through a mobile-friendly interface, so that the sandbox can test the actual journey reception and matching logic.

#### Acceptance Criteria

1. THE Carer_Simulation_Panel SHALL display a form for submitting actual journey data with fields: carer selection, operating day, actual departure time, actual arrival time, actual distance in miles, and an optional route coordinates input
2. WHEN the Carer submits the actual journey form with valid data, THE Carer_Simulation_Panel SHALL send a POST request to the Journey_API actual-journeys endpoint and display the response including the match status (matched or unmatched) and the matched journey identifier if applicable
3. THE Carer_Simulation_Panel SHALL pre-populate the operating day with today's date and the carer field with the first available carer to reduce form friction during testing
4. IF the Journey_API returns a validation error for the actual journey submission, THEN THE Carer_Simulation_Panel SHALL display each invalid field with its error message inline next to the corresponding form field
5. THE Carer_Simulation_Panel SHALL provide a "Quick Submit" mode that generates randomised actual journey data (departure within 30 minutes of now, arrival 15-60 minutes later, distance 1-20 miles) for rapid testing with a single button press
6. WHEN rendered on a viewport of 480 pixels or less, THE Carer_Simulation_Panel SHALL use a single-column layout with touch-friendly input controls (minimum 44x44 pixel tap targets)

### Requirement 5: Carer Route Feedback

**User Story:** As a Carer, I want to provide quick feedback on route quality after completing a journey, so that administrators can assess whether planned routes are practical.

#### Acceptance Criteria

1. WHEN the Carer has submitted an actual journey that matches a planned journey, THE Carer_Simulation_Panel SHALL display a feedback prompt with three rating options: thumbs up (good route), neutral, and thumbs down (poor route)
2. WHEN the Carer selects a Feedback_Rating, THE Carer_Simulation_Panel SHALL allow the Carer to add an optional comment of up to 300 characters describing their route experience
3. WHEN the Carer submits Route_Feedback, THE Carer_Simulation_Panel SHALL send the feedback (journey identifier, rating, comment, and UTC timestamp) to the Journey_API feedback endpoint and display a confirmation message
4. IF the Carer skips the feedback prompt without submitting, THEN THE Carer_Simulation_Panel SHALL dismiss the prompt and record no feedback for that journey
5. THE Carer_Simulation_Panel SHALL display a history of submitted feedback for the current session, showing journey identifier, rating icon, and truncated comment (first 50 characters)
6. WHEN the Carer submits a thumbs-down rating without a comment, THE Carer_Simulation_Panel SHALL display a soft prompt suggesting a comment to explain the issue, but SHALL allow submission without one

### Requirement 6: Real-Time Comparison View

**User Story:** As an Administrator, I want to see a live comparison of planned vs actual journey data, so that I can verify the matching and variance calculation logic in real time.

#### Acceptance Criteria

1. WHEN the Administrator selects an operating day in the Comparison_View, THE Comparison_View SHALL fetch the comparison data from the Journey_API comparison endpoint and display entries grouped by carer with planned and actual data side-by-side
2. THE Comparison_View SHALL display for each comparison entry: the carer name, planned departure and arrival, actual departure and arrival, departure variance in minutes (colour-coded: green for on-time or early, red for late), arrival variance, and distance variance
3. WHEN the Comparison_View contains entries with a match status of "unstarted", THE Comparison_View SHALL display those entries with a visual indicator (e.g., dashed border or muted colours) and the label "Not yet started"
4. WHEN the Comparison_View contains entries with a match status of "unplanned", THE Comparison_View SHALL display those entries with a distinct visual indicator (e.g., highlighted border) and the label "Unplanned journey"
5. THE Comparison_View SHALL provide a refresh button that re-fetches comparison data from the Journey_API without requiring a full page reload
6. WHEN the Administrator selects a specific plan version from a dropdown, THE Comparison_View SHALL request the comparison using that plan version and update the display accordingly
7. IF no comparison data exists for the selected operating day, THEN THE Comparison_View SHALL display a message indicating no data is available for that date

### Requirement 7: Journey Status Timeline

**User Story:** As an Administrator, I want to see the status history of individual journeys, so that I can verify state transitions are occurring correctly during sandbox testing.

#### Acceptance Criteria

1. WHEN the Administrator clicks on a journey entry in either the Plan_Builder or Comparison_View, THE Sandbox_Page SHALL display a status timeline showing all state transitions for that journey in chronological order
2. THE status timeline SHALL display for each transition: the previous status, the new status, the timestamp of the transition, and the trigger source (API call, actual data reception, or timeout)
3. WHEN a journey transitions state as a result of sandbox operations (e.g., receiving actuals triggers "planned" to "in_progress"), THE status timeline SHALL update within 5 seconds to reflect the new transition without requiring manual refresh
4. THE status timeline SHALL use colour-coded status badges: blue for planned, yellow for in_progress, green for completed, red for cancelled, orange for overdue, and grey for amended

### Requirement 8: Plan Version History Browser

**User Story:** As an Administrator, I want to browse the version history of plans for a given operating day, so that I can verify that modifications create new versions correctly.

#### Acceptance Criteria

1. WHEN the Administrator selects an operating day in the history browser, THE Sandbox_Page SHALL fetch all plan versions from the Journey_API history endpoint and display them as a vertical timeline ordered by creation timestamp
2. THE history browser SHALL display for each plan version: the version number, creation timestamp, creation reason (initial creation, manual amendment, or re-optimisation), and the count of journeys in that version
3. WHEN the Administrator selects a specific plan version in the history browser, THE Plan_Builder SHALL load that version's journeys for inspection without modifying any data
4. THE history browser SHALL visually highlight the latest (current) plan version and indicate archived versions with a distinct icon or label

### Requirement 9: Sandbox Data Isolation

**User Story:** As an Administrator, I want the sandbox to use real API endpoints against the existing database, so that I can validate actual system behaviour rather than mocked responses.

#### Acceptance Criteria

1. THE Sandbox_Page SHALL make requests to the same Journey_API endpoints used by the production dashboard, using the same base URL and authentication context
2. WHEN the Sandbox_Page loads, THE Sandbox_Page SHALL display a visible banner indicating "Sandbox Mode – operations affect the live database" so that the Administrator is aware operations are not isolated
3. THE Sandbox_Page SHALL provide a "Reset Test Data" button that deletes all journey plans for a user-specified operating day (with a confirmation dialog requiring the Administrator to type the operating day to confirm), enabling clean test runs
4. IF the reset operation encounters plans that cannot be deleted (active journeys), THEN THE Sandbox_Page SHALL display the error details from the Journey_API and list the blocking journey identifiers

### Requirement 10: Route Feedback API Endpoint

**User Story:** As a system developer, I want a backend endpoint to receive and store carer route feedback, so that the sandbox feedback feature has a server-side integration point.

#### Acceptance Criteria

1. WHEN the Carer_Simulation_Panel submits Route_Feedback, THE Journey_API SHALL accept a POST request at `/api/journey-feedback` containing: journey identifier, rating (thumbs_up, neutral, or thumbs_down), optional comment (maximum 300 characters), and submission timestamp in UTC
2. THE Journey_API SHALL validate that the journey identifier references an existing journey with a status of completed; IF the journey does not exist or is not completed, THEN THE Journey_API SHALL return a 422 error indicating the journey is not eligible for feedback
3. THE Journey_API SHALL persist the feedback record in a `journey_feedback` table with columns: id, journey_id, carer_id, rating, comment, submitted_at, and created_at
4. WHEN feedback is requested for a specific journey, THE Journey_API SHALL return the feedback record associated with that journey identifier via a GET request at `/api/journey-feedback/{journey_id}`
5. THE Journey_API SHALL allow only one feedback submission per journey per carer; IF a duplicate submission is received, THEN THE Journey_API SHALL return a 409 conflict error indicating feedback already exists for that journey

