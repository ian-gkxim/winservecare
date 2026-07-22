import { useState, useEffect, useCallback } from 'react';
import { getJourneyComparison, getJourneyHistory } from '../../services/api';

/** A single comparison entry returned from the API. */
export interface ComparisonEntry {
  journeyId: number;
  carerId: number;
  carerName: string;
  plannedDeparture: string | null;
  plannedArrival: string | null;
  actualDeparture: string | null;
  actualArrival: string | null;
  departureVarianceMinutes: number | null;
  arrivalVarianceMinutes: number | null;
  plannedDistanceMiles: number | null;
  actualDistanceMiles: number | null;
  distanceVarianceMiles: number | null;
  matchStatus: 'matched' | 'unstarted' | 'unplanned';
}

/** A plan version entry from journey history. */
export interface PlanVersion {
  version: number;
  createdAt: string;
  reason: string;
}

export interface ComparisonViewProps {
  onJourneySelected: (journey: ComparisonEntry) => void;
}

/** Returns the Tailwind colour class for a variance value in minutes. */
export function getVarianceColor(minutes: number | null): string {
  if (minutes === null) return 'text-gray-400';
  if (minutes <= 0) return 'text-green-600';
  return 'text-red-600';
}

/** Format a datetime string to a short time display. */
function formatTime(datetime: string | null): string {
  if (!datetime) return '—';
  try {
    return new Date(datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '—';
  }
}

/** Format variance with sign. */
function formatVariance(minutes: number | null): string {
  if (minutes === null) return '—';
  const sign = minutes > 0 ? '+' : '';
  return `${sign}${minutes} min`;
}

/** Format distance variance. */
function formatDistanceVariance(miles: number | null): string {
  if (miles === null) return '—';
  const sign = miles > 0 ? '+' : '';
  return `${sign}${miles.toFixed(1)} mi`;
}

/** Get today's date as YYYY-MM-DD. */
function getTodayString(): string {
  return new Date().toISOString().split('T')[0];
}

/**
 * ComparisonView — Real-time plan vs actual comparison display.
 * Shows journey comparison entries grouped by carer for a selected operating day.
 */
export function ComparisonView({ onJourneySelected }: ComparisonViewProps) {
  const [operatingDay, setOperatingDay] = useState(getTodayString());
  const [planVersions, setPlanVersions] = useState<PlanVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | undefined>(undefined);
  const [entries, setEntries] = useState<ComparisonEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Fetch plan versions for the selected operating day. */
  const fetchPlanVersions = useCallback(async (day: string) => {
    try {
      const history = await getJourneyHistory(day);
      const versions: PlanVersion[] = Array.isArray(history)
        ? history.map((h: Record<string, unknown>) => ({
            version: h.version as number,
            createdAt: h.createdAt as string,
            reason: (h.reason as string) || 'unknown',
          }))
        : [];
      setPlanVersions(versions);
      setSelectedVersion(undefined);
    } catch {
      setPlanVersions([]);
      setSelectedVersion(undefined);
    }
  }, []);

  /** Fetch comparison data for the selected day and version. */
  const fetchComparison = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getJourneyComparison(operatingDay, selectedVersion);
      const comparisonEntries: ComparisonEntry[] = Array.isArray(data)
        ? data.map((entry: Record<string, unknown>) => ({
            journeyId: entry.journeyId as number,
            carerId: entry.carerId as number,
            carerName: (entry.carerName as string) || `Carer ${entry.carerId}`,
            plannedDeparture: (entry.plannedDeparture as string) || null,
            plannedArrival: (entry.plannedArrival as string) || null,
            actualDeparture: (entry.actualDeparture as string) || null,
            actualArrival: (entry.actualArrival as string) || null,
            departureVarianceMinutes: entry.departureVarianceMinutes as number | null,
            arrivalVarianceMinutes: entry.arrivalVarianceMinutes as number | null,
            plannedDistanceMiles: entry.plannedDistanceMiles as number | null,
            actualDistanceMiles: entry.actualDistanceMiles as number | null,
            distanceVarianceMiles: entry.distanceVarianceMiles as number | null,
            matchStatus: (entry.matchStatus as 'matched' | 'unstarted' | 'unplanned') || 'matched',
          }))
        : [];
      setEntries(comparisonEntries);
    } catch {
      setError('Failed to load comparison data');
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [operatingDay, selectedVersion]);

  // Fetch plan versions when operating day changes
  useEffect(() => {
    if (operatingDay) {
      fetchPlanVersions(operatingDay);
    }
  }, [operatingDay, fetchPlanVersions]);

  // Fetch comparison data when operating day or version changes
  useEffect(() => {
    if (operatingDay) {
      fetchComparison();
    }
  }, [operatingDay, selectedVersion, fetchComparison]);

  /** Handle operating day change. */
  const handleDayChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setOperatingDay(e.target.value);
  };

  /** Handle plan version selection. */
  const handleVersionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setSelectedVersion(value ? Number(value) : undefined);
  };

  /** Refresh button handler — re-fetches comparison without page reload. */
  const handleRefresh = () => {
    fetchComparison();
  };

  /** Group entries by carer. */
  const groupedEntries = entries.reduce<Record<string, ComparisonEntry[]>>((acc, entry) => {
    const key = entry.carerName;
    if (!acc[key]) acc[key] = [];
    acc[key].push(entry);
    return acc;
  }, {});

  /** Get border/styling classes for an entry based on its match status. */
  function getEntryClasses(entry: ComparisonEntry): string {
    if (entry.matchStatus === 'unstarted') {
      return 'border-dashed border-gray-300 bg-gray-50 opacity-70';
    }
    if (entry.matchStatus === 'unplanned') {
      return 'border-solid border-amber-400 bg-amber-50';
    }
    return 'border-solid border-gray-200 bg-white';
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-lg font-semibold text-gray-900">Comparison View</h3>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            aria-label="Refresh comparison data"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>

        {/* Controls row */}
        <div className="flex items-end gap-4 mt-3 flex-wrap">
          {/* Operating day selector */}
          <div>
            <label htmlFor="comparison-day" className="block text-xs font-medium text-gray-600 mb-1">
              Operating Day
            </label>
            <input
              id="comparison-day"
              type="date"
              value={operatingDay}
              onChange={handleDayChange}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Plan version dropdown */}
          <div>
            <label htmlFor="comparison-version" className="block text-xs font-medium text-gray-600 mb-1">
              Plan Version
            </label>
            <select
              id="comparison-version"
              value={selectedVersion ?? ''}
              onChange={handleVersionChange}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Latest</option>
              {planVersions.map((pv) => (
                <option key={pv.version} value={pv.version}>
                  v{pv.version} — {pv.reason}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {/* Loading state */}
        {loading && (
          <p className="text-sm text-gray-500 py-4 text-center">Loading comparison data...</p>
        )}

        {/* Error state */}
        {error && !loading && (
          <p className="text-sm text-red-600 py-4 text-center">{error}</p>
        )}

        {/* Empty state */}
        {!loading && !error && entries.length === 0 && (
          <div className="py-8 text-center">
            <p className="text-sm text-gray-500">No data available for that date</p>
          </div>
        )}

        {/* Comparison entries grouped by carer */}
        {!loading && !error && entries.length > 0 && (
          <div className="space-y-4">
            {Object.entries(groupedEntries).map(([carerName, carerEntries]) => (
              <div key={carerName}>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">{carerName}</h4>
                <div className="space-y-2">
                  {carerEntries.map((entry) => (
                    <button
                      key={entry.journeyId}
                      type="button"
                      onClick={() => onJourneySelected(entry)}
                      className={`w-full text-left p-3 rounded-md border ${getEntryClasses(entry)} hover:shadow-sm transition-shadow cursor-pointer`}
                      aria-label={`Journey ${entry.journeyId} for ${entry.carerName}`}
                    >
                      {/* Status labels */}
                      {entry.matchStatus === 'unstarted' && (
                        <span className="inline-block text-xs font-medium text-gray-500 bg-gray-200 px-2 py-0.5 rounded mb-2">
                          Not yet started
                        </span>
                      )}
                      {entry.matchStatus === 'unplanned' && (
                        <span className="inline-block text-xs font-medium text-amber-700 bg-amber-200 px-2 py-0.5 rounded mb-2">
                          Unplanned journey
                        </span>
                      )}

                      {/* Data grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                        {/* Planned times */}
                        <div>
                          <span className="block text-gray-500">Planned Dep.</span>
                          <span className="font-medium text-gray-800">{formatTime(entry.plannedDeparture)}</span>
                        </div>
                        <div>
                          <span className="block text-gray-500">Planned Arr.</span>
                          <span className="font-medium text-gray-800">{formatTime(entry.plannedArrival)}</span>
                        </div>

                        {/* Actual times */}
                        <div>
                          <span className="block text-gray-500">Actual Dep.</span>
                          <span className="font-medium text-gray-800">{formatTime(entry.actualDeparture)}</span>
                        </div>
                        <div>
                          <span className="block text-gray-500">Actual Arr.</span>
                          <span className="font-medium text-gray-800">{formatTime(entry.actualArrival)}</span>
                        </div>

                        {/* Variances */}
                        <div>
                          <span className="block text-gray-500">Dep. Variance</span>
                          <span className={`font-medium ${getVarianceColor(entry.departureVarianceMinutes)}`}>
                            {formatVariance(entry.departureVarianceMinutes)}
                          </span>
                        </div>
                        <div>
                          <span className="block text-gray-500">Arr. Variance</span>
                          <span className={`font-medium ${getVarianceColor(entry.arrivalVarianceMinutes)}`}>
                            {formatVariance(entry.arrivalVarianceMinutes)}
                          </span>
                        </div>
                        <div>
                          <span className="block text-gray-500">Dist. Variance</span>
                          <span className="font-medium text-gray-700">
                            {formatDistanceVariance(entry.distanceVarianceMiles)}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
