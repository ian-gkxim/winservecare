/**
 * TypeScript type definitions for the WinServeCare Carer Mobile App.
 * These interfaces match the backend Pydantic models in backend/app/models/mobile.py.
 */

// --- Enums ---

export enum VisitStatus {
  PENDING = 'pending',
  TRAVELLING = 'travelling',
  ARRIVED = 'arrived',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  DELAYED = 'delayed',
  MISSED = 'missed',
  CANCELLED = 'cancelled',
}

// --- Signal Models ---

export interface GPSSignal {
  latitude: number;
  longitude: number;
  accuracy_metres: number;
  low_accuracy: boolean;
  captured_at: string; // ISO 8601 UTC
}

export interface GPSBatch {
  signals: GPSSignal[]; // Max 50
}

export interface QuestionResponse {
  question_id: number;
  response_text: string;
  responded_at: string; // ISO 8601 UTC
}

export type ProactiveInputType =
  | 'arrived'
  | 'visit_started'
  | 'visit_completed'
  | 'running_late'
  | 'issue_encountered'
  | 'cannot_complete';

export interface ProactiveInput {
  visit_id: number;
  input_type: ProactiveInputType;
  note?: string; // Max 500 chars
  latitude?: number;
  longitude?: number;
  location_unavailable: boolean;
  captured_at: string; // ISO 8601 UTC
}

// --- Visit Status Models ---

export interface VisitStatusResponse {
  visit_id: number;
  status: VisitStatus;
  confidence_score: number;
  last_updated: string; // ISO 8601 UTC
}

// --- Schedule Models ---

export interface MobileVisitSummary {
  id: number;
  patient_name: string;
  patient_address: string;
  patient_lat: number;
  patient_lng: number;
  window_start: string; // ISO 8601 UTC
  window_end: string; // ISO 8601 UTC
  duration_minutes: number;
  required_skills: string[];
  status: VisitStatus;
  confidence_score: number;
}

export interface MobileVisitDetail extends MobileVisitSummary {
  patient_preferences: string[];
}

// --- Question Models ---

export type QuestionType = 'yes_no' | 'single_choice' | 'free_text';

export interface ContextualQuestionPayload {
  id: number;
  visit_id: number;
  question_text: string;
  question_type: QuestionType;
  options?: string[];
}

// --- Auth Models ---

export interface LoginRequest {
  identifier: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number; // seconds
}

export interface DeviceTokenRequest {
  device_token: string;
  platform: 'ios' | 'android';
}
