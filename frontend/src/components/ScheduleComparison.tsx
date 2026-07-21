import { Schedule, Route, RouteStop } from '../types';

export interface ScheduleComparisonProps {
  current: Schedule | null;
  proposed: Schedule | null;
}

interface SavingsMetric {
  label: string;
  absolute: number;
  percent: number;
  unit: string;
}

/**
 * Compute savings between current and proposed schedules.
 */
export function computeSavings(current: Schedule, proposed: Schedule): SavingsMetric[] {
  const travelHoursSaved = current.totalTravelHours - proposed.totalTravelHours;
  const travelHoursPercent = current.totalTravelHours > 0
    ? (travelHoursSaved / current.totalTravelHours) * 100
    : 0;

  const mileageSaved = current.totalMileage - proposed.totalMileage;
  const mileagePercent = current.totalMileage > 0
    ? (mileageSaved / current.totalMileage) * 100
    : 0;

  const overtimeSaved = current.totalOvertimeHours - proposed.totalOvertimeHours;
  const overtimePercent = current.totalOvertimeHours > 0
    ? (overtimeSaved / current.totalOvertimeHours) * 100
    : 0;

  return [
    { label: 'Travel Hours', absolute: travelHoursSaved, percent: travelHoursPercent, unit: 'hrs' },
    { label: 'Mileage', absolute: mileageSaved, percent: mileagePercent, unit: 'mi' },
    { label: 'Overtime', absolute: overtimeSaved, percent: overtimePercent, unit: 'hrs' },
  ];
}

/**
 * Compute the total cost difference between current and proposed.
 */
export function computeCostDifference(current: Schedule, proposed: Schedule): {
  absolute: number;
  percent: number;
} {
  const absolute = current.totalCost - proposed.totalCost;
  const percent = current.totalCost > 0
    ? (absolute / current.totalCost) * 100
    : 0;
  return { absolute, percent };
}

/**
 * Build a map of visitId -> carerId from a schedule's routes.
 */
export function buildAssignmentMap(routes: Route[]): Map<number, number> {
  const map = new Map<number, number>();
  for (const route of routes) {
    for (const stop of route.stops) {
      map.set(stop.visitId, route.carerId);
    }
  }
  return map;
}

/**
 * Get the set of visitIds whose carer assignment changed between two schedules.
 */
export function getChangedVisitIds(current: Route[], proposed: Route[]): Set<number> {
  const currentMap = buildAssignmentMap(current);
  const proposedMap = buildAssignmentMap(proposed);
  const changed = new Set<number>();

  for (const [visitId, carerId] of proposedMap.entries()) {
    const currentCarerId = currentMap.get(visitId);
    if (currentCarerId !== undefined && currentCarerId !== carerId) {
      changed.add(visitId);
    }
  }

  return changed;
}

function SavingsCard({ metric }: { metric: SavingsMetric }) {
  const isPositive = metric.absolute > 0;
  const colorClass = isPositive ? 'text-green-700' : metric.absolute < 0 ? 'text-red-700' : 'text-gray-700';

  return (
    <div className="flex flex-col items-center rounded-lg bg-white px-4 py-3 shadow-sm border border-gray-100 min-w-[140px]">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        {metric.label}
      </span>
      <span className={`mt-1 text-lg font-semibold ${colorClass}`}>
        {isPositive ? '-' : metric.absolute < 0 ? '+' : ''}{Math.abs(metric.absolute).toFixed(1)} {metric.unit}
      </span>
      <span className={`text-sm ${colorClass}`}>
        {isPositive ? '-' : metric.absolute < 0 ? '+' : ''}{Math.abs(metric.percent).toFixed(1)}%
      </span>
    </div>
  );
}

function CostDifferenceCard({ absolute, percent }: { absolute: number; percent: number }) {
  const isPositive = absolute > 0;
  const colorClass = isPositive ? 'text-green-700 bg-green-50 border-green-200' : absolute < 0 ? 'text-red-700 bg-red-50 border-red-200' : 'text-gray-700 bg-gray-50 border-gray-200';

  return (
    <div className={`flex flex-col items-center rounded-lg px-6 py-4 border ${colorClass}`} aria-label="Total cost difference">
      <span className="text-xs font-medium uppercase tracking-wide opacity-80">
        Total Cost Savings
      </span>
      <span className="mt-1 text-2xl font-bold">
        {isPositive ? '-' : absolute < 0 ? '+' : ''}£{Math.abs(absolute).toFixed(2)}
      </span>
      <span className="text-sm">
        {isPositive ? '-' : absolute < 0 ? '+' : ''}{Math.abs(percent).toFixed(1)}%
      </span>
    </div>
  );
}

function RoutePanel({ routes, changedVisitIds, title }: { routes: Route[]; changedVisitIds: Set<number>; title: string }) {
  return (
    <div className="flex-1 min-w-0">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">{title}</h3>
      <div className="space-y-4">
        {routes.map((route) => (
          <div key={route.carerId} className="rounded-lg border border-gray-200 bg-white p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-800">
                Carer {route.carerId}
              </span>
              <span className="text-xs text-gray-500">
                {route.stops.length} visits • {route.totalTravelMinutes} min travel • {route.totalMileage.toFixed(1)} mi
              </span>
            </div>
            <div className="space-y-1">
              {sortStopsByTime(route.stops).map((stop) => {
                const isChanged = changedVisitIds.has(stop.visitId);
                return (
                  <div
                    key={stop.visitId}
                    className={`flex items-center justify-between rounded px-2 py-1 text-sm ${
                      isChanged ? 'bg-amber-100 border border-amber-300' : 'bg-gray-50'
                    }`}
                    aria-label={isChanged ? `Visit ${stop.visitId} - assignment changed` : `Visit ${stop.visitId}`}
                  >
                    <span className="font-mono text-xs text-gray-600">
                      {stop.startTime}–{stop.endTime}
                    </span>
                    <span className="text-gray-700">
                      Visit {stop.visitId} (Patient {stop.patientId})
                    </span>
                    {isChanged && (
                      <span className="text-xs font-medium text-amber-700" aria-hidden="true">
                        Changed
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Sort stops by startTime chronologically.
 */
function sortStopsByTime(stops: RouteStop[]): RouteStop[] {
  return [...stops].sort((a, b) => a.startTime.localeCompare(b.startTime));
}

export function ScheduleComparison({ current, proposed }: ScheduleComparisonProps) {
  if (!current || !proposed) {
    return (
      <div
        className="rounded-xl border border-gray-200 bg-white p-8 text-center"
        role="region"
        aria-label="Schedule Comparison"
      >
        <p className="text-gray-500">
          {!current && !proposed
            ? 'No schedule data available. Run an optimisation to see the comparison.'
            : !current
            ? 'Current schedule not available.'
            : 'Proposed schedule not available. Run an optimisation to generate a proposal.'}
        </p>
      </div>
    );
  }

  const savings = computeSavings(current, proposed);
  const costDiff = computeCostDifference(current, proposed);
  const changedVisitIds = getChangedVisitIds(current.routes, proposed.routes);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4" role="region" aria-label="Schedule Comparison">
      {/* Savings summary */}
      <div className="mb-6">
        <div className="flex flex-wrap items-center justify-center gap-3 mb-4">
          {savings.map((metric) => (
            <SavingsCard key={metric.label} metric={metric} />
          ))}
        </div>
        <div className="flex justify-center">
          <CostDifferenceCard absolute={costDiff.absolute} percent={costDiff.percent} />
        </div>
      </div>

      {/* Side-by-side schedules */}
      <div className="flex flex-col md:flex-row gap-4">
        <RoutePanel
          routes={current.routes}
          changedVisitIds={changedVisitIds}
          title="Current Schedule"
        />
        <RoutePanel
          routes={proposed.routes}
          changedVisitIds={changedVisitIds}
          title="Proposed Schedule"
        />
      </div>
    </div>
  );
}

export default ScheduleComparison;
