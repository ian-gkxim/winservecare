"""Mock data seed script for the AI Care Operations Optimiser.

Seeds the database with realistic UK-based mock data:
- 5 carers in the Bristol area with varied skills and working hours
- 12 patients with UK addresses and coordinates
- 20 visits exercising all 7 hard constraints
- 6 care competency skills
- 7 hard constraints pre-loaded and enabled

The seed is idempotent: only inserts data if the relevant tables are empty.
Includes at least one infeasible scenario (visit requiring a skill no carer has).
"""

import json

import aiosqlite

from backend.app.db.database import DB_DIR, DB_PATH

# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
SKILLS = [
    "personal_care",
    "medication",
    "mobility",
    "dementia_care",
    "wound_care",
    "nutrition",
]

# ---------------------------------------------------------------------------
# 7 Hard Constraints
# ---------------------------------------------------------------------------
CONSTRAINTS = [
    {
        "name": "skill_matching",
        "description": "Visits may only be assigned to carers who possess every required skill.",
    },
    {
        "name": "medication_competency",
        "description": "Medication visits may only be assigned to carers with the medication competency.",
    },
    {
        "name": "time_windows",
        "description": "Each visit must start and complete within its defined time window.",
    },
    {
        "name": "max_working_hours",
        "description": "A carer's total working time (visits + travel) must not exceed their maximum hours.",
    },
    {
        "name": "mandatory_breaks",
        "description": "Carers must take a break of at least minimum duration after their maximum continuous work period.",
    },
    {
        "name": "travel_feasibility",
        "description": "A visit cannot be assigned if the carer cannot physically travel from the previous location in time.",
    },
    {
        "name": "no_overlapping_visits",
        "description": "A carer cannot be assigned two visits whose scheduled times overlap.",
    },
]

# ---------------------------------------------------------------------------
# 5 Carers — Bristol area, varied skills, 6-10 max hours
# ---------------------------------------------------------------------------
CARERS = [
    {
        "name": "Sarah Thompson",
        "home_lat": 51.4545,
        "home_lng": -2.5879,
        "skills": json.dumps(["personal_care", "medication", "mobility"]),
        "max_working_hours": 8.0,
        "max_continuous_hours": 6.0,
        "min_break_minutes": 30,
    },
    {
        "name": "James Patel",
        "home_lat": 51.4416,
        "home_lng": -2.5630,
        "skills": json.dumps(["personal_care", "dementia_care", "nutrition"]),
        "max_working_hours": 10.0,
        "max_continuous_hours": 6.0,
        "min_break_minutes": 30,
    },
    {
        "name": "Emily Chen",
        "home_lat": 51.4700,
        "home_lng": -2.6100,
        "skills": json.dumps(["personal_care", "medication", "wound_care"]),
        "max_working_hours": 7.0,
        "max_continuous_hours": 5.0,
        "min_break_minutes": 30,
    },
    {
        "name": "David Williams",
        "home_lat": 51.4300,
        "home_lng": -2.5400,
        "skills": json.dumps(["personal_care", "mobility", "nutrition"]),
        "max_working_hours": 6.0,
        "max_continuous_hours": 6.0,
        "min_break_minutes": 30,
    },
    {
        "name": "Fatima Hassan",
        "home_lat": 51.4600,
        "home_lng": -2.5500,
        "skills": json.dumps(["personal_care", "medication", "dementia_care", "mobility"]),
        "max_working_hours": 9.0,
        "max_continuous_hours": 6.0,
        "min_break_minutes": 30,
    },
]

# ---------------------------------------------------------------------------
# 12 Patients — Bristol area, varied priorities and continuity scores
# ---------------------------------------------------------------------------
PATIENTS = [
    {
        "name": "Margaret Davies",
        "address": "14 Gloucester Road, Bristol BS7 8AE",
        "lat": 51.4650,
        "lng": -2.5900,
        "preferences": json.dumps(["female_carer"]),
        "priority": "high",
        "continuity_score": 85.0,
        "usual_carer_id": 1,
        "preferred_carer_id": 1,
    },
    {
        "name": "Arthur Robinson",
        "address": "27 Whiteladies Road, Bristol BS8 2LY",
        "lat": 51.4620,
        "lng": -2.6050,
        "preferences": json.dumps(["morning_visits"]),
        "priority": "high",
        "continuity_score": 72.0,
        "usual_carer_id": 5,
        "preferred_carer_id": 5,
    },
    {
        "name": "Dorothy Evans",
        "address": "8 Henleaze Road, Bristol BS9 4LQ",
        "lat": 51.4830,
        "lng": -2.6100,
        "preferences": json.dumps(["same_carer"]),
        "priority": "medium",
        "continuity_score": 60.0,
        "usual_carer_id": 3,
        "preferred_carer_id": 3,
    },
    {
        "name": "Harold Fisher",
        "address": "45 Bath Road, Bristol BS4 3EH",
        "lat": 51.4350,
        "lng": -2.5550,
        "preferences": json.dumps(["afternoon_visits"]),
        "priority": "medium",
        "continuity_score": 55.0,
        "usual_carer_id": 2,
        "preferred_carer_id": 2,
    },
    {
        "name": "Edith Price",
        "address": "3 Wells Road, Bristol BS4 2AJ",
        "lat": 51.4380,
        "lng": -2.5700,
        "preferences": json.dumps(["female_carer", "quiet_approach"]),
        "priority": "high",
        "continuity_score": 90.0,
        "usual_carer_id": 1,
        "preferred_carer_id": 3,
    },
    {
        "name": "George Mitchell",
        "address": "19 Stapleton Road, Bristol BS5 0QR",
        "lat": 51.4630,
        "lng": -2.5600,
        "preferences": json.dumps(["male_carer"]),
        "priority": "low",
        "continuity_score": 40.0,
        "usual_carer_id": 4,
        "preferred_carer_id": 4,
    },
    {
        "name": "Betty Ward",
        "address": "52 Filton Avenue, Bristol BS7 0AT",
        "lat": 51.4780,
        "lng": -2.5750,
        "preferences": json.dumps(["morning_visits"]),
        "priority": "medium",
        "continuity_score": 65.0,
        "usual_carer_id": 2,
        "preferred_carer_id": 5,
    },
    {
        "name": "Norman Clarke",
        "address": "7 Bedminster Parade, Bristol BS3 4HL",
        "lat": 51.4400,
        "lng": -2.5950,
        "preferences": json.dumps(["punctual"]),
        "priority": "low",
        "continuity_score": 30.0,
        "usual_carer_id": None,
        "preferred_carer_id": None,
    },
    {
        "name": "Iris Cooper",
        "address": "31 Southmead Road, Bristol BS10 5NB",
        "lat": 51.4920,
        "lng": -2.5950,
        "preferences": json.dumps(["same_carer", "female_carer"]),
        "priority": "high",
        "continuity_score": 78.0,
        "usual_carer_id": 5,
        "preferred_carer_id": 5,
    },
    {
        "name": "Albert Morris",
        "address": "16 Redland Road, Bristol BS6 6QT",
        "lat": 51.4700,
        "lng": -2.5980,
        "preferences": json.dumps(["no_preference"]),
        "priority": "medium",
        "continuity_score": 50.0,
        "usual_carer_id": 3,
        "preferred_carer_id": None,
    },
    {
        "name": "Gladys Turner",
        "address": "22 Cotham Hill, Bristol BS6 6LF",
        "lat": 51.4670,
        "lng": -2.6000,
        "preferences": json.dumps(["morning_visits"]),
        "priority": "low",
        "continuity_score": 35.0,
        "usual_carer_id": None,
        "preferred_carer_id": 2,
    },
    {
        "name": "Frederick Lewis",
        "address": "9 Horfield Common, Bristol BS7 0XJ",
        "lat": 51.4850,
        "lng": -2.5800,
        "preferences": json.dumps(["afternoon_visits"]),
        "priority": "medium",
        "continuity_score": 45.0,
        "usual_carer_id": 4,
        "preferred_carer_id": 4,
    },
]

# ---------------------------------------------------------------------------
# 20 Visits — exercising all 7 hard constraints
#
# Constraint coverage design:
#   - skill_matching: visits 1-3 require medication (only carers 1,3,5 have it)
#   - medication_competency: visits 1-3 require medication skill explicitly
#   - time_windows: all visits have defined windows; visit 18 has a very tight window
#   - max_working_hours: carer 4 has only 6 hours — many visits could overload
#   - mandatory_breaks: carer 2 has 10 hours max, could trigger break rule
#   - travel_feasibility: visit 19 has tight window after a distant prior visit
#   - no_overlapping_visits: visits 7,8,9 overlap in time window for same patient area
#   - INFEASIBLE: visit 20 requires "palliative_care" — a skill NO carer possesses
# ---------------------------------------------------------------------------
VISITS = [
    # Morning medication rounds (exercises skill_matching + medication_competency)
    {
        "patient_id": 1,
        "duration_minutes": 30,
        "window_start": "07:00",
        "window_end": "08:30",
        "required_skills": json.dumps(["personal_care", "medication"]),
        "preferred_time": "07:30",
    },
    {
        "patient_id": 2,
        "duration_minutes": 45,
        "window_start": "07:30",
        "window_end": "09:00",
        "required_skills": json.dumps(["medication", "dementia_care"]),
        "preferred_time": "08:00",
    },
    {
        "patient_id": 5,
        "duration_minutes": 30,
        "window_start": "08:00",
        "window_end": "09:30",
        "required_skills": json.dumps(["medication"]),
        "preferred_time": "08:30",
    },
    # Mid-morning personal care visits
    {
        "patient_id": 3,
        "duration_minutes": 45,
        "window_start": "09:00",
        "window_end": "10:30",
        "required_skills": json.dumps(["personal_care", "mobility"]),
        "preferred_time": "09:30",
    },
    {
        "patient_id": 6,
        "duration_minutes": 30,
        "window_start": "09:30",
        "window_end": "11:00",
        "required_skills": json.dumps(["personal_care"]),
        "preferred_time": None,
    },
    {
        "patient_id": 4,
        "duration_minutes": 60,
        "window_start": "09:00",
        "window_end": "11:00",
        "required_skills": json.dumps(["personal_care", "nutrition"]),
        "preferred_time": "09:30",
    },
    # Late morning — overlapping windows for constraint testing
    {
        "patient_id": 7,
        "duration_minutes": 30,
        "window_start": "10:30",
        "window_end": "11:30",
        "required_skills": json.dumps(["personal_care"]),
        "preferred_time": "10:45",
    },
    {
        "patient_id": 8,
        "duration_minutes": 45,
        "window_start": "10:30",
        "window_end": "12:00",
        "required_skills": json.dumps(["personal_care", "wound_care"]),
        "preferred_time": "11:00",
    },
    {
        "patient_id": 9,
        "duration_minutes": 30,
        "window_start": "10:30",
        "window_end": "11:30",
        "required_skills": json.dumps(["personal_care", "dementia_care"]),
        "preferred_time": "10:30",
    },
    # Lunchtime nutrition visits
    {
        "patient_id": 10,
        "duration_minutes": 30,
        "window_start": "12:00",
        "window_end": "13:00",
        "required_skills": json.dumps(["nutrition"]),
        "preferred_time": "12:15",
    },
    {
        "patient_id": 11,
        "duration_minutes": 30,
        "window_start": "12:00",
        "window_end": "13:30",
        "required_skills": json.dumps(["nutrition", "personal_care"]),
        "preferred_time": "12:30",
    },
    {
        "patient_id": 12,
        "duration_minutes": 45,
        "window_start": "12:30",
        "window_end": "14:00",
        "required_skills": json.dumps(["personal_care"]),
        "preferred_time": None,
    },
    # Afternoon medication and care
    {
        "patient_id": 1,
        "duration_minutes": 30,
        "window_start": "14:00",
        "window_end": "15:30",
        "required_skills": json.dumps(["medication"]),
        "preferred_time": "14:30",
    },
    {
        "patient_id": 5,
        "duration_minutes": 60,
        "window_start": "14:00",
        "window_end": "16:00",
        "required_skills": json.dumps(["personal_care", "wound_care"]),
        "preferred_time": "14:30",
    },
    {
        "patient_id": 9,
        "duration_minutes": 45,
        "window_start": "14:30",
        "window_end": "16:00",
        "required_skills": json.dumps(["dementia_care", "mobility"]),
        "preferred_time": "15:00",
    },
    # Late afternoon
    {
        "patient_id": 4,
        "duration_minutes": 30,
        "window_start": "16:00",
        "window_end": "17:30",
        "required_skills": json.dumps(["personal_care"]),
        "preferred_time": "16:30",
    },
    {
        "patient_id": 7,
        "duration_minutes": 45,
        "window_start": "16:00",
        "window_end": "18:00",
        "required_skills": json.dumps(["personal_care", "nutrition"]),
        "preferred_time": None,
    },
    # Tight time window visit — exercises time_windows constraint tightly
    {
        "patient_id": 2,
        "duration_minutes": 30,
        "window_start": "17:00",
        "window_end": "17:30",
        "required_skills": json.dumps(["medication", "dementia_care"]),
        "preferred_time": "17:00",
    },
    # Travel feasibility stress — far location with tight timing after prior visit
    # Southmead (patient 9, lat 51.492) → Bedminster (patient 8, lat 51.440) in 15 min window
    {
        "patient_id": 8,
        "duration_minutes": 15,
        "window_start": "18:00",
        "window_end": "18:30",
        "required_skills": json.dumps(["personal_care"]),
        "preferred_time": "18:00",
    },
    # INFEASIBLE VISIT — requires "palliative_care" which no carer possesses
    # This ensures at least one scenario demonstrates infeasibility
    {
        "patient_id": 3,
        "duration_minutes": 60,
        "window_start": "17:00",
        "window_end": "19:00",
        "required_skills": json.dumps(["palliative_care"]),
        "preferred_time": "17:30",
    },
]


async def seed_db() -> None:
    """Seed the database with mock data if tables are empty.

    This function is idempotent — it only seeds data when the respective
    tables have no existing rows. Safe to call on every application start.
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("PRAGMA foreign_keys=ON")

        # Check if data already exists (use carers as the canary table)
        cursor = await db.execute("SELECT COUNT(*) FROM carers")
        row = await cursor.fetchone()
        if row and row[0] > 0:
            # Data already seeded — preserve existing data
            pass
        else:
            # --- Skills ---
            for skill_name in SKILLS:
                await db.execute(
                    "INSERT INTO skills (name) VALUES (?)",
                    (skill_name,),
                )

            # --- Constraints ---
            for constraint in CONSTRAINTS:
                await db.execute(
                    "INSERT INTO constraints (name, description) VALUES (?, ?)",
                    (constraint["name"], constraint["description"]),
                )

            # --- Carers ---
            for carer in CARERS:
                await db.execute(
                    """INSERT INTO carers (name, home_lat, home_lng, skills, max_working_hours,
                       max_continuous_hours, min_break_minutes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        carer["name"],
                        carer["home_lat"],
                        carer["home_lng"],
                        carer["skills"],
                        carer["max_working_hours"],
                        carer["max_continuous_hours"],
                        carer["min_break_minutes"],
                    ),
                )

            # --- Patients ---
            for patient in PATIENTS:
                await db.execute(
                    """INSERT INTO patients (name, address, lat, lng, preferences, priority,
                       continuity_score, usual_carer_id, preferred_carer_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        patient["name"],
                        patient["address"],
                        patient["lat"],
                        patient["lng"],
                        patient["preferences"],
                        patient["priority"],
                        patient["continuity_score"],
                        patient["usual_carer_id"],
                        patient["preferred_carer_id"],
                    ),
                )

            # --- Visits ---
            for visit in VISITS:
                await db.execute(
                    """INSERT INTO visits (patient_id, duration_minutes, window_start, window_end,
                       required_skills, preferred_time)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        visit["patient_id"],
                        visit["duration_minutes"],
                        visit["window_start"],
                        visit["window_end"],
                        visit["required_skills"],
                        visit["preferred_time"],
                    ),
                )

            await db.commit()

    # Seed contracts (separate idempotent check)
    await seed_contracts()


# ---------------------------------------------------------------------------
# UK 2025 Bank Holidays (excluded dates for all contracts)
# ---------------------------------------------------------------------------
UK_BANK_HOLIDAYS_2025 = [
    "2025-01-01",
    "2025-04-18",
    "2025-04-21",
    "2025-05-05",
    "2025-05-26",
    "2025-08-25",
    "2025-12-25",
    "2025-12-26",
]

# ---------------------------------------------------------------------------
# Care Contracts — 12 patients with varied frequencies and visits_per_day
#
# Frequency distribution:
#   daily:         patients 1, 5 (high priority, medication needs)
#   weekdays_only: patients 2, 9 (regular weekday care)
#   specific_days: patients 3 (MWF), 7 (TuTh), 11 (MWThSa)
#   alternate_days: patients 4, 10
#   weekly:        patients 6, 8, 12
#
# Visits per day distribution:
#   1 visit/day:  patients 6, 8, 12
#   2 visits/day: patients 3, 4, 7, 10
#   3 visits/day: patients 1, 2, 11
#   4 visits/day: patients 5, 9
#
# Visit slot time coverage:
#   ≥4 morning slots (earliest_start before 09:00)
#   ≥4 midday slots (earliest_start 11:00–14:00)
#   ≥4 evening slots (earliest_start after 16:00)
# ---------------------------------------------------------------------------
CARE_CONTRACTS = [
    # Patient 1: daily, 3 visits/day — high priority medication
    {
        "patient_id": 1,
        "visit_frequency": "daily",
        "days_of_week": None,
        "visits_per_day": 3,
        "slots": [
            {
                "slot_index": 0,
                "label": "Morning medication",
                "earliest_start": "07:00",
                "latest_start": "08:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care", "medication"]),
            },
            {
                "slot_index": 1,
                "label": "Midday check",
                "earliest_start": "12:00",
                "latest_start": "13:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care"]),
            },
            {
                "slot_index": 2,
                "label": "Evening medication",
                "earliest_start": "17:00",
                "latest_start": "18:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["medication"]),
            },
        ],
    },
    # Patient 2: weekdays_only, 3 visits/day
    {
        "patient_id": 2,
        "visit_frequency": "weekdays_only",
        "days_of_week": None,
        "visits_per_day": 3,
        "slots": [
            {
                "slot_index": 0,
                "label": "Morning personal care",
                "earliest_start": "07:30",
                "latest_start": "08:30",
                "duration_minutes": 45,
                "required_skills": json.dumps(["personal_care", "dementia_care"]),
            },
            {
                "slot_index": 1,
                "label": "Lunchtime nutrition",
                "earliest_start": "12:00",
                "latest_start": "13:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["nutrition"]),
            },
            {
                "slot_index": 2,
                "label": "Evening medication",
                "earliest_start": "17:00",
                "latest_start": "18:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["medication", "dementia_care"]),
            },
        ],
    },
    # Patient 3: specific_days (MWF), 2 visits/day
    {
        "patient_id": 3,
        "visit_frequency": "specific_days",
        "days_of_week": json.dumps(["mon", "wed", "fri"]),
        "visits_per_day": 2,
        "slots": [
            {
                "slot_index": 0,
                "label": "Morning mobility session",
                "earliest_start": "08:30",
                "latest_start": "09:30",
                "duration_minutes": 45,
                "required_skills": json.dumps(["personal_care", "mobility"]),
            },
            {
                "slot_index": 1,
                "label": "Afternoon wound care",
                "earliest_start": "14:00",
                "latest_start": "15:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["wound_care"]),
            },
        ],
    },
    # Patient 4: alternate_days, 2 visits/day
    {
        "patient_id": 4,
        "visit_frequency": "alternate_days",
        "days_of_week": None,
        "visits_per_day": 2,
        "slots": [
            {
                "slot_index": 0,
                "label": "Morning nutrition",
                "earliest_start": "08:00",
                "latest_start": "09:00",
                "duration_minutes": 60,
                "required_skills": json.dumps(["personal_care", "nutrition"]),
            },
            {
                "slot_index": 1,
                "label": "Evening check-in",
                "earliest_start": "16:30",
                "latest_start": "17:30",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care"]),
            },
        ],
    },
    # Patient 5: daily, 4 visits/day — high priority
    {
        "patient_id": 5,
        "visit_frequency": "daily",
        "days_of_week": None,
        "visits_per_day": 4,
        "slots": [
            {
                "slot_index": 0,
                "label": "Early morning medication",
                "earliest_start": "07:00",
                "latest_start": "07:30",
                "duration_minutes": 30,
                "required_skills": json.dumps(["medication"]),
            },
            {
                "slot_index": 1,
                "label": "Mid-morning personal care",
                "earliest_start": "10:00",
                "latest_start": "11:00",
                "duration_minutes": 45,
                "required_skills": json.dumps(["personal_care", "wound_care"]),
            },
            {
                "slot_index": 2,
                "label": "Afternoon medication",
                "earliest_start": "13:00",
                "latest_start": "14:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["medication"]),
            },
            {
                "slot_index": 3,
                "label": "Evening personal care",
                "earliest_start": "18:00",
                "latest_start": "19:00",
                "duration_minutes": 45,
                "required_skills": json.dumps(["personal_care"]),
            },
        ],
    },
    # Patient 6: weekly, 1 visit/day
    {
        "patient_id": 6,
        "visit_frequency": "weekly",
        "days_of_week": None,
        "visits_per_day": 1,
        "slots": [
            {
                "slot_index": 0,
                "label": "Weekly check-up",
                "earliest_start": "11:00",
                "latest_start": "12:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care"]),
            },
        ],
    },
    # Patient 7: specific_days (TuTh), 2 visits/day
    {
        "patient_id": 7,
        "visit_frequency": "specific_days",
        "days_of_week": json.dumps(["tue", "thu"]),
        "visits_per_day": 2,
        "slots": [
            {
                "slot_index": 0,
                "label": "Morning personal care",
                "earliest_start": "08:00",
                "latest_start": "09:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care"]),
            },
            {
                "slot_index": 1,
                "label": "Afternoon nutrition support",
                "earliest_start": "16:00",
                "latest_start": "17:00",
                "duration_minutes": 45,
                "required_skills": json.dumps(["personal_care", "nutrition"]),
            },
        ],
    },
    # Patient 8: weekly, 1 visit/day
    {
        "patient_id": 8,
        "visit_frequency": "weekly",
        "days_of_week": None,
        "visits_per_day": 1,
        "slots": [
            {
                "slot_index": 0,
                "label": "Weekly wound check",
                "earliest_start": "11:00",
                "latest_start": "12:00",
                "duration_minutes": 45,
                "required_skills": json.dumps(["personal_care", "wound_care"]),
            },
        ],
    },
    # Patient 9: weekdays_only, 4 visits/day — high priority
    {
        "patient_id": 9,
        "visit_frequency": "weekdays_only",
        "days_of_week": None,
        "visits_per_day": 4,
        "slots": [
            {
                "slot_index": 0,
                "label": "Early morning care",
                "earliest_start": "06:30",
                "latest_start": "07:30",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care", "dementia_care"]),
            },
            {
                "slot_index": 1,
                "label": "Late morning mobility",
                "earliest_start": "11:00",
                "latest_start": "12:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["mobility"]),
            },
            {
                "slot_index": 2,
                "label": "Afternoon dementia support",
                "earliest_start": "14:30",
                "latest_start": "15:30",
                "duration_minutes": 45,
                "required_skills": json.dumps(["dementia_care", "mobility"]),
            },
            {
                "slot_index": 3,
                "label": "Evening settling",
                "earliest_start": "18:30",
                "latest_start": "19:30",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care", "dementia_care"]),
            },
        ],
    },
    # Patient 10: alternate_days, 2 visits/day
    {
        "patient_id": 10,
        "visit_frequency": "alternate_days",
        "days_of_week": None,
        "visits_per_day": 2,
        "slots": [
            {
                "slot_index": 0,
                "label": "Morning personal care",
                "earliest_start": "08:30",
                "latest_start": "09:30",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care"]),
            },
            {
                "slot_index": 1,
                "label": "Midday nutrition",
                "earliest_start": "12:30",
                "latest_start": "13:30",
                "duration_minutes": 30,
                "required_skills": json.dumps(["nutrition"]),
            },
        ],
    },
    # Patient 11: specific_days (MWThSa), 3 visits/day
    {
        "patient_id": 11,
        "visit_frequency": "specific_days",
        "days_of_week": json.dumps(["mon", "wed", "thu", "sat"]),
        "visits_per_day": 3,
        "slots": [
            {
                "slot_index": 0,
                "label": "Morning care",
                "earliest_start": "07:30",
                "latest_start": "08:30",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care"]),
            },
            {
                "slot_index": 1,
                "label": "Midday nutrition",
                "earliest_start": "12:00",
                "latest_start": "13:00",
                "duration_minutes": 30,
                "required_skills": json.dumps(["nutrition", "personal_care"]),
            },
            {
                "slot_index": 2,
                "label": "Evening personal care",
                "earliest_start": "17:30",
                "latest_start": "18:30",
                "duration_minutes": 30,
                "required_skills": json.dumps(["personal_care"]),
            },
        ],
    },
    # Patient 12: weekly, 1 visit/day
    {
        "patient_id": 12,
        "visit_frequency": "weekly",
        "days_of_week": None,
        "visits_per_day": 1,
        "slots": [
            {
                "slot_index": 0,
                "label": "Weekly check-in",
                "earliest_start": "13:00",
                "latest_start": "14:00",
                "duration_minutes": 45,
                "required_skills": json.dumps(["personal_care"]),
            },
        ],
    },
]


async def seed_contracts() -> None:
    """Seed care contracts for all 12 patients if not already present.

    This function is idempotent — it only inserts data when the
    care_contracts table has no existing rows.
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("PRAGMA foreign_keys=ON")

        # Idempotent check: skip if contracts already exist
        cursor = await db.execute("SELECT COUNT(*) FROM care_contracts")
        row = await cursor.fetchone()
        if row and row[0] > 0:
            return

        excluded_dates_json = json.dumps(UK_BANK_HOLIDAYS_2025)

        for contract in CARE_CONTRACTS:
            # Insert the contract
            cursor = await db.execute(
                """INSERT INTO care_contracts
                   (patient_id, visit_frequency, days_of_week, visits_per_day,
                    start_date, end_date, excluded_dates)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    contract["patient_id"],
                    contract["visit_frequency"],
                    contract["days_of_week"],
                    contract["visits_per_day"],
                    "2025-01-01",
                    None,
                    excluded_dates_json,
                ),
            )
            contract_id = cursor.lastrowid

            # Insert visit slots for this contract
            for slot in contract["slots"]:
                await db.execute(
                    """INSERT INTO visit_slots
                       (contract_id, slot_index, label, earliest_start,
                        latest_start, duration_minutes, required_skills)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        contract_id,
                        slot["slot_index"],
                        slot["label"],
                        slot["earliest_start"],
                        slot["latest_start"],
                        slot["duration_minutes"],
                        slot["required_skills"],
                    ),
                )

        await db.commit()
