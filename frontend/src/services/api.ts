import axios from 'axios';
import type {
  Carer,
  CarerUpdate,
  Patient,
  PatientUpdate,
  Visit,
  Skill,
  SkillCreate,
  Constraint,
  ConstraintUpdate,
  Scenario,
  ScenarioSummary,
  ScenarioComparison,
  ScenarioCreate,
  Exception,
  KPIMetrics,
  Report,
  Config,
  ConfigUpdate,
} from '../types';
import type { CareContract, CareContractCreate } from '../types/contracts';
import type {
  JourneyFeedbackCreate,
  JourneyFeedback,
  JourneyPlanCreate,
  JourneyUpdate,
  ActualJourneyCreate,
  JourneyQueryParams,
} from '../types/sandbox';

const api = axios.create({
  baseURL: '/ainative/api',
  headers: { 'Content-Type': 'application/json' },
});

// Convert snake_case keys to camelCase recursively
function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function transformKeys(data: unknown): unknown {
  if (Array.isArray(data)) {
    return data.map(transformKeys);
  }
  if (data !== null && typeof data === 'object' && !(data instanceof Date)) {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      result[snakeToCamel(key)] = transformKeys(value);
    }
    return result;
  }
  return data;
}

// Transform all API responses from snake_case to camelCase
api.interceptors.response.use((response) => {
  if (response.data) {
    response.data = transformKeys(response.data);
  }
  return response;
});

// Convert camelCase keys to snake_case for request payloads
function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

function transformKeysToSnake(data: unknown): unknown {
  if (Array.isArray(data)) {
    return data.map(transformKeysToSnake);
  }
  if (data !== null && typeof data === 'object' && !(data instanceof Date)) {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      result[camelToSnake(key)] = transformKeysToSnake(value);
    }
    return result;
  }
  return data;
}

api.interceptors.request.use((config) => {
  if (config.data && typeof config.data === 'object') {
    config.data = transformKeysToSnake(config.data);
  }
  return config;
});

// Carers
export const getCarers = () => api.get<Carer[]>('/carers').then((r) => r.data);
export const updateCarer = (id: number, data: CarerUpdate) =>
  api.put<Carer>(`/carers/${id}`, data).then((r) => r.data);

// Patients
export const getPatients = () => api.get<Patient[]>('/patients').then((r) => r.data);
export const updatePatient = (id: number, data: PatientUpdate) =>
  api.put<Patient>(`/patients/${id}`, data).then((r) => r.data);

// Visits
export const getVisits = () => api.get<Visit[]>('/visits').then((r) => r.data);
export const deleteVisit = (id: number) => api.delete(`/visits/${id}`);
export const getVisitsByDate = (targetDate: string) =>
  api.get('/visits', { params: { target_date: targetDate } }).then((r) => r.data);
export const generateVisits = (targetDate: string) =>
  api.post('/visits/generate', { target_date: targetDate }).then((r) => r.data);
export const regenerateVisits = (targetDate: string) =>
  api.post('/visits/regenerate', { target_date: targetDate }).then((r) => r.data);
export const cancelVisit = (id: number) =>
  api.patch(`/visits/${id}/cancel`).then((r) => r.data);

// Skills
export const getSkills = () => api.get<Skill[]>('/skills').then((r) => r.data);
export const createSkill = (data: SkillCreate) =>
  api.post<Skill>('/skills', data).then((r) => r.data);

// Constraints
export const getConstraints = () => api.get<Constraint[]>('/constraints').then((r) => r.data);
export const updateConstraint = (id: number, data: ConstraintUpdate) =>
  api.put<Constraint>(`/constraints/${id}`, data).then((r) => r.data);

// Scenarios
export const getScenarios = () => api.get<ScenarioSummary[]>('/scenarios').then((r) => r.data);
export const createScenario = (data: ScenarioCreate) =>
  api.post<Scenario>('/scenarios', data).then((r) => r.data);
export const getScenario = (id: number) =>
  api.get<Scenario>(`/scenarios/${id}`).then((r) => r.data);
export const compareScenarios = (ids: number[]) =>
  api.get<ScenarioComparison>('/scenarios/compare', { params: { ids: ids.join(',') } }).then((r) => r.data);

// Exceptions
export const getExceptions = () => api.get<Exception[]>('/exceptions').then((r) => r.data);
export const resolveException = (id: number) =>
  api.put<Exception>(`/exceptions/${id}/resolve`).then((r) => r.data);

// KPIs
export const getKpis = () => api.get<KPIMetrics>('/kpis').then((r) => r.data);

// Reports
export const getLatestReport = () => api.get<Report>('/reports/latest').then((r) => r.data);

// Config
export const getConfig = () => api.get<Config>('/config').then((r) => r.data);
export const updateConfig = (data: ConfigUpdate) =>
  api.put<Config>('/config', data).then((r) => r.data);

// Contracts
export const getPatientContract = (patientId: number) =>
  api.get<CareContract | null>(`/patients/${patientId}/contract`).then((r) => r.data);
export const savePatientContract = (patientId: number, data: CareContractCreate) =>
  api.put<CareContract>(`/patients/${patientId}/contract`, data).then((r) => r.data);
export const deletePatientContract = (patientId: number) =>
  api.delete(`/patients/${patientId}/contract`);

// Journey Feedback
export const submitJourneyFeedback = (data: JourneyFeedbackCreate) =>
  api.post<JourneyFeedback>('/journey-feedback', data).then((r) => r.data);

export const getJourneyFeedback = (journeyId: number) =>
  api.get<JourneyFeedback>(`/journey-feedback/${journeyId}`).then((r) => r.data);

// Journey Plans
export const createJourneyPlan = (data: JourneyPlanCreate) =>
  api.post('/journey-plans', data).then((r) => r.data);

export const listJourneyPlans = (params?: { operatingDay?: string; includeArchived?: boolean }) =>
  api.get('/journey-plans', { params }).then((r) => r.data);

export const getJourneyPlan = (planId: number) =>
  api.get(`/journey-plans/${planId}`).then((r) => r.data);

export const modifyJourney = (planId: number, journeyId: number, update: JourneyUpdate) =>
  api.put(`/journey-plans/${planId}/journeys/${journeyId}`, update).then((r) => r.data);

export const deleteJourneyPlan = (planId: number) =>
  api.delete(`/journey-plans/${planId}`).then((r) => r.data);

export const cancelJourney = (journeyId: number) =>
  api.post(`/journeys/${journeyId}/cancel`).then((r) => r.data);

// Actual Journeys
export const submitActualJourney = (data: ActualJourneyCreate) =>
  api.post('/actual-journeys', data).then((r) => r.data);

// Comparison & History
export const getJourneyComparison = (operatingDay: string, planVersion?: number) =>
  api.get(`/journey-comparison/${operatingDay}`, { params: planVersion ? { plan_version: planVersion } : {} }).then((r) => r.data);

export const getJourneyHistory = (operatingDay: string) =>
  api.get(`/journey-history/${operatingDay}`).then((r) => r.data);

export const getJourneyHistoryRange = (start: string, end: string) =>
  api.get('/journey-history', { params: { start, end } }).then((r) => r.data);

// Query
export const queryJourneys = (params: JourneyQueryParams) =>
  api.get('/journeys', { params }).then((r) => r.data);

export default api;
