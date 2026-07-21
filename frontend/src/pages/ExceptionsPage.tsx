import { useEffect, useState, useCallback } from 'react';
import { getExceptions, resolveException } from '../services/api';
import ConfirmationToast from '../components/ConfirmationToast';
import type { Exception } from '../types';

export default function ExceptionsPage() {
  const [exceptions, setExceptions] = useState<Exception[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchExceptions = useCallback(async () => {
    try {
      setError(null);
      const data = await getExceptions();
      const sorted = [...data].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      setExceptions(sorted);
    } catch {
      setError('Failed to load exceptions.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchExceptions();
  }, [fetchExceptions]);

  const handleResolve = async (id: number) => {
    setResolvingId(id);
    try {
      const updated = await resolveException(id);
      setExceptions((prev) =>
        prev.map((ex) => (ex.id === id ? updated : ex))
      );
      setToastMessage('Exception resolved successfully.');
    } catch (err: unknown) {
      // Handle already-resolved case (409 Conflict or similar)
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { status?: number } }).response?.status === 409
      ) {
        // Refresh list to get updated state
        await fetchExceptions();
        setToastMessage('Exception was already resolved.');
      } else {
        setError('Failed to resolve exception.');
      }
    } finally {
      setResolvingId(null);
    }
  };

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleString();
  };

  if (loading) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900">Exceptions</h1>
        <p className="mt-4 text-gray-500">Loading exceptions…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900">Exceptions</h1>
        <p className="mt-4 text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900">Exceptions</h1>
      <p className="mt-2 text-gray-600">View and resolve optimisation exceptions.</p>

      {exceptions.length === 0 ? (
        <p className="mt-6 text-gray-500">No exceptions have been recorded.</p>
      ) : (
        <div className="mt-6 space-y-4">
          {exceptions.map((ex) => (
            <div
              key={ex.id}
              className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{ex.description}</p>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
                    <span>{formatTimestamp(ex.timestamp)}</span>
                    <span>
                      Affected: {ex.affectedEntityType} #{ex.affectedEntityId}
                    </span>
                  </div>
                  {ex.constraintNames.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {ex.constraintNames.map((name) => (
                        <span
                          key={name}
                          className="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700"
                        >
                          {name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex-shrink-0">
                  {ex.isResolved ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700 border border-green-200">
                      <span aria-hidden="true">✓</span>
                      Resolved {ex.resolvedAt && `· ${formatTimestamp(ex.resolvedAt)}`}
                    </span>
                  ) : (
                    <button
                      onClick={() => handleResolve(ex.id)}
                      disabled={resolvingId === ex.id}
                      className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {resolvingId === ex.id ? 'Resolving…' : 'Acknowledge'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
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
