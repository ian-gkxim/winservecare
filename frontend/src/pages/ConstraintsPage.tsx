import { useState, useEffect, useCallback } from 'react';
import ConfirmationToast from '../components/ConfirmationToast';
import ErrorBanner from '../components/ErrorBanner';
import { getConstraints, updateConstraint } from '../services/api';
import type { Constraint } from '../types';

export default function ConstraintsPage() {
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [loading, setLoading] = useState(true);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchConstraints = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getConstraints();
      setConstraints(data);
    } catch {
      setErrorMessage('Failed to load constraints.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConstraints();
  }, [fetchConstraints]);

  const handleToggle = async (constraint: Constraint) => {
    const previousConstraints = [...constraints];
    // Optimistic update
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
      // Revert on failure
      setConstraints(previousConstraints);
      setErrorMessage('Failed to update constraint. Please try again.');
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Constraints</h1>

      {errorMessage && (
        <div className="mb-4">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        </div>
      )}

      {loading ? (
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
                        onChange={() => handleToggle(constraint)}
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

      {toastMessage && (
        <ConfirmationToast
          message={toastMessage}
          onClose={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
