// Care contract types

import type { Visit } from './index';

export type VisitFrequency = 'daily' | 'weekdays_only' | 'specific_days' | 'alternate_days' | 'weekly';
export type DayOfWeek = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';

export interface VisitSlot {
  id?: number;
  slotIndex: number;
  label: string;
  earliestStart: string; // HH:MM
  latestStart: string;   // HH:MM
  durationMinutes: number;
  requiredSkills: string[];
}

export interface CareContract {
  id: number;
  patientId: number;
  visitFrequency: VisitFrequency;
  daysOfWeek: DayOfWeek[] | null;
  visitsPerDay: number;
  startDate: string; // YYYY-MM-DD
  endDate: string | null;
  excludedDates: string[];
  visitSlots: VisitSlot[];
}

export interface CareContractCreate {
  visitFrequency: VisitFrequency;
  daysOfWeek?: DayOfWeek[];
  visitsPerDay: number;
  startDate: string;
  endDate?: string | null;
  excludedDates?: string[];
  visitSlots: Omit<VisitSlot, 'id'>[];
}

export interface GenerateVisitsResponse {
  visits: Visit[];
  scheduledCount: number;
  totalContractsEvaluated: number;
  eligibleContracts: number;
}
