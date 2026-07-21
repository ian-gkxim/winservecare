import { useState, useEffect, useCallback } from 'react';
import ErrorBanner from '../components/ErrorBanner';
import { getScenarios, compareScenarios } from '../services/api';
import type { ScenarioSummary, ScenarioComparison } from '../types';

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [comparison, setComparison] = useState<ScenarioComparison | null>(null);
  const [comparing, setComparing] = useState(false);

  const fetchScenarios = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getScenarios();
      setScenarios(data);
    } catch {
      setErrorMessage('Failed to load scenarios.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScenarios();
  }, [fetchScenarios]);

  const handleCheckboxChange = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= 2) {
          // Replace the oldest selection with the new one
          const [first] = next;
          next.delete(first);
        }
        next.add(id);
      }
      return next;
    });
  };

  const handleCompare = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length !== 2) return;

    try {
      setComparing(true);
      setErrorMessage(null);
      const result = await compareScenarios(ids);
      setComparison(result);
    } catch {
      setErrorMessage('Failed to compare scenarios.');
    } finally {
      setComparing(false);
    }
  };

  const handleBackToList = () => {
    setComparison(null);
  };

  const canCompare = selectedIds.size === 2 && scenarios.length >= 2;

  if (comparison) {
    return <ComparisonView comparison={comparison} onBack={handleBackToList} />;
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scenarios</h1>
          <p className="mt-1 text-sm text-gray-600">
            Compare saved optimisation scenarios side by side.
          </p>
        </div>
        <button
          onClick={handleCompare}
          disabled={!canCompare || comparing}
          className={`px-4 py-2 rounded-md text-sm font-medium ${
            canCompare && !comparing
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
          aria-label="Compare selected scenarios"
        >
          {comparing ? 'Comparing...' : 'Compare'}
        </button>
      </div>

      {errorMessage && (
        <div className="mb-4">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        </div>
      )}

      {scenarios.length < 2 && !loading && (
        <div className="mb-4 px-4 py-3 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-800 text-sm">
          At least two saved scenarios are required to use comparison.
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading scenarios...</p>
      ) : (
        <ScenarioTable
          scenarios={scenarios}
          selectedIds={selectedIds}
          onCheckboxChange={handleCheckboxChange}
        />
      )}
    </div>
  );
}

// --- Scenario Table ---

interface ScenarioTableProps {
  scenarios: ScenarioSummary[];
  selectedIds: Set<number>;
  onCheckboxChange: (id: number) => void;
}

function ScenarioTable({ scenarios, selectedIds, onCheckboxChange }: ScenarioTableProps) {
  if (scenarios.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-gray-500">
        No scenarios saved yet. Run an optimisation and save the result to create a scenario.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200" role="grid">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-10">
              <span className="sr-only">Select</span>
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Name
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Travel Hours
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Mileage
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Overtime
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Continuity
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Created
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {scenarios.map((scenario, idx) => (
            <tr
              key={scenario.id}
              className={`${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'} hover:bg-blue-50`}
            >
              <td className="px-4 py-3">
                <input
                  type="checkbox"
                  checked={selectedIds.has(scenario.id)}
                  onChange={() => onCheckboxChange(scenario.id)}
                  className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  aria-label={`Select ${scenario.name} for comparison`}
                />
              </td>
              <td className="px-4 py-3 text-sm font-medium text-gray-900">
                {scenario.name}
              </td>
              <td className="px-4 py-3 text-sm text-gray-700">
                {scenario.totalTravelHours.toFixed(1)} hrs
              </td>
              <td className="px-4 py-3 text-sm text-gray-700">
                {scenario.totalMileage.toFixed(1)} mi
              </td>
              <td className="px-4 py-3 text-sm text-gray-700">
                {scenario.totalOvertimeHours.toFixed(1)} hrs
              </td>
              <td className="px-4 py-3 text-sm text-gray-700">
                {scenario.continuityScore.toFixed(0)}%
              </td>
              <td className="px-4 py-3 text-sm text-gray-500">
                {new Date(scenario.createdAt).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Comparison View ---

interface ComparisonViewProps {
  comparison: ScenarioComparison;
  onBack: () => void;
}

function ComparisonView({ comparison, onBack }: ComparisonViewProps) {
  const { scenario1, scenario2, differences, changedVisits } = comparison;

  return (
    <div className="p-6">
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={onBack}
          className="px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
          aria-label="Back to scenarios list"
        >
          ← Back
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Scenario Comparison</h1>
      </div>

      {/* Side-by-side metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <MetricCard title={scenario1.name} scenario={scenario1} />
        <MetricCard title={scenario2.name} scenario={scenario2} />
      </div>

      {/* Differences table */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Metric Differences</h2>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200" role="grid">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Metric
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  {scenario1.name}
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  {scenario2.name}
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Difference
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {differences.map((diff) => {
                const hasDiff = diff.absoluteDiff !== 0;
                return (
                  <tr
                    key={diff.metric}
                    className={hasDiff ? 'bg-amber-50' : 'bg-white'}
                  >
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 capitalize">
                      {formatMetricName(diff.metric)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {diff.value1.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {diff.value2.toFixed(1)}
                    </td>
                    <td className={`px-4 py-3 text-sm font-medium ${hasDiff ? 'text-amber-700' : 'text-gray-400'}`}>
                      {hasDiff
                        ? `${diff.absoluteDiff > 0 ? '+' : ''}${diff.absoluteDiff.toFixed(1)} (${diff.percentageDiff > 0 ? '+' : ''}${diff.percentageDiff.toFixed(1)}%)`
                        : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Changed visit assignments */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Changed Visit Assignments
          <span className="ml-2 text-sm font-normal text-gray-500">
            ({changedVisits.length} visit{changedVisits.length !== 1 ? 's' : ''} differ)
          </span>
        </h2>
        {changedVisits.length === 0 ? (
          <p className="text-sm text-gray-500">
            All visits have identical carer assignments in both scenarios.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200" role="grid">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Visit ID
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Carer in {scenario1.name}
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Carer in {scenario2.name}
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {changedVisits.map((visitId) => {
                  const assignment1 = scenario1.assignments.find((a) => a.visitId === visitId);
                  const assignment2 = scenario2.assignments.find((a) => a.visitId === visitId);
                  return (
                    <tr key={visitId} className="bg-orange-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        Visit #{visitId}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        Carer #{assignment1?.carerId ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        Carer #{assignment2?.carerId ?? '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Metric Card ---

interface MetricCardProps {
  title: string;
  scenario: {
    totalTravelHours: number;
    totalMileage: number;
    totalOvertimeHours: number;
    continuityScore: number;
  };
}

function MetricCard({ title, scenario }: MetricCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <h3 className="text-md font-semibold text-gray-900 mb-4">{title}</h3>
      <dl className="grid grid-cols-2 gap-4">
        <div>
          <dt className="text-xs text-gray-500 uppercase">Travel Hours</dt>
          <dd className="text-lg font-medium text-gray-900">
            {scenario.totalTravelHours.toFixed(1)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500 uppercase">Mileage</dt>
          <dd className="text-lg font-medium text-gray-900">
            {scenario.totalMileage.toFixed(1)} mi
          </dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500 uppercase">Overtime</dt>
          <dd className="text-lg font-medium text-gray-900">
            {scenario.totalOvertimeHours.toFixed(1)} hrs
          </dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500 uppercase">Continuity</dt>
          <dd className="text-lg font-medium text-gray-900">
            {scenario.continuityScore.toFixed(0)}%
          </dd>
        </div>
      </dl>
    </div>
  );
}

// --- Helpers ---

function formatMetricName(metric: string): string {
  const names: Record<string, string> = {
    totalTravelHours: 'Travel Hours',
    totalMileage: 'Mileage',
    totalOvertimeHours: 'Overtime',
    continuityScore: 'Continuity Score',
  };
  return names[metric] ?? metric.replace(/([A-Z])/g, ' $1').trim();
}
