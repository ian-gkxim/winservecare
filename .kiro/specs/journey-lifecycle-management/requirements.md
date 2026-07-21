# Requirements Document

## Introduction

The Journey Lifecycle Management feature provides a database management framework for tracking a day's set of carer journeys through their complete lifecycle. It enables the WinServeCare system to retain historical planned and actual routes, receive real-time actual job data, compare planned schedules against actual activity, and manage future journey plans. This builds upon the existing optimisation engine by adding temporal state management to routes and journeys, allowing operations staff to track what was planned versus what actually happened throughout a care day.

## Glossary

- **Journey**: A single planned or actual trip by a Carer between two locations (either between Visit locations or between a Carer's home and a Visit location), forming one segment of a Route
- **Journey_Plan**: The complete set of Journeys for all Carers for a specific operating day, as produced by the Optimiser or manually created by the Administrator
- **Actual_Journey**: A Journey record containing real-world data captured from the field, including actual departure time, arrival time, and route taken
- **Journey_Status**: The current lifecycle state of a Journey, one of: planned, in_progress, completed, cancelled, or amended
- **Operating_Day**: A specific calendar date for which Journey_Plans are created, tracked, and compared
- **Plan_Version**: A numbered revision of a Journey_Plan for a given Operating_Day, allowing historical tracking of plan changes
- **Variance**: The calculated difference between a planned Journey and the corresponding Actual_Journey, measured in time, distance, or both
- **Journey_Store**: The SQLite database tables that persist all Journey_Plans, Actual_Journeys, and their associated metadata
- **Administrator**: The operations user who creates, reviews, and amends Journey_Plans
- **Carer**: A domiciliary care worker who travels between patient locations to deliver care visits
- **Route**: An ordered sequence of Journeys assigned to a single Carer for an Operating_Day

## Requirements

### Requirement 1: Journey Plan Creation

**User Story:** As an Administrator, I want to create journey plans for future operating days, so that I can prepare carer schedules in advance.

#### Acceptance Criteria

1. WHEN the Administrator creates a new Journey_Plan for a specified Operating_Day, THE Journey_Store SHALL persist the plan with a unique identifier, the Operating_Day date, a Plan_Version number of 1, a creation timestamp, and the set of Journeys for each assigned Carer
2. WHEN the Optimiser produces a set of Routes for an Operating_Day, THE Journey_Store SHALL convert each Route into a set of Journeys ordered by planned departure time and persist them as a new Journey_Plan with all Journey_Status values set to planned
3. THE Journey_Store SHALL allow Journey_Plans to be created for any Operating_Day that is today or a future date within 365 days from today
4. IF the Administrator attempts to create a Journey_Plan for a past Operating_Day, THEN THE Journey_Store SHALL reject the creation and return an error indicating that plans cannot be created for past dates
5. WHEN a Journey_Plan is created, THE Journey_Store SHALL record each Journey with the assigned Carer identifier, origin location, destination location, planned departure time, planned arrival time, planned distance in miles, and associated Visit identifier (where applicable)
6. IF a Journey_Plan already exists for the specified Operating_Day, THEN THE Journey_Store SHALL create a new Plan_Version by incrementing the previous version number by 1 and persisting the new plan without deleting the prior version

### Requirement 2: Journey Plan Modification

**User Story:** As an Administrator, I want to update or amend journey plans that have not yet completed, so that I can adapt to changing circumstances.

#### Acceptance Criteria

1. WHEN the Administrator updates a Journey within a Journey_Plan, THE Journey_Store SHALL create a new Plan_Version containing the full amended plan and retain the previous Plan_Version unchanged
2. WHILE a Journey has a Journey_Status of planned, THE Journey_Store SHALL allow the Administrator to update the Journey's assigned Carer, departure time, arrival time, origin location, or destination location
3. WHILE a Journey has a Journey_Status of in_progress, THE Journey_Store SHALL allow the Administrator to update only the planned arrival time and destination location of that Journey
4. IF the Administrator attempts to modify a Journey with a Journey_Status of completed, THEN THE Journey_Store SHALL reject the modification and return an error indicating that completed Journeys cannot be amended
5. IF the Administrator attempts to modify a Journey with a Journey_Status of cancelled, THEN THE Journey_Store SHALL reject the modification and return an error indicating that cancelled Journeys cannot be amended
6. WHEN a Journey is modified, THE Journey_Store SHALL set the Journey_Status to amended for the original Journey in the previous Plan_Version and record the new Journey details in the current Plan_Version with a Journey_Status of planned

### Requirement 3: Journey Plan Deletion

**User Story:** As an Administrator, I want to delete future journey plans that are no longer needed, so that I can keep the system free of obsolete data.

#### Acceptance Criteria

1. WHEN the Administrator deletes a Journey_Plan for an Operating_Day that is strictly after today's date where no Journeys have a Journey_Status of in_progress or completed, THE Journey_Store SHALL remove the Journey_Plan and all associated Journeys so that they are no longer returned in standard list or search operations, and SHALL return a confirmation response including the deleted Journey_Plan identifier and the count of removed Journeys
2. IF the Administrator attempts to delete a Journey_Plan that contains one or more Journeys with a Journey_Status of in_progress or completed, THEN THE Journey_Store SHALL reject the deletion and return an error listing the Journey identifiers that cannot be deleted
3. WHEN a Journey_Plan is deleted, THE Journey_Store SHALL retain the deleted plan data in an archived state retrievable via archive-specific queries, marked with a deletion timestamp in UTC, and retained indefinitely until explicitly purged by an Administrator
4. IF the Administrator attempts to delete the only Journey_Plan for an Operating_Day that is today, THEN THE Journey_Store SHALL reject the deletion and return an error indicating that the active day plan cannot be deleted
5. IF the Administrator attempts to delete a Journey_Plan for an Operating_Day that is in the past, THEN THE Journey_Store SHALL reject the deletion and return an error indicating that past journey plans cannot be deleted
6. IF the Administrator attempts to delete a Journey_Plan using an identifier that does not exist in the Journey_Store, THEN THE Journey_Store SHALL return an error indicating that the specified Journey_Plan was not found

### Requirement 4: Actual Journey Data Reception

**User Story:** As an Administrator, I want the system to receive actual journey data from the field, so that I can track what carers are doing in real time.

#### Acceptance Criteria

1. WHEN actual job data is received for a Journey, THE Journey_Store SHALL create an Actual_Journey record containing the Carer identifier, actual departure time, actual arrival time, actual distance travelled in miles to 1 decimal place, and actual route coordinates as an ordered list of latitude/longitude pairs (maximum 1000 coordinate pairs per journey)
2. WHEN actual departure data is received for a planned Journey, THE Journey_Store SHALL update the corresponding Journey's Journey_Status from planned to in_progress
3. WHEN actual arrival data is received for an in_progress Journey, THE Journey_Store SHALL update the corresponding Journey's Journey_Status from in_progress to completed
4. IF actual job data is received for a Journey that has no matching planned Journey in the Journey_Store, THEN THE Journey_Store SHALL create a new unplanned Actual_Journey record with a status of unmatched and display the record in the Administrator's exception list for review
5. IF actual job data is received with a Carer identifier that does not match any Carer in the Mock_Data_Store, or with missing required fields (departure time or arrival time), or with an actual arrival time that is not later than the actual departure time, THEN THE Journey_Store SHALL reject the data and return a validation error identifying each missing or invalid field
6. WHEN actual job data is received, THE Journey_Store SHALL associate the Actual_Journey with the corresponding planned Journey using the Carer identifier, Operating_Day, and planned departure time window (within 60 minutes of planned departure); IF multiple planned Journeys match within the 60-minute window, THEN THE Journey_Store SHALL select the planned Journey with the closest planned departure time to the actual departure time
7. IF an Actual_Journey remains in in_progress status for longer than 4 hours after the actual departure time, THEN THE Journey_Store SHALL flag the journey as requiring Administrator review by updating its status to overdue

### Requirement 5: Plan vs Actual Comparison

**User Story:** As an Administrator, I want to compare planned journeys with actual activity, so that I can identify variances and improve future planning accuracy.

#### Acceptance Criteria

1. WHEN the Administrator requests a comparison for an Operating_Day, THE Journey_Store SHALL return each planned Journey from the latest Plan_Version for that Operating_Day paired with its corresponding Actual_Journey, including calculated Variance values for departure time, arrival time, and distance, with results grouped by Carer and ordered by planned departure time within each group
2. THE Journey_Store SHALL calculate departure time Variance as the difference in minutes between actual departure time and planned departure time, expressed as a signed integer (positive meaning late, negative meaning early)
3. THE Journey_Store SHALL calculate arrival time Variance as the difference in minutes between actual arrival time and planned arrival time, expressed as a signed integer (positive meaning late, negative meaning early)
4. THE Journey_Store SHALL calculate distance Variance as the difference between actual distance and planned distance, expressed as a signed value in miles to 1 decimal place (positive meaning longer route, negative meaning shorter route)
5. WHEN a comparison is requested, THE Journey_Store SHALL include Journeys that have no corresponding Actual_Journey (unstarted planned Journeys) and Actual_Journeys that have no corresponding planned Journey (unplanned Journeys), marking each entry with a match status of matched, unstarted, or unplanned, and returning null for all Variance values on unstarted and unplanned entries
6. IF no Journey_Plan or Actual_Journey data exists for the requested Operating_Day, THEN THE Journey_Store SHALL return an empty comparison result with a message indicating no data is available for that date
7. WHEN the Administrator requests a comparison for a specific Plan_Version of an Operating_Day, THE Journey_Store SHALL use the Journeys from that Plan_Version instead of the latest version for pairing and Variance calculation

### Requirement 6: Historical Plan Retention

**User Story:** As an Administrator, I want all plan versions and actual journey data retained historically, so that I can audit past schedules and track planning accuracy over time.

#### Acceptance Criteria

1. THE Journey_Store SHALL retain all Plan_Versions for every Operating_Day without overwriting previous versions, preserving for each version: the version number, creation timestamp, creation reason, and the full set of Journeys including each Journey's assigned Carer, assigned Visits in order, calculated travel times between consecutive Visits, total mileage, and total scheduled duration
2. THE Journey_Store SHALL retain all Actual_Journey records for a minimum of 365 days, associating each Actual_Journey with its Operating_Day and matched planned Journey where a match exists
3. WHEN the Administrator requests the history for an Operating_Day, THE Journey_Store SHALL return all Plan_Versions in chronological order within 5 seconds, including for each version: creation timestamp, version number, creation reason, and the set of Journeys contained in that version
4. THE Journey_Store SHALL record the reason for each Plan_Version creation as one of the following enumerated values: initial creation, manual amendment, or re-optimisation
5. WHEN the Administrator requests historical data for a date range of up to 90 days, THE Journey_Store SHALL return within 10 seconds a summary record for each Operating_Day in the range, including: the number of Plan_Versions, total planned Journeys, total completed Actual_Journeys, and average Variance per Journey
6. IF the Administrator requests historical data for a date range exceeding 90 days or where the start date is after the end date, THEN THE Journey_Store SHALL reject the request and return an error message indicating the date range constraint that was violated

### Requirement 7: Journey Cancellation

**User Story:** As an Administrator, I want to cancel individual journeys within a plan, so that I can handle situations where visits are no longer required.

#### Acceptance Criteria

1. WHEN the Administrator cancels a Journey with a Journey_Status of planned, THE Journey_Store SHALL update the Journey_Status to cancelled, record the cancellation timestamp in UTC ISO 8601 format, and return a confirmation response indicating the Journey was successfully cancelled
2. WHEN the Administrator cancels a Journey with a Journey_Status of in_progress, THE Journey_Store SHALL update the Journey_Status to cancelled, record the cancellation timestamp in UTC ISO 8601 format, and mark all incomplete Visits within the Journey as unassigned
3. IF the Administrator attempts to cancel a Journey with a Journey_Status of completed, THEN THE Journey_Store SHALL reject the cancellation and return an error indicating that completed Journeys cannot be cancelled
4. IF the Administrator attempts to cancel a Journey with a Journey_Status of cancelled, THEN THE Journey_Store SHALL reject the cancellation and return an error indicating that the Journey is already cancelled
5. IF the Administrator attempts to cancel a Journey that does not exist in the Journey_Store, THEN THE Journey_Store SHALL return an error indicating that the specified Journey could not be found
6. WHEN a Journey is cancelled, THE Journey_Store SHALL create a new Plan_Version that includes the Journey with its updated cancelled status and updated Visit assignments, while retaining the previous Plan_Version with the Journey and its Visits in their pre-cancellation state

### Requirement 8: Journey Query and Filtering

**User Story:** As an Administrator, I want to query journeys by date, carer, status, and other criteria, so that I can quickly find relevant journey information.

#### Acceptance Criteria

1. WHEN the Administrator queries Journeys by Operating_Day, THE Journey_Store SHALL return all Journeys for that date from the latest Plan_Version, including their current Journey_Status and associated Actual_Journey data where available
2. WHEN the Administrator queries Journeys by Carer identifier, THE Journey_Store SHALL return all Journeys assigned to that Carer across all Operating_Days using the latest Plan_Version for each Operating_Day, ordered by planned departure time descending
3. WHEN the Administrator queries Journeys by Journey_Status, THE Journey_Store SHALL return all Journeys matching the specified status across all Operating_Days using the latest Plan_Version for each Operating_Day
4. WHEN the Administrator queries Journeys with multiple filter criteria (Operating_Day, Carer identifier, and Journey_Status), THE Journey_Store SHALL return only Journeys that satisfy all specified criteria simultaneously, using the latest Plan_Version for the specified Operating_Day
5. THE Journey_Store SHALL support pagination of query results, accepting a page number (minimum 1) and page size parameter (minimum 1, maximum 100, default 20), and returning the total count of matching records alongside the requested page of results
6. IF the Administrator submits a query with an invalid filter value (a non-existent Carer identifier, a Journey_Status not in the defined set of planned, in_progress, completed, cancelled, or amended, or an Operating_Day that is not a valid calendar date), THEN THE Journey_Store SHALL reject the query and return an error indicating which filter parameter is invalid
7. IF a query matches zero Journeys, THEN THE Journey_Store SHALL return an empty result set with a total count of 0 and an empty list of Journeys
