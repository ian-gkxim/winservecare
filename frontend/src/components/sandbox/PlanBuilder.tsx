import { useState, useEffect, useCallback } from 'react';
import {
  createJourneyPlan,
  listJourneyPlans,
  getJourneyPlan,
  modifyJourney,
  deleteJourneyPlan,
  cancelJourney,
  getCarers,
} from '../../services/api';
import type { Carer } from '../../types';
import type { JourneyCreateEntry, JourneyUpdate } from '../../types/sandbox';

/** Journey plan as returned by the API. */
interface JourneyPlan {
  id: number;
  operatingDay: string;
  version: number;
  reason: string;
  journeys: Journey[];
  createdAt?: string;
}

/** A single journey within a plan. */
interface Journey {
  id: number;
  carerId: number;
  originLat: number;
  originLng: number;
  originLabel?: string;
  destinationLat: number;
  destinationLng: number;
  destinationLabel?: string;
  plannedDeparture: string;
  plannedArrival: string;
  plannedDistanceMiles: number;
  status?: string;
}

export interface PlanBuilderProps {
  onPlanCreated: (plan: JourneyPlan) => void;
  onJourneySelected: (journey: Journey) => void;
}

type CreationReason = 'initial_creation' | 'manual_amendment' | 're_optimisation';

interface JourneyRowData {
  key: number;
  carerId: number;
  originLat: string;
  originLng: string;
  originLabel: string;
  destinationLat: string;
  destinationLng: string;
  destinationLabel: string;
  plannedDeparture: string;
  plannedArrival: string;
  plannedDistanceMiles: string;
}

interface ValidationErrors {
  operatingDay?: string;
  journeys: Record<number, string>;
}

/** Returns tomorrow's date as YYYY-MM-DD. */
function getTomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().split('T')[0];
}

/** Returns today's date as YYYY-MM-DD. */
function getToday(): string {
  return new Date().toISOString().split('T')[0];
}

/** Validates that a date string is today or in the future. */
export function isValidOperatingDay(dateStr: string): boolean {
  const today = getToday();
  return dateStr >= today;
}

/** Validates that arrival is strictly after departure. */
export function isArrivalAfterDeparture(departure: string, arrival: string): boolean {
  if (!departure || !arrival) return false;
  return new Date(arrival).getTime() > new Date(departure).getTime();
}

let nextRowKey = 1;

function createEmptyRow(): JourneyRowData {
  return {
    key: nextRowKey++,
    carerId: 0,
    originLat: '',
    originLng: '',
    originLabel: '',
    destinationLat: '',
    destinationLng: '',
    destinationLabel: '',
    plannedDeparture: '',
    plannedArrival: '',
    plannedDistanceMiles: '',
  };
}

/**
 * PlanBuilder — Visual CRUD for journey plans.
 * Provides plan creation form, plan list, and plan detail view with modify/cancel/delete actions.
 */
export function PlanBuilder({ onPlanCreated, onJourneySelected }: PlanBuilderProps) {
  // Form state
  const [operatingDay, setOperatingDay] = useState(getTomorrow());
  const [reason, setReason] = useState<CreationReason>('initial_creation');
  const [journeyRows, setJourneyRows] = useState<JourneyRowData[]>([createEmptyRow()]);
  const [validationErrors, setValidationErrors] = useState<ValidationErrors>({ journeys: {} });

  // Plan list & detail state
  const [plans, setPlans] = useState<JourneyPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<JourneyPlan | null>(null);
  const [loadingPlans, setLoadingPlans] = useState(false);

  // Carers for dropdown
  const [carers, setCarers] = useState<Carer[]>([]);

  // Error/success messages
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Delete confirmation
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  // Fetch carers on mount
  useEffect(() => {
    getCarers()
      .then(setCarers)
      .catch(() => {
        /* silently handle - dropdown will be empty */
      });
  }, []);

  // Fetch plans on mount
  const fetchPlans = useCallback(async () => {
    setLoadingPlans(true);
    try {
      const data = await listJourneyPlans();
      setPlans(Array.isArray(data) ? data : data?.plans ?? []);
    } catch {
      /* keep existing list */
    } finally {
      setLoadingPlans(false);
    }
  }, []);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  // Validation
  function validate(): boolean {
    const errors: ValidationErrors = { journeys: {} };
    let valid = true;

    if (!isValidOperatingDay(operatingDay)) {
      errors.operatingDay = 'Operating day must be today or a future date';
      valid = false;
    }

    journeyRows.forEach((row) => {
      if (row.plannedDeparture && row.plannedArrival) {
        if (!isArrivalAfterDeparture(row.plannedDeparture, row.plannedArrival)) {
          errors.journeys[row.key] = 'Arrival must be after departure';
          valid = false;
        }
      }
    });

    setValidationErrors(errors);
    return valid;
  }

  // Add/remove journey rows
  function addJourneyRow() {
    setJourneyRows((prev) => [...prev, createEmptyRow()]);
  }

  function removeJourneyRow(key: number) {
    setJourneyRows((prev) => prev.filter((r) => r.key !== key));
  }

  function updateJourneyRow(key: number, field: keyof JourneyRowData, value: string | number) {
    setJourneyRows((prev) =>
      prev.map((r) => (r.key === key ? { ...r, [field]: value } : r))
    );
  }

  // Submit plan
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setApiError(null);

    if (!validate()) return;

    const journeys: JourneyCreateEntry[] = journeyRows.map((row) => ({
      carerId: row.carerId,
      originLat: parseFloat(row.originLat) || 0,
      originLng: parseFloat(row.originLng) || 0,
      originLabel: row.originLabel || undefined,
      destinationLat: parseFloat(row.destinationLat) || 0,
      destinationLng: parseFloat(row.destinationLng) || 0,
      destinationLabel: row.destinationLabel || undefined,
      plannedDeparture: row.plannedDeparture,
      plannedArrival: row.plannedArrival,
      plannedDistanceMiles: parseFloat(row.plannedDistanceMiles) || 0,
    }));

    setSubmitting(true);
    try {
      const plan = await createJourneyPlan({
        operatingDay,
        journeys,
        reason,
      });
      onPlanCreated(plan);
      await fetchPlans();
      // Reset form
      setJourneyRows([createEmptyRow()]);
      setOperatingDay(getTomorrow());
      setReason('initial_creation');
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string; message?: string } } })?.response?.data
          ?.detail ||
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        (err as Error)?.message ||
        'Failed to create plan';
      setApiError(message);
    } finally {
      setSubmitting(false);
    }
  }

  // Select a plan to view details
  async function selectPlan(planId: number) {
    try {
      const plan = await getJourneyPlan(planId);
      setSelectedPlan(plan);
    } catch {
      setApiError('Failed to load plan details');
    }
  }

  // Modify a journey in the selected plan
  async function handleModifyJourney(journeyId: number, update: JourneyUpdate) {
    if (!selectedPlan) return;
    try {
      await modifyJourney(selectedPlan.id, journeyId, update);
      // Refresh the plan
      const updated = await getJourneyPlan(selectedPlan.id);
      setSelectedPlan(updated);
      await fetchPlans();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        'Failed to modify journey';
      setApiError(message);
    }
  }

  // Cancel a journey
  async function handleCancelJourney(journeyId: number) {
    try {
      await cancelJourney(journeyId);
      if (selectedPlan) {
        const updated = await getJourneyPlan(selectedPlan.id);
        setSelectedPlan(updated);
      }
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        'Failed to cancel journey';
      setApiError(message);
    }
  }

  // Delete a plan
  async function handleDeletePlan(planId: number) {
    try {
      await deleteJourneyPlan(planId);
      setPlans((prev) => prev.filter((p) => p.id !== planId));
      if (selectedPlan?.id === planId) {
        setSelectedPlan(null);
      }
      setDeleteConfirmId(null);
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        'Failed to delete plan';
      setApiError(message);
      setDeleteConfirmId(null);
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      {/* Header */}
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Plan Builder</h2>

      {/* API Error Banner */}
      {apiError && (
        <div
          className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-800 text-sm"
          role="alert"
        >
          <span className="font-medium">Error:</span> {apiError}
          <button
            onClick={() => setApiError(null)}
            className="ml-2 text-red-600 hover:text-red-800 font-bold"
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {/* Plan Creation Form */}
      <form onSubmit={handleSubmit} className="mb-6 border border-gray-200 rounded p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3">
          Create Plan — {journeyRows.length} journey{journeyRows.length !== 1 ? 's' : ''}
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          {/* Operating Day */}
          <div>
            <label htmlFor="operating-day" className="block text-xs font-medium text-gray-600 mb-1">
              Operating Day
            </label>
            <input
              id="operating-day"
              type="date"
              value={operatingDay}
              onChange={(e) => setOperatingDay(e.target.value)}
              className={`w-full border rounded px-2 py-1 text-sm ${
                validationErrors.operatingDay ? 'border-red-400' : 'border-gray-300'
              }`}
            />
            {validationErrors.operatingDay && (
              <p className="text-xs text-red-600 mt-1">{validationErrors.operatingDay}</p>
            )}
          </div>

          {/* Creation Reason */}
          <div>
            <label htmlFor="creation-reason" className="block text-xs font-medium text-gray-600 mb-1">
              Reason
            </label>
            <select
              id="creation-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value as CreationReason)}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            >
              <option value="initial_creation">Initial Creation</option>
              <option value="manual_amendment">Manual Amendment</option>
              <option value="re_optimisation">Re-optimisation</option>
            </select>
          </div>
        </div>

        {/* Journey Rows */}
        <div className="space-y-3">
          {journeyRows.map((row, idx) => (
            <div
              key={row.key}
              className="border border-gray-100 rounded p-3 bg-gray-50"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-500">Journey {idx + 1}</span>
                <button
                  type="button"
                  onClick={() => removeJourneyRow(row.key)}
                  className="text-xs text-red-600 hover:text-red-800"
                  aria-label={`Remove journey ${idx + 1}`}
                >
                  Remove
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {/* Carer dropdown */}
                <div className="col-span-2 sm:col-span-1">
                  <label className="block text-xs text-gray-500">Carer</label>
                  <select
                    value={row.carerId}
                    onChange={(e) => updateJourneyRow(row.key, 'carerId', Number(e.target.value))}
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                  >
                    <option value={0}>Select carer...</option>
                    {carers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Origin */}
                <div>
                  <label className="block text-xs text-gray-500">Origin Lat</label>
                  <input
                    type="text"
                    value={row.originLat}
                    onChange={(e) => updateJourneyRow(row.key, 'originLat', e.target.value)}
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                    placeholder="51.5"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500">Origin Lng</label>
                  <input
                    type="text"
                    value={row.originLng}
                    onChange={(e) => updateJourneyRow(row.key, 'originLng', e.target.value)}
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                    placeholder="-0.12"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500">Origin Label</label>
                  <input
                    type="text"
                    value={row.originLabel}
                    onChange={(e) => updateJourneyRow(row.key, 'originLabel', e.target.value)}
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                    placeholder="Office"
                  />
                </div>

                {/* Destination */}
                <div>
                  <label className="block text-xs text-gray-500">Dest Lat</label>
                  <input
                    type="text"
                    value={row.destinationLat}
                    onChange={(e) => updateJourneyRow(row.key, 'destinationLat', e.target.value)}
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                    placeholder="51.52"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500">Dest Lng</label>
                  <input
                    type="text"
                    value={row.destinationLng}
                    onChange={(e) => updateJourneyRow(row.key, 'destinationLng', e.target.value)}
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                    placeholder="-0.1"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500">Dest Label</label>
                  <input
                    type="text"
                    value={row.destinationLabel}
                    onChange={(e) => updateJourneyRow(row.key, 'destinationLabel', e.target.value)}
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                    placeholder="Patient Home"
                  />
                </div>

                {/* Times and distance */}
                <div>
                  <label className="block text-xs text-gray-500">Departure</label>
                  <input
                    type="datetime-local"
                    value={row.plannedDeparture}
                    onChange={(e) => updateJourneyRow(row.key, 'plannedDeparture', e.target.value)}
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500">Arrival</label>
                  <input
                    type="datetime-local"
                    value={row.plannedArrival}
                    onChange={(e) => updateJourneyRow(row.key, 'plannedArrival', e.target.value)}
                    className={`w-full border rounded px-1 py-1 text-xs ${
                      validationErrors.journeys[row.key] ? 'border-red-400' : 'border-gray-300'
                    }`}
                  />
                  {validationErrors.journeys[row.key] && (
                    <p className="text-xs text-red-600 mt-0.5">
                      {validationErrors.journeys[row.key]}
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-xs text-gray-500">Distance (mi)</label>
                  <input
                    type="text"
                    value={row.plannedDistanceMiles}
                    onChange={(e) =>
                      updateJourneyRow(row.key, 'plannedDistanceMiles', e.target.value)
                    }
                    className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
                    placeholder="5.2"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add Journey + Submit */}
        <div className="flex items-center justify-between mt-4">
          <button
            type="button"
            onClick={addJourneyRow}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            + Add Journey
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? 'Creating...' : 'Create Plan'}
          </button>
        </div>
      </form>

      {/* Plan List */}
      <div className="mb-4">
        <h3 className="text-sm font-medium text-gray-700 mb-2">
          Plans {loadingPlans && <span className="text-gray-400">(loading...)</span>}
        </h3>
        {plans.length === 0 && !loadingPlans && (
          <p className="text-xs text-gray-500">No plans yet. Create one above.</p>
        )}
        <ul className="space-y-1">
          {plans.map((plan) => (
            <li key={plan.id}>
              <button
                onClick={() => selectPlan(plan.id)}
                className={`w-full text-left px-3 py-2 rounded text-sm border ${
                  selectedPlan?.id === plan.id
                    ? 'border-blue-400 bg-blue-50'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <span className="font-medium">{plan.operatingDay}</span>
                <span className="ml-2 text-gray-500">v{plan.version}</span>
                <span className="ml-2 text-gray-400 text-xs">{plan.reason}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Plan Detail View */}
      {selectedPlan && (
        <div className="border border-gray-200 rounded p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-700">
              Plan #{selectedPlan.id} — {selectedPlan.operatingDay} (v{selectedPlan.version})
            </h3>
            <div className="flex gap-2">
              <button
                onClick={() => setDeleteConfirmId(selectedPlan.id)}
                className="text-xs text-red-600 hover:text-red-800 font-medium"
              >
                Delete Plan
              </button>
              <button
                onClick={() => setSelectedPlan(null)}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                Close
              </button>
            </div>
          </div>

          {/* Delete confirmation */}
          {deleteConfirmId === selectedPlan.id && (
            <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded text-sm">
              <p className="text-red-800 mb-2">
                Are you sure you want to delete this plan? This will remove{' '}
                {selectedPlan.journeys?.length ?? 0} journey(s).
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleDeletePlan(selectedPlan.id)}
                  className="px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700"
                >
                  Confirm Delete
                </button>
                <button
                  onClick={() => setDeleteConfirmId(null)}
                  className="px-3 py-1 bg-gray-200 text-gray-700 text-xs rounded hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Journeys Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="pb-2 pr-2">Carer</th>
                  <th className="pb-2 pr-2">Origin</th>
                  <th className="pb-2 pr-2">Destination</th>
                  <th className="pb-2 pr-2">Departure</th>
                  <th className="pb-2 pr-2">Arrival</th>
                  <th className="pb-2 pr-2">Distance</th>
                  <th className="pb-2 pr-2">Status</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(selectedPlan.journeys ?? []).map((j) => {
                  const carerName =
                    carers.find((c) => c.id === j.carerId)?.name || `Carer #${j.carerId}`;
                  return (
                    <tr
                      key={j.id}
                      className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                      onClick={() => onJourneySelected(j)}
                    >
                      <td className="py-2 pr-2">{carerName}</td>
                      <td className="py-2 pr-2">{j.originLabel || `${j.originLat}, ${j.originLng}`}</td>
                      <td className="py-2 pr-2">
                        {j.destinationLabel || `${j.destinationLat}, ${j.destinationLng}`}
                      </td>
                      <td className="py-2 pr-2">
                        {j.plannedDeparture
                          ? new Date(j.plannedDeparture).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : '—'}
                      </td>
                      <td className="py-2 pr-2">
                        {j.plannedArrival
                          ? new Date(j.plannedArrival).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : '—'}
                      </td>
                      <td className="py-2 pr-2">{j.plannedDistanceMiles} mi</td>
                      <td className="py-2 pr-2">
                        <span
                          className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
                            j.status === 'completed'
                              ? 'bg-green-100 text-green-800'
                              : j.status === 'cancelled'
                              ? 'bg-red-100 text-red-800'
                              : j.status === 'in_progress'
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-blue-100 text-blue-800'
                          }`}
                        >
                          {j.status || 'planned'}
                        </span>
                      </td>
                      <td className="py-2">
                        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() =>
                              handleModifyJourney(j.id, {
                                /* placeholder for inline edit */
                              })
                            }
                            className="px-1.5 py-0.5 text-xs text-blue-600 hover:text-blue-800 border border-blue-200 rounded"
                            title="Modify journey"
                          >
                            Modify
                          </button>
                          <button
                            onClick={() => handleCancelJourney(j.id)}
                            className="px-1.5 py-0.5 text-xs text-orange-600 hover:text-orange-800 border border-orange-200 rounded"
                            title="Cancel journey"
                          >
                            Cancel
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
