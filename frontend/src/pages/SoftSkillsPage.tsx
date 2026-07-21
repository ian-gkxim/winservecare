import { useState, useEffect, useCallback, type FormEvent } from 'react';
import { DataTable, type Column } from '../components/DataTable';
import ConfirmationToast from '../components/ConfirmationToast';
import ErrorBanner from '../components/ErrorBanner';
import { getSkills, createSkill, getConstraints, updateConstraint } from '../services/api';
import type { Skill, Constraint } from '../types';

type Tab = 'skills' | 'constraints';

const skillColumns: Column<Skill>[] = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'carerCount', label: 'Carer Count', sortable: true },
  { key: 'visitCount', label: 'Visit Count', sortable: true },
];

export default function SoftSkillsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('skills');

  // Skills state
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(true);
  const [newSkillName, setNewSkillName] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  // Constraints state
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [constraintsLoading, setConstraintsLoading] = useState(true);

  // Shared state
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    try {
      setSkillsLoading(true);
      const data = await getSkills();
      setSkills(data);
    } catch {
      setErrorMessage('Failed to load skills.');
    } finally {
      setSkillsLoading(false);
    }
  }, []);

  const fetchConstraints = useCallback(async () => {
    try {
      setConstraintsLoading(true);
      const data = await getConstraints();
      setConstraints(data);
    } catch {
      setErrorMessage('Failed to load constraints.');
    } finally {
      setConstraintsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
    fetchConstraints();
  }, [fetchSkills, fetchConstraints]);

  const handleSkillSubmit = async (e: FormEvent) => {
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

  const handleConstraintToggle = async (constraint: Constraint) => {
    const previousConstraints = [...constraints];
    setConstraints((prev) =>
      prev.map((c) =>
        c.id === constraint.id ? { ...c, isEnabled: !c.isEnabled } : c
      )
    );

    try {
      await updateConstraint(constraint.id, { isEnabled: !constraint.isEnabled });
      setToastMessage(
        `Constraint "${constraint.name}" ${!constraint.isEnabled ? 'enabled' : 'disabled'}.`
      );
    } catch {
      setConstraints(previousConstraints);
      setErrorMessage('Failed to update constraint. Please try again.');
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Soft Skills</h1>

      {errorMessage && (
        <div className="mb-4">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('skills')}
            className={`py-3 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'skills'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
            aria-selected={activeTab === 'skills'}
            role="tab"
          >
            Skills
          </button>
          <button
            onClick={() => setActiveTab('constraints')}
            className={`py-3 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'constraints'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
            aria-selected={activeTab === 'constraints'}
            role="tab"
          >
            Constraints
          </button>
        </nav>
      </div>

      {/* Skills Tab */}
      {activeTab === 'skills' && (
        <div>
          <form onSubmit={handleSkillSubmit} className="mb-6 flex items-start gap-3">
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

          {skillsLoading ? (
            <p className="text-gray-500">Loading skills...</p>
          ) : (
            <DataTable columns={skillColumns} data={skills} />
          )}
        </div>
      )}

      {/* Constraints Tab */}
      {activeTab === 'constraints' && (
        <div>
          {constraintsLoading ? (
            <p className="text-gray-500">Loading constraints...</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200" role="grid">
                <thead className="bg-gray-50">
                  <tr>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Name
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Description
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Enabled
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {constraints.map((constraint, index) => (
                    <tr
                      key={constraint.id}
                      className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                    >
                      <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                        {constraint.name}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {constraint.description}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            className="sr-only peer"
                            checked={constraint.isEnabled}
                            onChange={() => handleConstraintToggle(constraint)}
                            aria-label={`Toggle ${constraint.name}`}
                          />
                          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                        </label>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
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
