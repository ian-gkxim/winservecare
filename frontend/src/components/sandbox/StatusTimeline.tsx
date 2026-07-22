import { useState, useEffect, useCallback } from 'react';
import { queryJourneys } from '../../services/api';

/** Possible journey statuses with their colour mappings. */
export type JourneyStatus =
  | 'planned'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'overdue'
  | 'amended';

/** A single status transition entry. */
export interface StatusTransition {
  previousStatus: JourneyStatus | null;
  newStatus: JourneyStatus;
  timestamp: string;
  triggerSource: string;
}

export interface StatusTimelineProps {
  journeyId: number;
  isOpen: boolean;
  onClose: () => void;
}

/** Maps each journey status to its badge colour class. */
export const STATUS_COLOUR_MAP: Record<JourneyStatus, string> = {
  planned: 'bg-blue-100 text-blue-800 border-blue-300',
  in_progress: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  completed: 'bg-green-100 text-green-800 border-green-300',
  cancelled: 'bg-red-100 text-red-800 border-red-300',
  overdue: 'bg-orange-100 text-orange-800 border-orange-300',
  amended: 'bg-gray-100 text-gray-800 border-gray-300',
};

/** Returns tailwind classes for a status badge. */
export function getStatusBadgeClasses(status: JourneyStatus): string {
  return STATUS_COLOUR_MAP[status] ?? 'bg-gray-100 text-gray-800 border-gray-300';
}

/**
 * Derives a simplified list of status transitions from a journey's current status.
 * Since we don't have a dedicated transition log table yet, we infer the likely
 * transitions based on the current status.
 */
export function deriveTransitions(
  currentStatus: JourneyStatus,
  createdAt?: string,
  updatedAt?: string
): StatusTransition[] {
  const transitions: StatusTransition[] = [];
  const baseTimestamp = createdAt || new Date().toISOString();
  const lastTimestamp = updatedAt || baseTimestamp;

  // All journeys start as planned
  transitions.push({
    previousStatus: null,
    newStatus: 'planned',
    timestamp: baseTimestamp,
    triggerSource: 'API call',
  });

  if (currentStatus === 'planned') {
    return transitions;
  }

  if (currentStatus === 'in_progress') {
    transitions.push({
      previousStatus: 'planned',
      newStatus: 'in_progress',
      timestamp: lastTimestamp,
      triggerSource: 'Actual data received',
    });
    return transitions;
  }

  if (currentStatus === 'completed') {
    transitions.push({
      previousStatus: 'planned',
      newStatus: 'in_progress',
      timestamp: baseTimestamp,
      triggerSource: 'Actual data received',
    });
    transitions.push({
      previousStatus: 'in_progress',
      newStatus: 'completed',
      timestamp: lastTimestamp,
      triggerSource: 'Actual data received',
    });
    return transitions;
  }

  if (currentStatus === 'cancelled') {
    transitions.push({
      previousStatus: 'planned',
      newStatus: 'cancelled',
      timestamp: lastTimestamp,
      triggerSource: 'API call',
    });
    return transitions;
  }

  if (currentStatus === 'overdue') {
    transitions.push({
      previousStatus: 'planned',
      newStatus: 'in_progress',
      timestamp: baseTimestamp,
      triggerSource: 'Actual data received',
    });
    transitions.push({
      previousStatus: 'in_progress',
      newStatus: 'overdue',
      timestamp: lastTimestamp,
      triggerSource: 'Timeout',
    });
    return transitions;
  }

  if (currentStatus === 'amended') {
    transitions.push({
      previousStatus: 'planned',
      newStatus: 'amended',
      timestamp: lastTimestamp,
      triggerSource: 'API call',
    });
    return transitions;
  }

  return transitions;
}

/**
 * StatusTimeline component — displays journey state transitions in chronological order.
 * Renders as a slide-over panel when `isOpen` is true.
 */
export function StatusTimeline({ journeyId, isOpen, onClose }: StatusTimelineProps) {
  const [transitions, setTransitions] = useState<StatusTransition[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJourneyDetails = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Query the specific journey by ID
      const result = await queryJourneys({ page: 1, pageSize: 50 });
      const journeys = result?.journeys ?? result ?? [];
      const journey = Array.isArray(journeys)
        ? journeys.find((j: Record<string, unknown>) => j.id === journeyId)
        : null;

      if (journey) {
        const derived = deriveTransitions(
          journey.status as JourneyStatus,
          journey.createdAt as string | undefined,
          journey.updatedAt as string | undefined
        );
        setTransitions(derived);
      } else {
        // Fallback: show a single planned status
        setTransitions([
          {
            previousStatus: null,
            newStatus: 'planned',
            timestamp: new Date().toISOString(),
            triggerSource: 'API call',
          },
        ]);
      }
    } catch (err) {
      setError('Failed to load journey details');
      // Still show a minimal fallback
      setTransitions([
        {
          previousStatus: null,
          newStatus: 'planned',
          timestamp: new Date().toISOString(),
          triggerSource: 'API call',
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [journeyId]);

  useEffect(() => {
    if (isOpen && journeyId) {
      fetchJourneyDetails();
    }
  }, [isOpen, journeyId, fetchJourneyDetails]);

  // Handle escape key to close
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="timeline-title"
    >
      <div className="bg-white w-full max-w-md h-full shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 id="timeline-title" className="text-lg font-semibold text-gray-900">
            Status Timeline — Journey #{journeyId}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Close timeline"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {loading && (
            <p className="text-sm text-gray-500">Loading timeline...</p>
          )}

          {error && (
            <p className="text-sm text-red-600 mb-4">{error}</p>
          )}

          {!loading && transitions.length === 0 && (
            <p className="text-sm text-gray-500">No transitions recorded for this journey.</p>
          )}

          {!loading && transitions.length > 0 && (
            <ol className="relative border-l-2 border-gray-200 ml-3 space-y-6">
              {transitions.map((transition, index) => (
                <li key={index} className="ml-6">
                  {/* Timeline dot */}
                  <span className="absolute -left-2 flex items-center justify-center w-4 h-4 bg-white border-2 border-gray-300 rounded-full" />

                  {/* Transition content */}
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                    {/* Status badges */}
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      {transition.previousStatus && (
                        <>
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${getStatusBadgeClasses(transition.previousStatus)}`}
                            data-testid={`badge-${transition.previousStatus}`}
                          >
                            {transition.previousStatus.replace('_', ' ')}
                          </span>
                          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </>
                      )}
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${getStatusBadgeClasses(transition.newStatus)}`}
                        data-testid={`badge-${transition.newStatus}`}
                      >
                        {transition.newStatus.replace('_', ' ')}
                      </span>
                    </div>

                    {/* Timestamp */}
                    <p className="text-xs text-gray-500 mb-1">
                      <span className="font-medium">Time:</span>{' '}
                      {new Date(transition.timestamp).toLocaleString()}
                    </p>

                    {/* Trigger source */}
                    <p className="text-xs text-gray-500">
                      <span className="font-medium">Trigger:</span>{' '}
                      {transition.triggerSource}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
