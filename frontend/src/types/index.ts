// Core entity types

export interface Carer {
  id: number;
  name: string;
  homeLat: number;
  homeLng: number;
  skills: string[];
  maxWorkingHours: number;
  maxContinuousHours: number;
  minBreakMinutes: number;
}

export interface Patient {
  id: number;
  name: string;
  address: string;
  lat: number;
  lng: number;
  preferences: string[];
  priority: 'low' | 'medium' | 'high';
  continuityScore: number;
  usualCarerId: number | null;
  preferredCarerId: number | null;
}

export interface Visit {
  id: number;
  patientId: number;
  durationMinutes: number;
  windowStart: string; // HH:MM
  windowEnd: string; // HH:MM
  requiredSkills: string[];
  preferredTime: string | null; // HH:MM
  isCancelled: boolean;
  targetDate: string | null;   // YYYY-MM-DD or null for legacy visits
  contractId: number | null;   // Reference to care_contracts.id
}

// KPI types

export interface KPIMetrics {
  totalVisits: number;
  carersAvailable: number;
  travelHours: number; // 1 decimal place
  mileage: number; // 1 decimal place
  overtime: number; // 1 decimal place
  continuityScore: number; // 0-100 percentage
}

// Route types

export interface Route {
  carerId: number;
  stops: RouteStop[];
  totalTravelMinutes: number;
  totalMileage: number;
  totalCost: number;
}

export interface RouteStop {
  visitId: number;
  patientId: number;
  arrivalTime: string; // HH:MM
  startTime: string; // HH:MM
  endTime: string; // HH:MM
  travelTimeFromPrev: number; // minutes
  mileageFromPrev: number;
}

// Animation types

export interface MarkerData {
  id: number;
  name: string;
  lat: number;
  lng: number;
}

export interface AssignmentEdge {
  carerId: number;
  visitId: number;
  patientId: number;
}

export interface CandidateRoute {
  carerId: number;
  stops: RouteStop[];
  score: number;
}

export interface RouteAnimation {
  carerId: number;
  waypoints: Array<{ lat: number; lng: number }>;
  colour: string;
}

export interface AnimationStep {
  stepNumber: number; // 1-8
  stepName: string;
  data: StepData;
}

export type StepData =
  | { type: 'locations'; carers: MarkerData[]; patients: MarkerData[] }
  | { type: 'matrix'; pairCount: number }
  | { type: 'assignments'; edges: AssignmentEdge[] }
  | { type: 'pruning'; removedEdges: AssignmentEdge[]; reason: string }
  | { type: 'evaluation'; candidateRoutes: CandidateRoute[] }
  | { type: 'improvement'; iterations: Array<{ score: number }> }
  | { type: 'solution'; routes: Route[]; finalScore: number }
  | { type: 'animation'; routes: RouteAnimation[] };

// Recommendation types

export interface Recommendation {
  id: number;
  type: 'recommendation' | 'warning';
  title: string;
  description: string; // max 200 chars
  impact: number; // for ordering
}

// Scenario types

export interface VisitAssignment {
  visitId: number;
  carerId: number;
  startTime: string; // HH:MM
  travelTime: number; // minutes
  mileage: number;
}

export interface Scenario {
  id: number;
  name: string;
  totalTravelHours: number;
  totalMileage: number;
  totalOvertimeHours: number;
  continuityScore: number;
  objectiveScore: number;
  assignments: VisitAssignment[];
  routes: Route[];
  createdAt: string;
}

export interface ScenarioSummary {
  id: number;
  name: string;
  totalTravelHours: number;
  totalMileage: number;
  totalOvertimeHours: number;
  continuityScore: number;
  objectiveScore: number;
  createdAt: string;
}

export interface ScenarioComparison {
  scenario1: Scenario;
  scenario2: Scenario;
  differences: MetricDifference[];
  changedVisits: number[];
}

export interface MetricDifference {
  metric: string;
  value1: number;
  value2: number;
  absoluteDiff: number;
  percentageDiff: number;
}

// Exception types

export interface Exception {
  id: number;
  timestamp: string;
  description: string;
  constraintNames: string[];
  affectedEntityType: 'carer' | 'visit';
  affectedEntityId: number;
  isResolved: boolean;
  resolvedAt: string | null;
}

// Skill and constraint types

export interface Skill {
  id: number;
  name: string;
  carerCount: number;
  visitCount: number;
}

export interface Constraint {
  id: number;
  name: string;
  description: string;
  isEnabled: boolean;
}

// Configuration types

export interface Config {
  googleMapsApiKey: string;
  hasApiKey: boolean;
}

// Schedule comparison types

export interface Schedule {
  routes: Route[];
  totalTravelHours: number;
  totalMileage: number;
  totalOvertimeHours: number;
  continuityScore: number;
  totalCost: number;
}

export interface ScheduleSavings {
  travelHours: number;
  travelHoursPercent: number;
  mileage: number;
  mileagePercent: number;
  overtime: number;
  overtimePercent: number;
  totalCost: number;
  totalCostPercent: number;
}

// Report types

export interface ReportMetrics {
  totalTravelHours: number;
  totalMileage: number;
  totalOvertimeHours: number;
  continuityScore: number;
}

export interface ReportDifferences {
  travelHours: { absolute: number; percentage: number };
  mileage: { absolute: number; percentage: number };
  overtime: { absolute: number; percentage: number };
  continuityScore: { absolute: number; percentage: number };
}

export interface Report {
  available: boolean;
  message?: string;
  before?: ReportMetrics;
  after?: ReportMetrics;
  differences?: ReportDifferences;
}

// WebSocket message types

export interface WsStartMessage {
  type: 'start';
  visitIds?: number[];
}

export interface WsPauseMessage {
  type: 'pause';
}

export interface WsResumeMessage {
  type: 'resume';
}

export type WsClientMessage = WsStartMessage | WsPauseMessage | WsResumeMessage;

export interface WsStepMessage {
  type: 'step';
  payload: AnimationStep;
}

export interface WsProgressMessage {
  type: 'progress';
  step: number;
  name: string;
  score: number;
}

export interface WsCompleteMessage {
  type: 'complete';
  finalScore: number;
  routes: Route[];
}

export interface WsErrorMessage {
  type: 'error';
  step: number;
  message: string;
}

export type WsServerMessage =
  | WsStepMessage
  | WsProgressMessage
  | WsCompleteMessage
  | WsErrorMessage;

// Optimisation result types

export interface InfeasibilityReason {
  visitId: number;
  carerIds: number[];
  constraintName: string;
  reason: string;
}

export interface OptimisationResult {
  routes: Route[];
  objectiveScore: number;
  kpis: KPIMetrics;
  recommendations: Recommendation[];
  unassignedVisits: number[];
  infeasibilityReasons: InfeasibilityReason[];
}

// Update/create payload types

export interface CarerUpdate {
  name?: string;
  homeLat?: number;
  homeLng?: number;
  skills?: string[];
  maxWorkingHours?: number;
  maxContinuousHours?: number;
  minBreakMinutes?: number;
}

export interface PatientUpdate {
  name?: string;
  address?: string;
  lat?: number;
  lng?: number;
  preferences?: string[];
  priority?: 'low' | 'medium' | 'high';
  usualCarerId?: number | null;
  preferredCarerId?: number | null;
}

export interface SkillCreate {
  name: string;
}

export interface ConstraintUpdate {
  isEnabled: boolean;
}

export interface ScenarioCreate {
  name: string;
}

export interface ConfigUpdate {
  googleMapsApiKey: string;
}
