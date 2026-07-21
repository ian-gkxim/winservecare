import { useState, useEffect, useCallback } from 'react';
import type {
  CareContract,
  CareContractCreate,
  VisitFrequency,
  DayOfWeek,
  VisitSlot,
} from '../types/contracts';

export interface ContractFormProps {
  contract: CareContract | null; // null = no existing contract
  skills: string[]; // available skills for multi-select
  onSubmit: (data: CareContractCreate) => Promise<void>;
  onDelete?: () => Promise<void>; // optional delete handler
}

interface SlotFormData {
  label: string;
  earliestStart: string;
  latestStart: string;
  durationMinutes: number;
  requiredSkills: string[];
}

interface FormErrors {
  frequency?: string;
  daysOfWeek?: string;
  startDate?: string;
  endDate?: string;
  slots?: Record<number, Record<string, string>>;
  excludedDates?: string;
  general?: string;
}

const FREQUENCY_OPTIONS: { value: VisitFrequency; label: string }[] = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekdays_only', label: 'Weekdays Only' },
  { value: 'specific_days', label: 'Specific Days' },
  { value: 'alternate_days', label: 'Alternate Days' },
  { value: 'weekly', label: 'Weekly' },
];

const DAYS_OF_WEEK: { value: DayOfWeek; label: string }[] = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
];

const MAX_SLOTS = 4;

function createEmptySlot(): SlotFormData {
  return {
    label: '',
    earliestStart: '08:00',
    latestStart: '09:00',
    durationMinutes: 30,
    requiredSkills: [],
  };
}

export function ContractForm({ contract, skills, onSubmit, onDelete }: ContractFormProps) {
  const [frequency, setFrequency] = useState<VisitFrequency>('daily');
  const [daysOfWeek, setDaysOfWeek] = useState<DayOfWeek[]>([]);
  const [slots, setSlots] = useState<SlotFormData[]>([createEmptySlot()]);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [excludedDates, setExcludedDates] = useState<string[]>([]);
  const [newExcludedDate, setNewExcludedDate] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Pre-populate fields when editing an existing contract
  useEffect(() => {
    if (contract) {
      setFrequency(contract.visitFrequency);
      setDaysOfWeek(contract.daysOfWeek ?? []);
      setSlots(
        contract.visitSlots.map((slot: VisitSlot) => ({
          label: slot.label,
          earliestStart: slot.earliestStart,
          latestStart: slot.latestStart,
          durationMinutes: slot.durationMinutes,
          requiredSkills: [...slot.requiredSkills],
        }))
      );
      setStartDate(contract.startDate);
      setEndDate(contract.endDate ?? '');
      setExcludedDates([...contract.excludedDates]);
    }
  }, [contract]);

  const validate = useCallback((): FormErrors => {
    const newErrors: FormErrors = {};

    // Start date required
    if (!startDate) {
      newErrors.startDate = 'Start date is required';
    }

    // End date >= start date
    if (startDate && endDate && endDate < startDate) {
      newErrors.endDate = 'End date must be on or after start date';
    }

    // Specific days requires at least one day
    if (frequency === 'specific_days' && daysOfWeek.length === 0) {
      newErrors.daysOfWeek = 'At least one day must be selected';
    }

    // Validate slots
    const slotErrors: Record<number, Record<string, string>> = {};
    slots.forEach((slot, index) => {
      const errs: Record<string, string> = {};

      // Label 1-100 chars
      if (!slot.label || slot.label.trim().length === 0) {
        errs.label = 'Label is required';
      } else if (slot.label.length > 100) {
        errs.label = 'Label must be 100 characters or fewer';
      }

      // Earliest start between 06:00 and 22:00
      if (!slot.earliestStart) {
        errs.earliestStart = 'Earliest start is required';
      } else if (slot.earliestStart < '06:00' || slot.earliestStart > '22:00') {
        errs.earliestStart = 'Must be between 06:00 and 22:00';
      }

      // Latest start must be after earliest start and <= 22:00
      if (!slot.latestStart) {
        errs.latestStart = 'Latest start is required';
      } else {
        if (slot.latestStart > '22:00') {
          errs.latestStart = 'Must be no later than 22:00';
        } else if (slot.earliestStart && slot.latestStart <= slot.earliestStart) {
          errs.latestStart = 'Must be after earliest start';
        }
      }

      // Duration 15-120
      if (slot.durationMinutes < 15 || slot.durationMinutes > 120) {
        errs.durationMinutes = 'Must be between 15 and 120 minutes';
      }

      if (Object.keys(errs).length > 0) {
        slotErrors[index] = errs;
      }
    });

    if (Object.keys(slotErrors).length > 0) {
      newErrors.slots = slotErrors;
    }

    return newErrors;
  }, [frequency, daysOfWeek, slots, startDate, endDate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationErrors = validate();
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const data: CareContractCreate = {
      visitFrequency: frequency,
      visitsPerDay: slots.length,
      startDate,
      endDate: endDate || null,
      excludedDates: excludedDates,
      visitSlots: slots.map((slot, index) => ({
        slotIndex: index,
        label: slot.label.trim(),
        earliestStart: slot.earliestStart,
        latestStart: slot.latestStart,
        durationMinutes: slot.durationMinutes,
        requiredSkills: slot.requiredSkills,
      })),
    };

    if (frequency === 'specific_days') {
      data.daysOfWeek = daysOfWeek;
    }

    setSubmitting(true);
    try {
      await onSubmit(data);
    } catch {
      setErrors({ general: 'Failed to save contract. Please try again.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    setDeleting(true);
    try {
      await onDelete();
    } catch {
      setErrors({ general: 'Failed to delete contract. Please try again.' });
    } finally {
      setDeleting(false);
    }
  };

  const handleAddSlot = () => {
    if (slots.length < MAX_SLOTS) {
      setSlots([...slots, createEmptySlot()]);
    }
  };

  const handleRemoveSlot = (index: number) => {
    if (slots.length > 1) {
      setSlots(slots.filter((_, i) => i !== index));
    }
  };

  const handleSlotChange = (index: number, field: keyof SlotFormData, value: unknown) => {
    setSlots((prev) =>
      prev.map((slot, i) => (i === index ? { ...slot, [field]: value } : slot))
    );
    // Clear slot error on change
    if (errors.slots?.[index]?.[field]) {
      setErrors((prev) => {
        const newSlotErrors = { ...prev.slots };
        if (newSlotErrors[index]) {
          const updated = { ...newSlotErrors[index] };
          delete updated[field];
          if (Object.keys(updated).length === 0) {
            delete newSlotErrors[index];
          } else {
            newSlotErrors[index] = updated;
          }
        }
        return {
          ...prev,
          slots: Object.keys(newSlotErrors).length > 0 ? newSlotErrors : undefined,
        };
      });
    }
  };

  const handleSkillToggle = (slotIndex: number, skill: string) => {
    setSlots((prev) =>
      prev.map((slot, i) => {
        if (i !== slotIndex) return slot;
        const updated = slot.requiredSkills.includes(skill)
          ? slot.requiredSkills.filter((s) => s !== skill)
          : [...slot.requiredSkills, skill];
        return { ...slot, requiredSkills: updated };
      })
    );
  };

  const handleDayToggle = (day: DayOfWeek) => {
    setDaysOfWeek((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    );
    if (errors.daysOfWeek) {
      setErrors((prev) => ({ ...prev, daysOfWeek: undefined }));
    }
  };

  const handleAddExcludedDate = () => {
    if (newExcludedDate && !excludedDates.includes(newExcludedDate)) {
      setExcludedDates([...excludedDates, newExcludedDate]);
      setNewExcludedDate('');
    }
  };

  const handleRemoveExcludedDate = (date: string) => {
    setExcludedDates(excludedDates.filter((d) => d !== date));
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Care Contract</h3>
          {contract && onDelete && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="px-3 py-1.5 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-md hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {deleting ? 'Deleting...' : 'Delete Contract'}
            </button>
          )}
        </div>

        {errors.general && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
            {errors.general}
          </p>
        )}

        {/* Frequency Selector */}
        <div>
          <label htmlFor="frequency" className="block text-sm font-medium text-gray-700 mb-1">
            Visit Frequency <span className="text-red-500">*</span>
          </label>
          <select
            id="frequency"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as VisitFrequency)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {FREQUENCY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Day-of-Week Checkboxes (shown only when specific_days) */}
        {frequency === 'specific_days' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Days of Week <span className="text-red-500">*</span>
            </label>
            <div className="flex flex-wrap gap-3">
              {DAYS_OF_WEEK.map((day) => (
                <label
                  key={day.value}
                  className="flex items-center gap-1.5 text-sm cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={daysOfWeek.includes(day.value)}
                    onChange={() => handleDayToggle(day.value)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  {day.label}
                </label>
              ))}
            </div>
            {errors.daysOfWeek && (
              <p className="mt-1 text-xs text-red-600">{errors.daysOfWeek}</p>
            )}
          </div>
        )}

        {/* Visit Slots Section */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="block text-sm font-medium text-gray-700">
              Visit Slots ({slots.length}/{MAX_SLOTS})
            </label>
            {slots.length < MAX_SLOTS && (
              <button
                type="button"
                onClick={handleAddSlot}
                className="px-3 py-1 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100"
              >
                Add Slot
              </button>
            )}
          </div>

          <div className="space-y-4">
            {slots.map((slot, index) => (
              <div
                key={index}
                className="border border-gray-200 rounded-lg p-4 bg-gray-50"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-gray-700">
                    Slot {index + 1}
                  </span>
                  {slots.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveSlot(index)}
                      className="px-2 py-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-md hover:bg-red-100"
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* Label */}
                  <div className="md:col-span-2">
                    <label
                      htmlFor={`slot-label-${index}`}
                      className="block text-xs font-medium text-gray-600 mb-1"
                    >
                      Label <span className="text-red-500">*</span>
                    </label>
                    <input
                      id={`slot-label-${index}`}
                      type="text"
                      value={slot.label}
                      onChange={(e) => handleSlotChange(index, 'label', e.target.value)}
                      placeholder="e.g. Morning visit"
                      maxLength={100}
                      className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                        errors.slots?.[index]?.label ? 'border-red-300' : 'border-gray-300'
                      }`}
                    />
                    {errors.slots?.[index]?.label && (
                      <p className="mt-1 text-xs text-red-600">{errors.slots[index].label}</p>
                    )}
                  </div>

                  {/* Earliest Start */}
                  <div>
                    <label
                      htmlFor={`slot-earliest-${index}`}
                      className="block text-xs font-medium text-gray-600 mb-1"
                    >
                      Earliest Start <span className="text-red-500">*</span>
                    </label>
                    <input
                      id={`slot-earliest-${index}`}
                      type="time"
                      value={slot.earliestStart}
                      onChange={(e) => handleSlotChange(index, 'earliestStart', e.target.value)}
                      min="06:00"
                      max="22:00"
                      className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                        errors.slots?.[index]?.earliestStart ? 'border-red-300' : 'border-gray-300'
                      }`}
                    />
                    {errors.slots?.[index]?.earliestStart && (
                      <p className="mt-1 text-xs text-red-600">
                        {errors.slots[index].earliestStart}
                      </p>
                    )}
                  </div>

                  {/* Latest Start */}
                  <div>
                    <label
                      htmlFor={`slot-latest-${index}`}
                      className="block text-xs font-medium text-gray-600 mb-1"
                    >
                      Latest Start <span className="text-red-500">*</span>
                    </label>
                    <input
                      id={`slot-latest-${index}`}
                      type="time"
                      value={slot.latestStart}
                      onChange={(e) => handleSlotChange(index, 'latestStart', e.target.value)}
                      max="22:00"
                      className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                        errors.slots?.[index]?.latestStart ? 'border-red-300' : 'border-gray-300'
                      }`}
                    />
                    {errors.slots?.[index]?.latestStart && (
                      <p className="mt-1 text-xs text-red-600">
                        {errors.slots[index].latestStart}
                      </p>
                    )}
                  </div>

                  {/* Duration */}
                  <div>
                    <label
                      htmlFor={`slot-duration-${index}`}
                      className="block text-xs font-medium text-gray-600 mb-1"
                    >
                      Duration (minutes) <span className="text-red-500">*</span>
                    </label>
                    <input
                      id={`slot-duration-${index}`}
                      type="number"
                      value={slot.durationMinutes}
                      onChange={(e) =>
                        handleSlotChange(index, 'durationMinutes', Number(e.target.value))
                      }
                      min={15}
                      max={120}
                      className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                        errors.slots?.[index]?.durationMinutes ? 'border-red-300' : 'border-gray-300'
                      }`}
                    />
                    {errors.slots?.[index]?.durationMinutes && (
                      <p className="mt-1 text-xs text-red-600">
                        {errors.slots[index].durationMinutes}
                      </p>
                    )}
                  </div>

                  {/* Required Skills Multi-select */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Required Skills
                    </label>
                    <div className="border border-gray-300 rounded-md p-2 max-h-32 overflow-y-auto bg-white">
                      {skills.length > 0 ? (
                        skills.map((skill) => (
                          <label
                            key={skill}
                            className="flex items-center gap-2 px-1 py-0.5 text-xs hover:bg-gray-50 rounded cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={slot.requiredSkills.includes(skill)}
                              onChange={() => handleSkillToggle(index, skill)}
                              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                            {skill}
                          </label>
                        ))
                      ) : (
                        <span className="text-xs text-gray-500">No skills available</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Date Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="start-date" className="block text-sm font-medium text-gray-700 mb-1">
              Start Date <span className="text-red-500">*</span>
            </label>
            <input
              id="start-date"
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                if (errors.startDate) setErrors((prev) => ({ ...prev, startDate: undefined }));
              }}
              className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                errors.startDate ? 'border-red-300' : 'border-gray-300'
              }`}
            />
            {errors.startDate && (
              <p className="mt-1 text-xs text-red-600">{errors.startDate}</p>
            )}
          </div>

          <div>
            <label htmlFor="end-date" className="block text-sm font-medium text-gray-700 mb-1">
              End Date <span className="text-gray-400 text-xs">(optional)</span>
            </label>
            <input
              id="end-date"
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                if (errors.endDate) setErrors((prev) => ({ ...prev, endDate: undefined }));
              }}
              className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                errors.endDate ? 'border-red-300' : 'border-gray-300'
              }`}
            />
            {errors.endDate && (
              <p className="mt-1 text-xs text-red-600">{errors.endDate}</p>
            )}
          </div>
        </div>

        {/* Excluded Dates */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Excluded Dates <span className="text-gray-400 text-xs">(optional)</span>
          </label>
          <div className="flex gap-2 mb-2">
            <input
              type="date"
              value={newExcludedDate}
              onChange={(e) => setNewExcludedDate(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={handleAddExcludedDate}
              disabled={!newExcludedDate}
              className="px-3 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Add
            </button>
          </div>
          {excludedDates.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {excludedDates.map((date) => (
                <span
                  key={date}
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-gray-100 border border-gray-200 rounded-md"
                >
                  {date}
                  <button
                    type="button"
                    onClick={() => handleRemoveExcludedDate(date)}
                    className="text-gray-500 hover:text-red-600"
                    aria-label={`Remove excluded date ${date}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Form Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Saving...' : contract ? 'Update Contract' : 'Create Contract'}
          </button>
        </div>
      </form>
    </div>
  );
}
