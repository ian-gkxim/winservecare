-- AI Care Operations Optimiser - Database Schema
-- SQLite database for mock data persistence

CREATE TABLE IF NOT EXISTS carers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    home_lat REAL NOT NULL,
    home_lng REAL NOT NULL,
    skills TEXT NOT NULL,  -- JSON array of skill names
    max_working_hours REAL NOT NULL CHECK(max_working_hours >= 1 AND max_working_hours <= 24),
    max_continuous_hours REAL NOT NULL DEFAULT 6.0,
    min_break_minutes INTEGER NOT NULL DEFAULT 30,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    preferences TEXT NOT NULL DEFAULT '[]',  -- JSON array
    priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
    continuity_score REAL NOT NULL DEFAULT 0.0 CHECK(continuity_score >= 0 AND continuity_score <= 100),
    usual_carer_id INTEGER REFERENCES carers(id),
    preferred_carer_id INTEGER REFERENCES carers(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    duration_minutes INTEGER NOT NULL CHECK(duration_minutes >= 15 AND duration_minutes <= 120),
    window_start TEXT NOT NULL,  -- HH:MM format
    window_end TEXT NOT NULL,    -- HH:MM format
    required_skills TEXT NOT NULL DEFAULT '[]',  -- JSON array of skill names
    preferred_time TEXT,  -- HH:MM format, nullable
    is_cancelled INTEGER NOT NULL DEFAULT 0,
    target_date TEXT,  -- YYYY-MM-DD, NULL for legacy pre-seeded visits
    contract_id INTEGER REFERENCES care_contracts(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS constraints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE CHECK(length(name) >= 1 AND length(name) <= 100),
    total_travel_hours REAL NOT NULL,
    total_mileage REAL NOT NULL,
    total_overtime_hours REAL NOT NULL,
    continuity_score REAL NOT NULL,
    objective_score REAL NOT NULL,
    assignments TEXT NOT NULL,  -- JSON: [{visit_id, carer_id, start_time, travel_time, mileage}]
    routes TEXT NOT NULL,       -- JSON: full route data per carer
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL,
    constraint_names TEXT NOT NULL,  -- JSON array
    affected_entity_type TEXT NOT NULL CHECK(affected_entity_type IN ('carer', 'visit')),
    affected_entity_id INTEGER NOT NULL,
    is_resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Journey Lifecycle Management tables

CREATE TABLE IF NOT EXISTS journey_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operating_day TEXT NOT NULL,           -- YYYY-MM-DD
    plan_version INTEGER NOT NULL DEFAULT 1,
    creation_reason TEXT NOT NULL CHECK(creation_reason IN ('initial_creation', 'manual_amendment', 're_optimisation')),
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,                       -- UTC ISO 8601
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(operating_day, plan_version)
);

CREATE TABLE IF NOT EXISTS journeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES journey_plans(id),
    carer_id INTEGER NOT NULL REFERENCES carers(id),
    visit_id INTEGER REFERENCES visits(id),  -- NULL for home-to-first and last-to-home legs
    origin_lat REAL NOT NULL,
    origin_lng REAL NOT NULL,
    origin_label TEXT,                       -- Human-readable origin name
    destination_lat REAL NOT NULL,
    destination_lng REAL NOT NULL,
    destination_label TEXT,                  -- Human-readable destination name
    planned_departure TEXT NOT NULL,          -- ISO 8601 datetime
    planned_arrival TEXT NOT NULL,            -- ISO 8601 datetime
    planned_distance_miles REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned', 'in_progress', 'completed', 'cancelled', 'amended', 'overdue')),
    cancelled_at TEXT,                       -- UTC ISO 8601
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS actual_journeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER REFERENCES journeys(id),  -- NULL for unmatched
    carer_id INTEGER NOT NULL REFERENCES carers(id),
    operating_day TEXT NOT NULL,              -- YYYY-MM-DD
    actual_departure TEXT NOT NULL,           -- ISO 8601 datetime
    actual_arrival TEXT NOT NULL,             -- ISO 8601 datetime
    actual_distance_miles REAL NOT NULL,      -- 1 decimal place
    route_coordinates TEXT NOT NULL DEFAULT '[]',  -- JSON array of [lat, lng] pairs, max 1000
    match_status TEXT NOT NULL DEFAULT 'matched' CHECK(match_status IN ('matched', 'unmatched')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_journey_plans_operating_day ON journey_plans(operating_day);
CREATE INDEX IF NOT EXISTS idx_journeys_plan_id ON journeys(plan_id);
CREATE INDEX IF NOT EXISTS idx_journeys_carer_id ON journeys(carer_id);
CREATE INDEX IF NOT EXISTS idx_journeys_status ON journeys(status);
CREATE INDEX IF NOT EXISTS idx_actual_journeys_operating_day ON actual_journeys(operating_day);
CREATE INDEX IF NOT EXISTS idx_actual_journeys_carer_id ON actual_journeys(carer_id);

-- Carer Mobile App tables

-- Carer authentication and device management
CREATE TABLE IF NOT EXISTS carer_auth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carer_id INTEGER NOT NULL REFERENCES carers(id),
    password_hash TEXT NOT NULL,
    refresh_token TEXT,
    refresh_token_expires_at TEXT,
    device_token TEXT,
    device_platform TEXT CHECK(device_platform IN ('ios', 'android')),
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    lockout_until TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- GPS signals from mobile app
CREATE TABLE IF NOT EXISTS gps_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carer_id INTEGER NOT NULL REFERENCES carers(id),
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    accuracy_metres REAL NOT NULL,
    low_accuracy INTEGER NOT NULL DEFAULT 0,
    captured_at TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    visit_id INTEGER REFERENCES visits(id),
    geofence_state TEXT CHECK(geofence_state IN ('inside', 'near', 'outside'))
);

-- Contextual questions sent to carers
CREATE TABLE IF NOT EXISTS contextual_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carer_id INTEGER NOT NULL REFERENCES carers(id),
    visit_id INTEGER NOT NULL REFERENCES visits(id),
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL CHECK(question_type IN ('yes_no', 'single_choice', 'free_text')),
    options TEXT,
    status TEXT NOT NULL DEFAULT 'sent' CHECK(status IN ('sent', 'answered', 'timed_out', 'suppressed')),
    response_text TEXT,
    responded_at TEXT,
    timed_out_at TEXT,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Proactive inputs from carers
CREATE TABLE IF NOT EXISTS proactive_inputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carer_id INTEGER NOT NULL REFERENCES carers(id),
    visit_id INTEGER NOT NULL REFERENCES visits(id),
    input_type TEXT NOT NULL CHECK(input_type IN (
        'arrived', 'visit_started', 'visit_completed',
        'running_late', 'issue_encountered', 'cannot_complete'
    )),
    note TEXT,
    latitude REAL,
    longitude REAL,
    location_unavailable INTEGER NOT NULL DEFAULT 0,
    captured_at TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Visit status tracking with full audit trail
CREATE TABLE IF NOT EXISTS visit_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id INTEGER NOT NULL REFERENCES visits(id),
    carer_id INTEGER NOT NULL REFERENCES carers(id),
    status TEXT NOT NULL CHECK(status IN (
        'pending', 'travelling', 'arrived', 'in_progress',
        'completed', 'delayed', 'missed', 'cancelled'
    )),
    confidence_score INTEGER NOT NULL CHECK(confidence_score >= 0 AND confidence_score <= 100),
    inferred_by TEXT NOT NULL CHECK(inferred_by IN ('gps', 'question', 'proactive', 'timeout', 'system')),
    is_current INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Audit log for status transitions
CREATE TABLE IF NOT EXISTS visit_status_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id INTEGER NOT NULL REFERENCES visits(id),
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    trigger_signal_type TEXT NOT NULL CHECK(trigger_signal_type IN ('gps', 'question', 'proactive', 'timeout', 'system')),
    confidence_score INTEGER NOT NULL,
    trigger_signal_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Push notification tracking
CREATE TABLE IF NOT EXISTS push_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carer_id INTEGER NOT NULL REFERENCES carers(id),
    notification_type TEXT NOT NULL CHECK(notification_type IN ('schedule_change', 'contextual_question', 'general')),
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'delivered', 'failed', 'undelivered')),
    retry_count INTEGER NOT NULL DEFAULT 0,
    sent_at TEXT,
    delivered_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for carer mobile app tables
CREATE INDEX IF NOT EXISTS idx_gps_signals_carer_captured ON gps_signals(carer_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_visit_status_visit_current ON visit_status(visit_id, is_current);
CREATE INDEX IF NOT EXISTS idx_visit_status_carer ON visit_status(carer_id);
CREATE INDEX IF NOT EXISTS idx_contextual_questions_carer_status ON contextual_questions(carer_id, status);
CREATE INDEX IF NOT EXISTS idx_proactive_inputs_carer ON proactive_inputs(carer_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_push_notifications_carer ON push_notifications(carer_id, created_at);

-- Care Contracts & Visit Generation tables

CREATE TABLE IF NOT EXISTS care_contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL UNIQUE REFERENCES patients(id),
    visit_frequency TEXT NOT NULL CHECK(visit_frequency IN ('daily', 'weekdays_only', 'specific_days', 'alternate_days', 'weekly')),
    days_of_week TEXT,  -- JSON array e.g. ["mon","tue","fri"], required when frequency=specific_days
    visits_per_day INTEGER NOT NULL CHECK(visits_per_day >= 1 AND visits_per_day <= 4),
    start_date TEXT NOT NULL,  -- YYYY-MM-DD
    end_date TEXT,  -- YYYY-MM-DD or NULL for ongoing
    excluded_dates TEXT NOT NULL DEFAULT '[]',  -- JSON array of YYYY-MM-DD strings
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS visit_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL REFERENCES care_contracts(id) ON DELETE CASCADE,
    slot_index INTEGER NOT NULL,  -- 0-based ordering within contract
    label TEXT NOT NULL CHECK(length(label) >= 1 AND length(label) <= 100),
    earliest_start TEXT NOT NULL,  -- HH:MM format
    latest_start TEXT NOT NULL,    -- HH:MM format
    duration_minutes INTEGER NOT NULL CHECK(duration_minutes >= 15 AND duration_minutes <= 120),
    required_skills TEXT NOT NULL DEFAULT '[]',  -- JSON array of skill names
    UNIQUE(contract_id, slot_index)
);

-- Indexes for care contracts tables
CREATE INDEX IF NOT EXISTS idx_care_contracts_patient ON care_contracts(patient_id);
CREATE INDEX IF NOT EXISTS idx_visit_slots_contract ON visit_slots(contract_id);
CREATE INDEX IF NOT EXISTS idx_visits_target_date ON visits(target_date);
CREATE INDEX IF NOT EXISTS idx_visits_contract_id ON visits(contract_id);

-- Background Optimisation Jobs table

CREATE TABLE IF NOT EXISTS optimisation_jobs (
    id TEXT PRIMARY KEY,                    -- UUID v4
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK(status IN ('queued', 'running', 'completed', 'failed', 'stale', 'cancelled')),
    visit_ids TEXT NOT NULL DEFAULT '[]',   -- JSON array of visit IDs
    
    -- Fingerprint at creation
    fingerprint_carers TEXT,               -- ISO 8601 max(updated_at) or NULL
    fingerprint_visits TEXT,
    fingerprint_patients TEXT,
    fingerprint_constraints TEXT,
    
    -- Progress (updated in-flight)
    elapsed_seconds INTEGER NOT NULL DEFAULT 0,
    percentage_complete INTEGER NOT NULL DEFAULT 0,
    solutions_found INTEGER NOT NULL DEFAULT 0,
    current_best_score REAL,
    
    -- Result (populated on completion)
    result_json TEXT,                       -- Full OptimisationResult JSON blob
    error_message TEXT,                    -- Max 1000 chars, populated on failure
    
    -- Staleness detail
    is_stale INTEGER NOT NULL DEFAULT 0,
    stale_tables TEXT,                     -- JSON: {"carers": false, "visits": true, ...}
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    
    -- Cancellation support
    cancelled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_optimisation_jobs_status ON optimisation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_optimisation_jobs_created_at ON optimisation_jobs(created_at);
