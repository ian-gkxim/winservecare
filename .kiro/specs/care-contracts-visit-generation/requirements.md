# Requirements Document

## Introduction

The Care Contracts and Visit Generation feature replaces the static pre-seeded visits in the AI Care Operations Optimiser with a dynamic, contract-based model. Each patient receives a care contract defining their recurring care needs (frequency, time slots, required skills). The system generates visits dynamically for a selected date based on active contracts, provides a dedicated Visits page for managing the generated schedule, and feeds the generated visits into the existing route optimiser. This feature adds a "Contracts" configuration flow to the Patient edit experience and a new "Visits" navigation page, while integrating with the existing Dashboard optimisation workflow through a date-selection mechanism.

## Glossary

- **Care_Contract**: A persistent record attached to a Patient defining recurring care needs including visit frequency, time slots, required skills, and active date range
- **Visit_Slot**: A single slot definition within a Care_Contract specifying the label, time window (earliest and latest start), duration, and required skills for one visit occurrence per day
- **Visit_Frequency**: The recurrence pattern for a Care_Contract; one of: daily, weekdays_only, specific_days, alternate_days, or weekly
- **Generated_Visit**: A Visit record dynamically created from a Care_Contract and Visit_Slot for a specific target date
- **Target_Date**: The calendar date selected by the Administrator for which visits are generated and optimisation is run
- **Excluded_Date**: A specific date on which a Care_Contract does not generate visits (e.g., bank holidays, patient absences)
- **Visit_Generation_Engine**: The backend service that evaluates all active Care_Contracts against a Target_Date and produces Generated_Visits
- **Visits_Page**: The frontend screen displaying all Generated_Visits for the selected Target_Date with controls for generation, cancellation, and regeneration
- **Contract_Form**: The UI component within the Patient edit flow for creating and editing Care_Contract definitions
- **Administrator**: The single user of the system who manages contracts, generates visits, and triggers optimisation
- **Optimiser**: The existing backend service that computes optimal visit assignments and routes using OR-Tools

## Requirements

### Requirement 1: Care Contract Data Model

**User Story:** As an Administrator, I want to define a care contract for each patient specifying their recurring visit needs, so that visits can be generated automatically based on predictable care patterns.

#### Acceptance Criteria

1. THE Care_Contract SHALL store a visit_frequency field with one of the following values: daily, weekdays_only, specific_days, alternate_days, or weekly
2. WHEN visit_frequency is set to specific_days, THE Care_Contract SHALL store a days_of_week field containing one or more values from the set: mon, tue, wed, thu, fri, sat, sun
3. THE Care_Contract SHALL store a visits_per_day field with an integer value between 1 and 4 inclusive
4. THE Care_Contract SHALL store a visit_slots array containing between 1 and 4 Visit_Slot definitions, where each Visit_Slot includes a label (text, 1–100 characters), earliest_start (HH:MM format, between 06:00 and 22:00), latest_start (HH:MM format, greater than earliest_start for the same slot), duration_minutes (integer, 15–120), and required_skills (array of zero or more skill names)
5. THE Care_Contract SHALL store a start_date field (calendar date) indicating when the contract becomes active
6. THE Care_Contract SHALL store an end_date field that is either null (indicating an ongoing contract) or a calendar date that is equal to or later than start_date
7. THE Care_Contract SHALL store an excluded_dates field containing zero or more calendar dates on which visits are not generated
8. THE Care_Contract SHALL enforce that the count of Visit_Slot definitions equals the visits_per_day value

### Requirement 2: Visit Generation Logic

**User Story:** As an Administrator, I want the system to generate visits for a selected date based on patient contracts, so that the daily schedule is built automatically without manual entry.

#### Acceptance Criteria

1. WHEN the Administrator requests visit generation for a Target_Date, THE Visit_Generation_Engine SHALL evaluate each Care_Contract in the system to determine eligibility for that date
2. THE Visit_Generation_Engine SHALL determine a Care_Contract is eligible for the Target_Date only when all of the following conditions are met: the Target_Date is on or after the contract start_date, the Target_Date is on or before the contract end_date (or end_date is null), and the Target_Date is not in the contract excluded_dates list
3. WHEN visit_frequency is daily, THE Visit_Generation_Engine SHALL consider the contract eligible for every calendar date that passes the active-date and excluded-date checks
4. WHEN visit_frequency is weekdays_only, THE Visit_Generation_Engine SHALL consider the contract eligible only for dates falling on Monday through Friday
5. WHEN visit_frequency is specific_days, THE Visit_Generation_Engine SHALL consider the contract eligible only for dates whose day-of-week appears in the contract days_of_week field
6. WHEN visit_frequency is alternate_days, THE Visit_Generation_Engine SHALL consider the contract eligible only for dates where the number of days between start_date and the Target_Date is an even number (including zero)
7. WHEN visit_frequency is weekly, THE Visit_Generation_Engine SHALL consider the contract eligible only for dates where the Target_Date falls on the same day-of-week as the contract start_date
8. WHEN a Care_Contract is eligible for the Target_Date, THE Visit_Generation_Engine SHALL create one Generated_Visit for each Visit_Slot in the contract, setting patient_id, duration_minutes, window_start (from earliest_start), window_end (from latest_start), and required_skills from the Visit_Slot definition
9. IF no Care_Contracts are eligible for the Target_Date, THEN THE Visit_Generation_Engine SHALL return an empty set of visits and display a message indicating no visits are scheduled for the selected date

### Requirement 3: Target Date Selection and Validation

**User Story:** As an Administrator, I want to select a target date for visit generation with sensible defaults and validation, so that I always work with a valid future or present schedule.

#### Acceptance Criteria

1. THE Visits_Page SHALL display a date picker that defaults to today if today is a weekday (Monday–Friday) or the next Monday if today is a Saturday or Sunday
2. WHEN the Administrator selects a Target_Date, THE system SHALL validate that the selected date is not in the past (earlier than today's date)
3. IF the Administrator selects a date in the past, THEN THE system SHALL reject the selection, retain the previous valid date, and display an error message indicating that past dates are not permitted
4. WHEN the Administrator changes the Target_Date via the date picker, THE system SHALL trigger visit generation for the newly selected date within 2 seconds
5. THE Dashboard SHALL display a date picker for selecting the Target_Date for optimisation, defaulting to the same value as the Visits_Page date picker

### Requirement 4: Visits Page Display and Management

**User Story:** As an Administrator, I want a dedicated Visits page showing the generated visits for the selected day with controls for managing them, so that I can review and adjust the daily schedule before optimisation.

#### Acceptance Criteria

1. THE system SHALL provide a Visits_Page accessible from the main navigation between "Patients" and "Skills" items
2. THE Visits_Page SHALL display a table of Generated_Visits for the selected Target_Date with columns: patient name, visit label, time window (earliest_start – latest_start), duration in minutes, required skills, and status (scheduled or cancelled)
3. WHEN the Administrator clicks the Cancel button for a Generated_Visit with status "scheduled", THE system SHALL update that visit's status to "cancelled" and THE Visits_Page SHALL reflect the updated status without requiring a page reload
4. WHEN the Administrator clicks the "Generate Visits" button, THE Visit_Generation_Engine SHALL generate visits for the currently selected Target_Date, replacing any previously generated visits for that date
5. WHEN the Administrator clicks the "Regenerate" button, THE system SHALL reset all cancelled visits for the Target_Date back to "scheduled" status and regenerate visits from the current contract definitions
6. IF no visits are generated for the selected Target_Date, THEN THE Visits_Page SHALL display a message indicating no visits are scheduled for the selected date
7. THE Visits_Page SHALL display the total count of scheduled visits and the total count of cancelled visits for the selected Target_Date

### Requirement 5: Contract Management UI

**User Story:** As an Administrator, I want to create and edit care contracts within the patient management flow, so that I can define and adjust recurring care needs for each patient.

#### Acceptance Criteria

1. THE system SHALL provide a Care_Contract configuration section within the Patient edit screen, displayed below the existing patient fields
2. THE Contract_Form SHALL provide a frequency selector with options: daily, weekdays_only, specific_days, alternate_days, and weekly
3. WHEN the Administrator selects specific_days as the frequency, THE Contract_Form SHALL display checkboxes for each day of the week (Monday through Sunday) and require at least one day to be selected
4. THE Contract_Form SHALL provide controls to add and remove Visit_Slot definitions, allowing between 1 and 4 slots
5. THE Contract_Form SHALL provide fields for each Visit_Slot: label (text input), earliest_start (time picker, 06:00–22:00), latest_start (time picker, must be after earliest_start), duration_minutes (number input, 15–120), and required_skills (multi-select from existing skills)
6. THE Contract_Form SHALL provide date fields for start_date (required) and end_date (optional)
7. THE Contract_Form SHALL provide an excluded_dates field allowing the Administrator to add and remove specific dates
8. WHEN the Administrator submits a valid Care_Contract, THE system SHALL persist the contract to the database and display a confirmation message
9. IF the Administrator submits a Care_Contract with invalid data (visits_per_day not matching slot count, earliest_start after latest_start, duration outside 15–120 range, or missing required fields), THEN THE system SHALL reject the submission, retain the form data, and display error messages indicating each validation failure
10. WHEN the Administrator opens the Patient edit screen for a patient with an existing Care_Contract, THE Contract_Form SHALL pre-populate all fields with the current contract values

### Requirement 6: Integration with Existing Optimiser

**User Story:** As an Administrator, I want the optimiser to operate on generated visits for the selected date, so that route optimisation reflects the actual daily schedule derived from contracts.

#### Acceptance Criteria

1. WHEN the Administrator triggers an optimisation run from the Dashboard, THE Optimiser SHALL use the Generated_Visits for the selected Target_Date as input, including only visits with status "scheduled"
2. THE Optimiser SHALL exclude Generated_Visits with status "cancelled" from the optimisation computation
3. WHEN no Generated_Visits with status "scheduled" exist for the selected Target_Date, THE system SHALL display a message indicating there are no visits to optimise and SHALL NOT start the optimisation run
4. WHEN the Administrator changes the Target_Date on the Dashboard, THE system SHALL generate visits for that date (if not already generated) before the optimisation can be triggered
5. THE Generated_Visits SHALL include all fields required by the existing Optimiser: patient_id, duration_minutes, window_start, window_end, required_skills, and is_cancelled status

### Requirement 7: Mock Data Seeding for Contracts

**User Story:** As an Administrator, I want the system to include realistic contract data for existing patients, so that I can demonstrate the visit generation feature immediately after setup.

#### Acceptance Criteria

1. THE system SHALL seed Care_Contracts for all 12 existing patients when the database is initialised
2. THE seeded contracts SHALL include at least 2 patients with daily frequency, at least 2 patients with weekdays_only frequency, at least 3 patients with specific_days frequency (each with different day combinations), at least 2 patients with alternate_days frequency, and at least 2 patients with weekly frequency
3. THE seeded contracts SHALL include varied visits_per_day values: at least 3 patients with 1 visit per day, at least 4 patients with 2 visits per day, at least 3 patients with 3 visits per day, and at least 2 patients with 4 visits per day
4. THE seeded Visit_Slots SHALL span across different times of day: at least 4 slots with earliest_start before 09:00 (morning), at least 4 slots with earliest_start between 11:00 and 14:00 (midday), and at least 4 slots with earliest_start after 16:00 (evening)
5. THE seeded contracts SHALL all have a start_date of 2025-01-01 and end_date of null (ongoing), with excluded_dates containing UK bank holidays for 2025
6. THE seeded Visit_Slots SHALL reference only skills that exist in the current skills table
7. WHEN the database already contains Care_Contract data on application start, THE system SHALL not overwrite existing contract data
