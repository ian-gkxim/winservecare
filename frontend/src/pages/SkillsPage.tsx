import { useState, useEffect, useCallback, type FormEvent } from 'react';
import { DataTable, type Column } from '../components/DataTable';
import ConfirmationToast from '../components/ConfirmationToast';
import ErrorBanner from '../components/ErrorBanner';
import { getSkills, createSkill } from '../services/api';
import type { Skill } from '../types';

const columns: Column<Skill>[] = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'carerCount', label: 'Carer Count', sortable: true },
  { key: 'visitCount', label: 'Visit Count', sortable: true },
];

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [newSkillName, setNewSkillName] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getSkills();
      setSkills(data);
    } catch {
      setErrorMessage('Failed to load skills.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setErrorMessage(null);

    const trimmed = newSkillName.trim();

    if (trimmed.length === 0) {
      setValidationError('Skill name is required.');
      return;
    }

    if (trimmed.length > 100) {
      setValidationError('Skill name must be 100 characters or fewer.');
      return;
    }

    try {
      await createSkill({ name: trimmed });
      setNewSkillName('');
      setToastMessage('Skill added successfully.');
      await fetchSkills();
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { status?: number } }).response?.status === 422
      ) {
        setValidationError('A skill with this name already exists.');
      } else {
        setErrorMessage('Failed to create skill. Please try again.');
      }
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Skills</h1>

      {errorMessage && (
        <div className="mb-4">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        </div>
      )}

      <form onSubmit={handleSubmit} className="mb-6 flex items-start gap-3">
        <div className="flex flex-col">
          <label htmlFor="new-skill-name" className="sr-only">
            New skill name
          </label>
          <input
            id="new-skill-name"
            type="text"
            value={newSkillName}
            onChange={(e) => {
              setNewSkillName(e.target.value);
              setValidationError(null);
            }}
            placeholder="Enter skill name"
            className={`px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              validationError ? 'border-red-500' : 'border-gray-300'
            }`}
            aria-invalid={!!validationError}
            aria-describedby={validationError ? 'skill-name-error' : undefined}
          />
          {validationError && (
            <p id="skill-name-error" className="mt-1 text-sm text-red-600" role="alert">
              {validationError}
            </p>
          )}
        </div>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          Add Skill
        </button>
      </form>

      {loading ? (
        <p className="text-gray-500">Loading skills...</p>
      ) : (
        <DataTable columns={columns} data={skills} />
      )}

      {toastMessage && (
        <ConfirmationToast
          message={toastMessage}
          onClose={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
