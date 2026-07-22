import { useCallback, useEffect, useState } from 'react';
import { KPIRibbon } from '../components/KPIRibbon';
import { AnimatedMap } from '../components/AnimatedMap';
import { MapControls } from '../components/MapControls';
import { ProgressPanel } from '../components/ProgressPanel';
import { ScheduleComparison } from '../components/ScheduleComparison';
import { RecommendationsPanel } from '../components/RecommendationsPanel';
import { CompletionNotification } from '../components/CompletionNotification';
import { useOptimisation } from '../hooks/useOptimisation';
import { getKpis, generateVisits, getVisitsByDate } from '../services/api';
import type { KPIMetrics, Schedule, Recommendation } from '../types';

/** Compute default target date: today if weekday, next Monday if weekend. */
function getDefaultDate(): string {
  const today = new Date();
  const day = today.getDay(); // 0=Sun, 6=Sat
  if (day === 0) today.setDate(today.getDate() + 1); // Sun → Mon
  if (day === 6) today.setDate(today.getDate() + 2); // Sat → Mon
  return today.toISOString().split('T')[0];
}

function getTodayString(): string {
  return new Date().toISOString().split('T')[0];
}

/** Step names corresponding to the 8-step optimisation pipeline */
const STEP_NAMES = [
  'Loading Locations',
  'Computing Distance Matrix',
  'Generating Assignments',
  'Pruning Infeasible',
  'Evaluating Routes',
  'Improving Solution',
  'Finalising Solution',
  'Animating Routes',
];

export default function DashboardPage() {
  const [kpis, setKpis] = useState<KPIMetrics | null>(null);
  const [showCompletion, setShowCompletion] = useState(false);
  const [targetDate, setTargetDate] = useState(getDefaultDate);
  const [dateError, setDateError] = useState<string | null>(null);
  const [scheduledCount, setScheduledCount] = useState<number | null>(null);
  const [noVisitsMessage, setNoVisitsMessage] = useState<string | null>(null);

  const {
    isRunning,
    isPaused,
    currentStep,
    steps,
    progress,
    result,
    error,
    solverProgress,
    startOptimisation,
    pause,
    resume,
  } = useOptimisation();

  // Fetch KPIs on mount
  useEffect(() => {
    getKpis()
      .then(setKpis)
      .catch(() => {
        // KPIs unavailable — ribbon will show placeholders
      });
  }, []);

  // Refetch KPIs when optimisation completes and show completion notification
  useEffect(() => {
    if (result) {
      setShowCompletion(true);
      getKpis()
        .then(setKpis)
        .catch(() => {});
    }
  }, [result]);

  // Load or generate visits when target date changes
  useEffect(() => {
    let cancelled = false;

    async function loadVisitsForDate() {
      setNoVisitsMessage(null);
      setDateError(null);

      try {
        // First try to fetch existing visits for the date
        const data = await getVisitsByDate(targetDate);
        const visits = Array.isArray(data) ? data : data.visits ?? [];
        const scheduled = visits.filter((v: { isCancelled: boolean }) => !v.isCancelled).length;

        if (visits.length === 0) {
          // No visits exist yet — generate them
          const genResult = await generateVisits(targetDate);
          const generatedVisits = genResult.visits ?? [];
          const generatedScheduled = generatedVisits.filter((v: { isCancelled: boolean }) => !v.isCancelled).length;

          if (!cancelled) {
            setScheduledCount(generatedScheduled);
            if (generatedScheduled === 0) {
              setNoVisitsMessage('No scheduled visits exist for this date. Check that care contracts are active.');
            }
          }
        } else {
          if (!cancelled) {
            setScheduledCount(scheduled);
            if (scheduled === 0) {
              setNoVisitsMessage('No scheduled visits exist for this date. All visits may be cancelled.');
            }
          }
        }
      } catch {
        if (!cancelled) {
          setScheduledCount(null);
          setNoVisitsMessage('Failed to load visits for the selected date.');
        }
      }
    }

    loadVisitsForDate();
    return () => { cancelled = true; };
  }, [targetDate]);

  const handleDateChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newDate = e.target.value;
    if (newDate < getTodayString()) {
      setDateError('Past dates are not permitted.');
      return;
    }
    setDateError(null);
    setTargetDate(newDate);
  }, []);

  const handleDismissCompletion = useCallback(() => {
    setShowCompletion(false);
  }, []);

  const handleRunOptimisation = useCallback(() => {
    setShowCompletion(false);
    startOptimisation(undefined, targetDate);
  }, [startOptimisation, targetDate]);

  // Derive step name from current step
  const stepName = currentStep >= 1 && currentStep <= STEP_NAMES.length
    ? STEP_NAMES[currentStep - 1]
    : '';

  // Build proposed schedule from result
  const proposedSchedule: Schedule | null = result
    ? {
        routes: result.routes,
        totalTravelHours: result.routes.reduce((sum, r) => sum + r.totalTravelMinutes / 60, 0),
        totalMileage: result.routes.reduce((sum, r) => sum + r.totalMileage, 0),
        totalOvertimeHours: 0,
        continuityScore: 0,
        totalCost: result.routes.reduce((sum, r) => sum + r.totalCost, 0),
      }
    : null;

  // Recommendations from optimisation result (if available)
  const recommendations: Recommendation[] = [];

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Top: KPI Ribbon (full width) */}
      <KPIRibbon metrics={kpis} />

      {/* Date picker and Run Optimisation button */}
      <div className="flex flex-col gap-3">
        <div className="flex items-end justify-between gap-4">
          <div className="flex items-end gap-4">
            <div>
              <label htmlFor="dashboard-target-date" className="block text-sm font-medium text-gray-700 mb-1">
                Target Date
              </label>
              <input
                id="dashboard-target-date"
                type="date"
                value={targetDate}
                min={getTodayString()}
                onChange={handleDateChange}
                className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Optimisation Dashboard</h1>
          </div>
          <button
            onClick={handleRunOptimisation}
            disabled={isRunning || scheduledCount === 0}
            className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            aria-label="Run optimisation"
          >
            {isRunning ? 'Optimising...' : 'Run Optimisation'}
          </button>
        </div>

        {/* Date validation error */}
        {dateError && (
          <p className="text-sm text-red-600 font-medium">{dateError}</p>
        )}

        {/* No visits warning */}
        {noVisitsMessage && !dateError && (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            {noVisitsMessage}
          </p>
        )}

        {/* Scheduled visits count */}
        {scheduledCount !== null && scheduledCount > 0 && !dateError && (
          <p className="text-sm text-gray-600">
            <span className="font-medium text-green-700">{scheduledCount} scheduled visit{scheduledCount !== 1 ? 's' : ''}</span> for {targetDate}
          </p>
        )}
      </div>

      {/* Middle row: Map (2/3) + Progress/Completion (1/3) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Map column (2/3 width) */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="h-[480px] rounded-lg border border-gray-200 overflow-hidden">
            <AnimatedMap
              steps={steps}
              isRunning={isRunning}
              isPaused={isPaused}
              currentStep={currentStep}
            />
          </div>
          <MapControls
            isPaused={isPaused}
            isRunning={isRunning}
            currentStep={currentStep}
            stepName={stepName}
            onPause={pause}
            onResume={resume}
          />
        </div>

        {/* Right column (1/3 width): Progress or Completion */}
        <div className="flex flex-col gap-4">
          {showCompletion && result ? (
            <CompletionNotification
              score={result.finalScore}
              onDismiss={handleDismissCompletion}
            />
          ) : null}
          <ProgressPanel
            currentStep={currentStep}
            stepName={stepName}
            score={progress}
            isRunning={isRunning}
            error={error}
            solverProgress={solverProgress}
          />
        </div>
      </div>

      {/* Bottom row: ScheduleComparison (2/3) + Recommendations (1/3) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ScheduleComparison
            current={null}
            proposed={proposedSchedule}
          />
        </div>
        <div>
          <RecommendationsPanel items={recommendations} />
        </div>
      </div>
    </div>
  );
}
