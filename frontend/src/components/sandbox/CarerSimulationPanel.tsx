import { useState, useEffect } from 'react';
import { getCarers, submitActualJourney, submitJourneyFeedback } from '../../services/api';
import type { Carer } from '../../types';
import type {
  ActualJourneyCreate,
  FeedbackRating,
  JourneyFeedbackCreate,
  JourneyFeedback,
} from '../../types/sandbox';

export interface CarerSimulationPanelProps {
  onActualSubmitted: (actual: Record<string, unknown>) => void;
  onFeedbackSubmitted: (feedback: JourneyFeedback) => void;
}

interface FieldErrors {
  carerId?: string;
  operatingDay?: string;
  actualDeparture?: string;
  actualArrival?: string;
  actualDistanceMiles?: string;
  routeCoordinates?: string;
  general?: string;
}

interface SubmissionResult {
  matchStatus: 'matched' | 'unmatched';
  matchedJourneyId?: number;
  journeyId?: number;
}

interface FeedbackHistoryEntry {
  journeyId: number;
  rating: FeedbackRating;
  comment?: string;
}

/**
 * Generates randomised actual journey data for Quick Submit.
 * Departure: ±30 min of now, Arrival: 15-60 min after departure, Distance: 1-20 miles.
 */
export function generateQuickSubmitData(carerId: number, operatingDay: string) {
  const now = new Date();

  // Departure ±30 min of now
  const departureOffsetMs = (Math.random() * 60 - 30) * 60 * 1000;
  const departure = new Date(now.getTime() + departureOffsetMs);

  // Arrival 15-60 min after departure
  const arrivalOffsetMs = (Math.random() * 45 + 15) * 60 * 1000;
  const arrival = new Date(departure.getTime() + arrivalOffsetMs);

  // Distance 1-20 miles
  const distance = Math.round((Math.random() * 19 + 1) * 10) / 10;

  return {
    carerId,
    operatingDay,
    actualDeparture: departure.toISOString(),
    actualArrival: arrival.toISOString(),
    actualDistanceMiles: distance,
  };
}

/**
 * CarerSimulationPanel — Mobile-friendly carer simulation with actual journey
 * submission, feedback, and quick submit.
 */
export function CarerSimulationPanel({
  onActualSubmitted,
  onFeedbackSubmitted,
}: CarerSimulationPanelProps) {
  // Carer list
  const [carers, setCarers] = useState<Carer[]>([]);
  const [carersLoading, setCarersLoading] = useState(true);

  // Form state
  const [selectedCarerId, setSelectedCarerId] = useState<number | ''>('');
  const [operatingDay, setOperatingDay] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [actualDeparture, setActualDeparture] = useState('');
  const [actualArrival, setActualArrival] = useState('');
  const [actualDistanceMiles, setActualDistanceMiles] = useState('');
  const [routeCoordinates, setRouteCoordinates] = useState('');

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submissionResult, setSubmissionResult] = useState<SubmissionResult | null>(null);

  // Feedback state
  const [showFeedbackPrompt, setShowFeedbackPrompt] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState<FeedbackRating | null>(null);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [showThumbsDownHint, setShowThumbsDownHint] = useState(false);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  // Session feedback history
  const [feedbackHistory, setFeedbackHistory] = useState<FeedbackHistoryEntry[]>([]);

  // Load carers on mount
  useEffect(() => {
    const loadCarers = async () => {
      try {
        const data = await getCarers();
        setCarers(data);
        if (data.length > 0) {
          setSelectedCarerId(data[0].id);
        }
      } catch {
        // Silently fail; user can retry
      } finally {
        setCarersLoading(false);
      }
    };
    loadCarers();
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setFieldErrors({});
    setSubmissionResult(null);
    setShowFeedbackPrompt(false);

    if (!selectedCarerId) {
      setFieldErrors({ carerId: 'Please select a carer' });
      return;
    }

    const payload: ActualJourneyCreate = {
      carerId: Number(selectedCarerId),
      operatingDay,
      actualDeparture: actualDeparture
        ? new Date(actualDeparture).toISOString()
        : '',
      actualArrival: actualArrival
        ? new Date(actualArrival).toISOString()
        : '',
      actualDistanceMiles: parseFloat(actualDistanceMiles) || 0,
    };

    // Parse route coordinates if provided
    if (routeCoordinates.trim()) {
      try {
        const parsed = JSON.parse(routeCoordinates);
        if (Array.isArray(parsed)) {
          payload.routeCoordinates = parsed;
        }
      } catch {
        setFieldErrors({ routeCoordinates: 'Invalid JSON array format' });
        return;
      }
    }

    setSubmitting(true);
    try {
      const result = await submitActualJourney(payload);
      const matchStatus =
        result.matchedJourneyId || result.journeyId
          ? 'matched'
          : 'unmatched';

      const submission: SubmissionResult = {
        matchStatus,
        matchedJourneyId: result.matchedJourneyId ?? result.journeyId,
        journeyId: result.id ?? result.journeyId,
      };

      setSubmissionResult(submission);
      onActualSubmitted(result);

      // Show feedback prompt if matched
      if (matchStatus === 'matched') {
        setShowFeedbackPrompt(true);
      }
    } catch (err: unknown) {
      // Handle 4xx API errors with field-level messages
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { status?: number; data?: Record<string, unknown> } }).response
      ) {
        const response = (err as { response: { status: number; data: Record<string, unknown> } })
          .response;
        if (response.status >= 400 && response.status < 500) {
          const data = response.data;
          const errors: FieldErrors = {};

          if (data.detail && Array.isArray(data.detail)) {
            for (const d of data.detail as Array<{ loc?: string[]; msg?: string }>) {
              const field = d.loc?.[d.loc.length - 1];
              if (field && field in errors === false) {
                (errors as Record<string, string>)[field] = d.msg || 'Invalid value';
              }
            }
          } else if (data.message) {
            errors.general = data.message as string;
          } else if (data.error) {
            errors.general = data.error as string;
          } else {
            errors.general = 'Submission failed. Please check your inputs.';
          }

          setFieldErrors(
            Object.keys(errors).length > 0
              ? errors
              : { general: 'Submission failed' }
          );
        } else {
          setFieldErrors({ general: 'An unexpected error occurred' });
        }
      } else {
        setFieldErrors({ general: 'Network error. Please try again.' });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleQuickSubmit = async () => {
    if (!selectedCarerId) return;

    const data = generateQuickSubmitData(Number(selectedCarerId), operatingDay);

    // Fill form for visibility
    setActualDeparture(data.actualDeparture.slice(0, 16));
    setActualArrival(data.actualArrival.slice(0, 16));
    setActualDistanceMiles(data.actualDistanceMiles.toString());
    setRouteCoordinates('');
    setFieldErrors({});
    setSubmissionResult(null);
    setShowFeedbackPrompt(false);

    setSubmitting(true);
    try {
      const result = await submitActualJourney(data);
      const matchStatus =
        result.matchedJourneyId || result.journeyId
          ? 'matched'
          : 'unmatched';

      const submission: SubmissionResult = {
        matchStatus,
        matchedJourneyId: result.matchedJourneyId ?? result.journeyId,
        journeyId: result.id ?? result.journeyId,
      };

      setSubmissionResult(submission);
      onActualSubmitted(result);

      if (matchStatus === 'matched') {
        setShowFeedbackPrompt(true);
      }
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { data?: Record<string, unknown> } }).response
      ) {
        const data = (err as { response: { data: Record<string, unknown> } }).response.data;
        setFieldErrors({
          general: (data.message as string) || (data.error as string) || 'Quick submit failed',
        });
      } else {
        setFieldErrors({ general: 'Network error. Please try again.' });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleFeedbackSubmit = async () => {
    if (!feedbackRating || !submissionResult?.matchedJourneyId) return;

    // Soft prompt on thumbs_down without comment
    if (feedbackRating === 'thumbs_down' && !feedbackComment.trim() && !showThumbsDownHint) {
      setShowThumbsDownHint(true);
      return;
    }

    setFeedbackSubmitting(true);
    setFeedbackError(null);

    const payload: JourneyFeedbackCreate = {
      journeyId: submissionResult.matchedJourneyId,
      carerId: Number(selectedCarerId),
      rating: feedbackRating,
      submittedAt: new Date().toISOString(),
    };

    if (feedbackComment.trim()) {
      payload.comment = feedbackComment.trim();
    }

    try {
      const result = await submitJourneyFeedback(payload);
      onFeedbackSubmitted(result);

      // Add to session history
      setFeedbackHistory((prev) => [
        {
          journeyId: submissionResult.matchedJourneyId!,
          rating: feedbackRating,
          comment: feedbackComment.trim() || undefined,
        },
        ...prev,
      ]);

      // Reset feedback state
      setShowFeedbackPrompt(false);
      setFeedbackRating(null);
      setFeedbackComment('');
      setShowThumbsDownHint(false);
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { data?: Record<string, unknown> } }).response
      ) {
        const data = (err as { response: { data: Record<string, unknown> } }).response.data;
        setFeedbackError(
          (data.message as string) || (data.error as string) || 'Failed to submit feedback'
        );
      } else {
        setFeedbackError('Network error. Please try again.');
      }
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const handleSkipFeedback = () => {
    setShowFeedbackPrompt(false);
    setFeedbackRating(null);
    setFeedbackComment('');
    setShowThumbsDownHint(false);
    setFeedbackError(null);
  };

  const ratingIcon = (rating: FeedbackRating) => {
    switch (rating) {
      case 'thumbs_up':
        return '👍';
      case 'neutral':
        return '😐';
      case 'thumbs_down':
        return '👎';
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      {/* Panel Header */}
      <div className="px-4 py-3 border-b border-gray-200">
        <h3 className="text-base font-semibold text-gray-900">
          Carer Simulation
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Submit actual journey data and provide route feedback
        </p>
      </div>

      <div className="p-4 space-y-4">
        {/* Actual Journey Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          {/* General error */}
          {fieldErrors.general && (
            <div className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {fieldErrors.general}
            </div>
          )}

          {/* Carer Selection */}
          <div>
            <label
              htmlFor="carer-select"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Carer
            </label>
            <select
              id="carer-select"
              value={selectedCarerId}
              onChange={(e) => setSelectedCarerId(Number(e.target.value) || '')}
              disabled={carersLoading}
              className={`w-full min-h-[44px] px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                fieldErrors.carerId ? 'border-red-300' : 'border-gray-300'
              }`}
            >
              {carersLoading && <option value="">Loading carers...</option>}
              {!carersLoading && carers.length === 0 && (
                <option value="">No carers available</option>
              )}
              {carers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {fieldErrors.carerId && (
              <p className="text-xs text-red-600 mt-0.5">{fieldErrors.carerId}</p>
            )}
          </div>

          {/* Operating Day */}
          <div>
            <label
              htmlFor="operating-day"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Operating Day
            </label>
            <input
              id="operating-day"
              type="date"
              value={operatingDay}
              onChange={(e) => setOperatingDay(e.target.value)}
              className={`w-full min-h-[44px] px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                fieldErrors.operatingDay ? 'border-red-300' : 'border-gray-300'
              }`}
            />
            {fieldErrors.operatingDay && (
              <p className="text-xs text-red-600 mt-0.5">{fieldErrors.operatingDay}</p>
            )}
          </div>

          {/* Actual Departure */}
          <div>
            <label
              htmlFor="actual-departure"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Actual Departure
            </label>
            <input
              id="actual-departure"
              type="datetime-local"
              value={actualDeparture}
              onChange={(e) => setActualDeparture(e.target.value)}
              className={`w-full min-h-[44px] px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                fieldErrors.actualDeparture ? 'border-red-300' : 'border-gray-300'
              }`}
            />
            {fieldErrors.actualDeparture && (
              <p className="text-xs text-red-600 mt-0.5">{fieldErrors.actualDeparture}</p>
            )}
          </div>

          {/* Actual Arrival */}
          <div>
            <label
              htmlFor="actual-arrival"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Actual Arrival
            </label>
            <input
              id="actual-arrival"
              type="datetime-local"
              value={actualArrival}
              onChange={(e) => setActualArrival(e.target.value)}
              className={`w-full min-h-[44px] px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                fieldErrors.actualArrival ? 'border-red-300' : 'border-gray-300'
              }`}
            />
            {fieldErrors.actualArrival && (
              <p className="text-xs text-red-600 mt-0.5">{fieldErrors.actualArrival}</p>
            )}
          </div>

          {/* Actual Distance */}
          <div>
            <label
              htmlFor="actual-distance"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Actual Distance (miles)
            </label>
            <input
              id="actual-distance"
              type="number"
              step="0.1"
              min="0"
              value={actualDistanceMiles}
              onChange={(e) => setActualDistanceMiles(e.target.value)}
              placeholder="e.g. 5.2"
              className={`w-full min-h-[44px] px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                fieldErrors.actualDistanceMiles ? 'border-red-300' : 'border-gray-300'
              }`}
            />
            {fieldErrors.actualDistanceMiles && (
              <p className="text-xs text-red-600 mt-0.5">
                {fieldErrors.actualDistanceMiles}
              </p>
            )}
          </div>

          {/* Route Coordinates (optional) */}
          <div>
            <label
              htmlFor="route-coordinates"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Route Coordinates{' '}
              <span className="text-gray-400 font-normal">(optional JSON)</span>
            </label>
            <textarea
              id="route-coordinates"
              value={routeCoordinates}
              onChange={(e) => setRouteCoordinates(e.target.value)}
              placeholder='[[51.5, -0.1], [51.6, -0.2]]'
              rows={2}
              className={`w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                fieldErrors.routeCoordinates ? 'border-red-300' : 'border-gray-300'
              }`}
            />
            {fieldErrors.routeCoordinates && (
              <p className="text-xs text-red-600 mt-0.5">
                {fieldErrors.routeCoordinates}
              </p>
            )}
          </div>

          {/* Buttons */}
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="submit"
              disabled={submitting}
              className="min-h-[44px] min-w-[44px] flex-1 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Submitting...' : 'Submit Actual'}
            </button>
            <button
              type="button"
              onClick={handleQuickSubmit}
              disabled={submitting || !selectedCarerId}
              className="min-h-[44px] min-w-[44px] flex-1 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-md hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ⚡ Quick Submit
            </button>
          </div>
        </form>

        {/* Submission Result */}
        {submissionResult && (
          <div
            className={`p-3 rounded-md border text-sm ${
              submissionResult.matchStatus === 'matched'
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-yellow-50 border-yellow-200 text-yellow-800'
            }`}
            role="status"
            aria-live="polite"
          >
            <p className="font-medium">
              Status:{' '}
              <span className="capitalize">{submissionResult.matchStatus}</span>
            </p>
            {submissionResult.matchedJourneyId && (
              <p className="text-xs mt-0.5">
                Matched Journey ID: #{submissionResult.matchedJourneyId}
              </p>
            )}
          </div>
        )}

        {/* Feedback Prompt */}
        {showFeedbackPrompt && (
          <div className="p-4 bg-gray-50 rounded-md border border-gray-200 space-y-3">
            <p className="text-sm font-medium text-gray-700">
              How was the route?
            </p>

            {/* Rating icons */}
            <div className="flex gap-3">
              {(['thumbs_up', 'neutral', 'thumbs_down'] as FeedbackRating[]).map(
                (rating) => (
                  <button
                    key={rating}
                    type="button"
                    onClick={() => {
                      setFeedbackRating(rating);
                      setShowThumbsDownHint(false);
                    }}
                    className={`min-h-[44px] min-w-[44px] flex items-center justify-center text-2xl rounded-md border-2 transition-colors ${
                      feedbackRating === rating
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-400'
                    }`}
                    aria-label={rating.replace('_', ' ')}
                    aria-pressed={feedbackRating === rating}
                  >
                    {ratingIcon(rating)}
                  </button>
                )
              )}
            </div>

            {/* Thumbs down hint */}
            {showThumbsDownHint && (
              <p className="text-xs text-amber-600">
                Consider adding a comment to explain the issue. You can still
                submit without one.
              </p>
            )}

            {/* Comment input */}
            {feedbackRating && (
              <div>
                <label
                  htmlFor="feedback-comment"
                  className="block text-xs text-gray-600 mb-1"
                >
                  Comment (optional, max 300 chars)
                </label>
                <textarea
                  id="feedback-comment"
                  value={feedbackComment}
                  onChange={(e) =>
                    setFeedbackComment(e.target.value.slice(0, 300))
                  }
                  maxLength={300}
                  rows={2}
                  placeholder="Describe your route experience..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-400 text-right">
                  {feedbackComment.length}/300
                </p>
              </div>
            )}

            {/* Feedback error */}
            {feedbackError && (
              <p className="text-xs text-red-600">{feedbackError}</p>
            )}

            {/* Feedback actions */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleFeedbackSubmit}
                disabled={!feedbackRating || feedbackSubmitting}
                className="min-h-[44px] min-w-[44px] flex-1 px-3 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {feedbackSubmitting ? 'Sending...' : 'Submit Feedback'}
              </button>
              <button
                type="button"
                onClick={handleSkipFeedback}
                className="min-h-[44px] min-w-[44px] px-3 py-2 bg-gray-200 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400"
              >
                Skip
              </button>
            </div>
          </div>
        )}

        {/* Session Feedback History */}
        {feedbackHistory.length > 0 && (
          <div className="border-t border-gray-200 pt-3">
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Session Feedback History
            </h4>
            <ul className="space-y-1.5">
              {feedbackHistory.map((entry, idx) => (
                <li
                  key={idx}
                  className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 px-2 py-1.5 rounded"
                >
                  <span className="text-base">{ratingIcon(entry.rating)}</span>
                  <span className="font-medium text-gray-700">
                    #{entry.journeyId}
                  </span>
                  {entry.comment && (
                    <span className="text-xs text-gray-500 truncate max-w-[150px]">
                      {entry.comment.slice(0, 50)}
                      {entry.comment.length > 50 ? '…' : ''}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
