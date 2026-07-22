import { useState, useCallback } from 'react';
import { PlanBuilder } from '../components/sandbox/PlanBuilder';
import { CarerSimulationPanel } from '../components/sandbox/CarerSimulationPanel';
import { ComparisonView } from '../components/sandbox/ComparisonView';
import { StatusTimeline } from '../components/sandbox/StatusTimeline';
import { listJourneyPlans, deleteJourneyPlan, getJourneyHistory } from '../services/api';

/** Plan version entry for the history browser. */
interface PlanVersionEntry {
  version: number;
  createdAt: string;
  reason: string;
  journeyCount: number;
  isCurrent: boolean;
}

/**
 * JourneySandboxPage — Main sandbox testing page with three-panel layout.
 *
 * Desktop (≥768px): Grid with Plan Builder on left, Carer Simulation + Comparison on right.
 * Mobile (<768px): Stacks vertically: PlanBuilder → CarerSimulation → ComparisonView.
 *
 * Requirements: 1.1-1.4, 8.1-8.4, 9.1-9.4
 */
export default function JourneySandboxPage() {
  // StatusTimeline slide-over state
  const [selectedJourneyId, setSelectedJourneyId] = useState<number | null>(null);
  const [isTimelineOpen, setIsTimelineOpen] = useState(false);

  // Reset test data state
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [resetDayInput, setResetDayInput] = useState('');
  const [resetError, setResetError] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);

  // Shared refresh trigger — incremented to signal ComparisonView to refresh
  const [refreshKey, setRefreshKey] = useState(0);

  // Plan version history browser state
  const [historyDay, setHistoryDay] = useState('');
  const [planVersions, setPlanVersions] = useState<PlanVersionEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  /** Trigger a refresh of the ComparisonView. */
  const triggerRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  /** Handle plan creation — refresh comparison view. */
  const handlePlanCreated = useCallback(() => {
    triggerRefresh();
  }, [triggerRefresh]);

  /** Handle actual journey submission — refresh comparison view. */
  const handleActualSubmitted = useCallback(() => {
    triggerRefresh();
  }, [triggerRefresh]);

  /** Handle feedback submission (currently a no-op from page perspective). */
  const handleFeedbackSubmitted = useCallback(() => {
    // Could trigger notifications or refresh in future
  }, []);

  /** Handle journey selection from Plan Builder or Comparison View — open timeline. */
  const handleJourneySelected = useCallback((journey: { journeyId?: number; id?: number }) => {
    const id = journey.journeyId ?? journey.id;
    if (id != null) {
      setSelectedJourneyId(id);
      setIsTimelineOpen(true);
    }
  }, []);

  /** Close the StatusTimeline slide-over. */
  const handleTimelineClose = useCallback(() => {
    setIsTimelineOpen(false);
    setSelectedJourneyId(null);
  }, []);

  /** Open the reset confirmation dialog. */
  const handleResetClick = () => {
    setShowResetDialog(true);
    setResetDayInput('');
    setResetError(null);
  };

  /** Execute the reset: delete all plans for the specified operating day. */
  const handleResetConfirm = async () => {
    if (!resetDayInput.trim()) {
      setResetError('Please enter an operating day to confirm.');
      return;
    }

    setIsResetting(true);
    setResetError(null);

    try {
      // Fetch all plans for the operating day
      const plans = await listJourneyPlans({ operatingDay: resetDayInput.trim() });
      const planList = Array.isArray(plans) ? plans : [];

      if (planList.length === 0) {
        setResetError(`No plans found for ${resetDayInput.trim()}.`);
        setIsResetting(false);
        return;
      }

      // Attempt to delete each plan
      const errors: string[] = [];
      for (const plan of planList) {
        try {
          await deleteJourneyPlan(plan.id);
        } catch (err: unknown) {
          const errorMsg = extractErrorMessage(err, plan.id);
          errors.push(errorMsg);
        }
      }

      if (errors.length > 0) {
        setResetError(`Some plans could not be deleted:\n${errors.join('\n')}`);
      } else {
        setShowResetDialog(false);
        triggerRefresh();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Reset operation failed. Please try again.';
      setResetError(msg);
    } finally {
      setIsResetting(false);
    }
  };

  /** Cancel the reset dialog. */
  const handleResetCancel = () => {
    setShowResetDialog(false);
    setResetDayInput('');
    setResetError(null);
  };

  /** Fetch plan version history for the selected day. */
  const handleFetchHistory = async () => {
    if (!historyDay) return;
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const history = await getJourneyHistory(historyDay);
      const versions: PlanVersionEntry[] = Array.isArray(history)
        ? history.map((h: Record<string, unknown>, idx: number, arr: Record<string, unknown>[]) => ({
            version: (h.version as number) ?? idx + 1,
            createdAt: (h.createdAt as string) ?? '',
            reason: (h.reason as string) ?? 'unknown',
            journeyCount: (h.journeyCount as number) ?? 0,
            isCurrent: idx === arr.length - 1,
          }))
        : [];
      setPlanVersions(versions);
    } catch {
      setHistoryError('Failed to load version history.');
      setPlanVersions([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Sandbox Banner - Requirement 9.2 */}
      <div className="bg-amber-100 border-b border-amber-300 px-4 py-3 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-amber-700 font-semibold text-sm" aria-live="polite">
            ⚠️ Sandbox Mode – operations affect the live database
          </span>
        </div>
        <button
          onClick={handleResetClick}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-md hover:bg-red-100 transition-colors"
          aria-label="Reset test data"
        >
          🗑️ Reset Test Data
        </button>
      </div>

      {/* Three-panel layout - Requirements 1.2, 1.4 */}
      <div className="flex-1 p-4 md:p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6" key={refreshKey}>
          {/* Left column: Plan Builder */}
          <div className="md:row-span-2">
            <PlanBuilder
              onPlanCreated={handlePlanCreated}
              onJourneySelected={handleJourneySelected}
            />
          </div>

          {/* Right top: Carer Simulation Panel */}
          <div>
            <CarerSimulationPanel
              onActualSubmitted={handleActualSubmitted}
              onFeedbackSubmitted={handleFeedbackSubmitted}
            />
          </div>

          {/* Right bottom: Comparison View */}
          <div>
            <ComparisonView
              onJourneySelected={handleJourneySelected}
            />
          </div>
        </div>

        {/* Plan Version History Browser - Requirements 8.1-8.4 */}
        <div className="mt-6 bg-white rounded-lg border border-gray-200 shadow-sm">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Plan Version History</h3>
            <p className="text-xs text-gray-500 mt-0.5">Browse version timeline for a selected operating day</p>
          </div>
          <div className="px-4 py-3">
            <div className="flex items-end gap-3 flex-wrap">
              <div>
                <label htmlFor="history-day" className="block text-xs font-medium text-gray-600 mb-1">
                  Operating Day
                </label>
                <input
                  id="history-day"
                  type="date"
                  value={historyDay}
                  onChange={(e) => setHistoryDay(e.target.value)}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <button
                onClick={handleFetchHistory}
                disabled={!historyDay || historyLoading}
                className="px-3 py-1.5 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {historyLoading ? 'Loading...' : 'Load History'}
              </button>
            </div>

            {/* History error */}
            {historyError && (
              <p className="mt-3 text-sm text-red-600">{historyError}</p>
            )}

            {/* Empty state for history */}
            {!historyLoading && !historyError && planVersions.length === 0 && historyDay && (
              <p className="mt-4 text-sm text-gray-500 text-center py-4">
                No plan versions found. Select an operating day and click "Load History".
              </p>
            )}

            {/* Version timeline */}
            {planVersions.length > 0 && (
              <div className="mt-4 space-y-3">
                {planVersions.map((pv) => (
                  <div
                    key={pv.version}
                    className={`flex items-start gap-3 p-3 rounded-md border ${
                      pv.isCurrent
                        ? 'border-blue-300 bg-blue-50'
                        : 'border-gray-200 bg-gray-50'
                    }`}
                  >
                    {/* Timeline dot */}
                    <div className={`mt-1 w-3 h-3 rounded-full flex-shrink-0 ${
                      pv.isCurrent ? 'bg-blue-500' : 'bg-gray-400'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-gray-900">
                          Version {pv.version}
                        </span>
                        {pv.isCurrent && (
                          <span className="text-xs font-medium text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded">
                            Current
                          </span>
                        )}
                        {!pv.isCurrent && (
                          <span className="text-xs font-medium text-gray-500 bg-gray-200 px-1.5 py-0.5 rounded">
                            Archived
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-600 mt-0.5">
                        {pv.reason} • {pv.journeyCount} journey{pv.journeyCount !== 1 ? 's' : ''}
                      </p>
                      {pv.createdAt && (
                        <p className="text-xs text-gray-400 mt-0.5">
                          {new Date(pv.createdAt).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* StatusTimeline slide-over - Requirement 7.1 */}
      {selectedJourneyId !== null && (
        <StatusTimeline
          journeyId={selectedJourneyId}
          isOpen={isTimelineOpen}
          onClose={handleTimelineClose}
        />
      )}

      {/* Reset Confirmation Dialog - Requirement 9.3, 9.4 */}
      {showResetDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-labelledby="reset-dialog-title">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h2 id="reset-dialog-title" className="text-lg font-bold text-gray-900 mb-2">
              Reset Test Data
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              This will delete all journey plans for the specified operating day. This action cannot be undone.
            </p>
            <div className="mb-4">
              <label htmlFor="reset-day-input" className="block text-sm font-medium text-gray-700 mb-1">
                Type the operating day (YYYY-MM-DD) to confirm:
              </label>
              <input
                id="reset-day-input"
                type="text"
                value={resetDayInput}
                onChange={(e) => setResetDayInput(e.target.value)}
                placeholder="e.g. 2026-08-01"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500"
                autoFocus
              />
            </div>

            {/* Reset error display */}
            {resetError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm text-red-700 whitespace-pre-line">{resetError}</p>
              </div>
            )}

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={handleResetCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200 transition-colors"
                disabled={isResetting}
              >
                Cancel
              </button>
              <button
                onClick={handleResetConfirm}
                disabled={isResetting || !resetDayInput.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-red-700 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isResetting ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Extract a descriptive error message from an API error for plan deletion. */
function extractErrorMessage(err: unknown, planId: number): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const response = (err as { response?: { data?: { message?: string; detail?: string; blockingJourneyIds?: number[] } } }).response;
    if (response?.data) {
      const { message, detail, blockingJourneyIds } = response.data;
      const msg = message || detail || 'Unknown error';
      if (blockingJourneyIds && blockingJourneyIds.length > 0) {
        return `Plan ${planId}: ${msg} (blocking journeys: ${blockingJourneyIds.join(', ')})`;
      }
      return `Plan ${planId}: ${msg}`;
    }
  }
  return `Plan ${planId}: Failed to delete`;
}
