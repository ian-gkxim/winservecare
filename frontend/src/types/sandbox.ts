// Journey Sandbox Testing types

export type FeedbackRating = 'thumbs_up' | 'neutral' | 'thumbs_down';

export interface JourneyFeedbackCreate {
  journeyId: number;
  carerId: number;
  rating: FeedbackRating;
  comment?: string;
  submittedAt: string; // ISO 8601 UTC
}

export interface JourneyFeedback {
  id: number;
  journeyId: number;
  carerId: number;
  rating: FeedbackRating;
  comment?: string;
  submittedAt: string;
  createdAt: string;
}

export interface JourneyPlanCreate {
  operatingDay: string; // YYYY-MM-DD
  journeys: JourneyCreateEntry[];
  reason?: 'initial_creation' | 'manual_amendment' | 're_optimisation';
}

export interface JourneyCreateEntry {
  carerId: number;
  visitId?: number;
  originLat: number;
  originLng: number;
  originLabel?: string;
  destinationLat: number;
  destinationLng: number;
  destinationLabel?: string;
  plannedDeparture: string;
  plannedArrival: string;
  plannedDistanceMiles: number;
}

export interface JourneyUpdate {
  carerId?: number;
  plannedDeparture?: string;
  plannedArrival?: string;
  originLat?: number;
  originLng?: number;
  destinationLat?: number;
  destinationLng?: number;
}

export interface ActualJourneyCreate {
  carerId: number;
  operatingDay: string;
  actualDeparture: string;
  actualArrival: string;
  actualDistanceMiles: number;
  routeCoordinates?: number[][];
}

export interface JourneyQueryParams {
  operatingDay?: string;
  carerId?: number;
  status?: string;
  page?: number;
  pageSize?: number;
}

export interface QuickSubmitConfig {
  carerId: number;
  operatingDay: string;
}
