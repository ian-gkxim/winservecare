import { useState, useEffect, useCallback } from 'react';
import ErrorBanner from '../components/ErrorBanner';
import ConfirmationToast from '../components/ConfirmationToast';
import { getVisitsByDate, generateVisits, regenerateVisits, cancelVisit, getPatients } from '../services/api';
import type { Visit, Patient } from '../types';

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

export default function VisitsPage() {
  const [targetDate, setTargetDate] = useState(getDefaultDate);
  const [visits, setVisits] = useState<Visit[]>([]);
  const [patients, setPatients] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchPatients = useCallback(async () => {
    try {
      const data = await getPatients();
      const map: Record<number, string> = {};
      data.forEach((p: Patient) => { map[p.id] = p.name; });
      setPatients(map);
    } catch {
      // Non-critical — visits will show IDs instead of names
    }
  }, []);

  const fetchVisits = useCallback(async (date: string) => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const data = await getVisitsByDate(date);
      setVisits(Array.isArray(data) ? data : data.visits ?? []);
    } catch {
      setErrorMessage('Failed to load visits for the selected date.');
      setVisits([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  useEffect(() => {
    fetchVisits(targetDate);
  }, [targetDate, fetchVisits]);

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTargetDate(e.target.value);
    setErrorMessage(null);
  };

  const isPastDate = (date: string): boolean => {
    return date < getTodayString();
  };

  const handleGenerate = async () => {
    if (isPastDate(targetDate)) {
      setErrorMessage('Cannot generate visits for a past date.');
      return;
    }
    try {
      setGenerating(true);
      setErrorMessage(null);
      const result = await generateVisits(targetDate);
      setVisits(result.visits ?? []);
      setToastMessage(`Generated ${result.scheduledCount ?? result.visits?.length ?? 0} visits.`);
    } catch {
      setErrorMessage('Failed to generate visits. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleRegenerate = async () => {
    if (isPastDate(targetDate)) {
      setErrorMessage('Cannot regenerate visits for a past date.');
      return;
    }
    try {
      setGenerating(true);
      setErrorMessage(null);
      const result = await regenerateVisits(targetDate);
      setVisits(result.visits ?? []);
      setToastMessage(`Regenerated ${result.scheduledCount ?? result.visits?.length ?? 0} visits.`);
    } catch {
      setErrorMessage('Failed to regenerate visits. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleCancel = async (visitId: number) => {
    try {
      setErrorMessage(null);
      await cancelVisit(visitId);
      setVisits((prev) =>
        prev.map((v) => (v.id === visitId ? { ...v, isCancelled: true } : v))
      );
      setToastMessage('Visit cancelled.');
    } catch {
      setErrorMessage('Failed to cancel visit. Please try again.');
    }
  };

  const scheduledCount = visits.filter((v) => !v.isCancelled).length;
  const cancelledCount = visits.filter((v) => v.isCancelled).length;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Visits</h1>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4 mb-6">
        <div>
          <label htmlFor="target-date" className="block text-sm font-medium text-gray-700 mb-1">
            Target Date
          </label>
          <input
            id="target-date"
            type="date"
            value={targetDate}
            onChange={handleDateChange}
            className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          {generating ? 'Generating...' : 'Generate Visits'}
        </button>
        <button
          onClick={handleRegenerate}
          disabled={generating || visits.length === 0}
          className="px-4 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          Regenerate
        </button>
      </div>

      {/* Error */}
      {errorMessage && (
        <div className="mb-4">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        </div>
      )}

      {/* Summary */}
      {visits.length > 0 && (
        <p className="text-sm text-gray-600 mb-4">
          <span className="font-medium text-green-700">{scheduledCount} scheduled</span>
          {' / '}
          <span className="font-medium text-red-700">{cancelledCount} cancelled</span>
        </p>
      )}

      {/* Table or empty state */}
      {loading ? (
        <p className="text-gray-500">Loading visits...</p>
      ) : visits.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
          <p className="text-gray-500 text-lg mb-2">No visits for this date</p>
          <p className="text-gray-400 text-sm">
            Select a date and click "Generate Visits" to create visits from care contracts.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-lg">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Patient</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Visit Label</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time Window</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Required Skills</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {visits.map((visit) => (
                <tr key={visit.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {patients[visit.patientId] ?? `Patient #${visit.patientId}`}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {(visit as Visit & { label?: string }).label ?? `Visit ${visit.id}`}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {visit.windowStart} – {visit.windowEnd}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {visit.durationMinutes} min
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {visit.requiredSkills.length > 0
                      ? visit.requiredSkills.join(', ')
                      : <span className="text-gray-400">None</span>}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {visit.isCancelled ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        Cancelled
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        Scheduled
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <button
                      onClick={() => handleCancel(visit.id)}
                      disabled={visit.isCancelled}
                      className="text-red-600 hover:text-red-800 disabled:text-gray-400 disabled:cursor-not-allowed font-medium text-sm"
                    >
                      Cancel
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Toast */}
      {toastMessage && (
        <ConfirmationToast
          message={toastMessage}
          onClose={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
