import { useState, useEffect } from 'react';
import { getConfig, updateConfig } from '../services/api';
import ConfirmationToast from '../components/ConfirmationToast';
import ErrorBanner from '../components/ErrorBanner';

export default function ConfigPage() {
  const [apiKey, setApiKey] = useState('');
  const [hasApiKey, setHasApiKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        setLoading(true);
        const config = await getConfig();
        setHasApiKey(config.hasApiKey);
        if (config.hasApiKey) {
          setApiKey(config.googleMapsApiKey);
        }
      } catch {
        setErrorMessage('Failed to load configuration.');
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setErrorMessage(null);

    const trimmedKey = apiKey.trim();
    if (!trimmedKey) {
      setValidationError('API key is required');
      return;
    }

    try {
      setSaving(true);
      const config = await updateConfig({ googleMapsApiKey: trimmedKey });
      setHasApiKey(config.hasApiKey);
      setApiKey(config.googleMapsApiKey);
      setToastMessage('Configuration saved successfully.');
    } catch {
      setErrorMessage('Failed to save configuration. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const maskedKey = hasApiKey && apiKey ? `${'•'.repeat(Math.max(0, apiKey.length - 4))}${apiKey.slice(-4)}` : '';

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Configuration</h1>

      {errorMessage && (
        <div className="mb-4">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading configuration...</p>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 p-6 max-w-lg">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Google Maps API Key</h2>

          {hasApiKey && (
            <p className="text-sm text-gray-600 mb-4">
              Current key: <span className="font-mono text-gray-800">{maskedKey}</span>
            </p>
          )}

          {!hasApiKey && (
            <p className="text-sm text-gray-500 mb-4">
              No API key configured. Enter your Google Maps API key below.
            </p>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label htmlFor="api-key" className="block text-sm font-medium text-gray-700 mb-1">
                API Key
              </label>
              <input
                id="api-key"
                type="text"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  if (validationError) setValidationError(null);
                }}
                placeholder="Enter your Google Maps API key"
                className={`w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  validationError ? 'border-red-300 focus:ring-red-500' : 'border-gray-300'
                }`}
                aria-describedby={validationError ? 'api-key-error' : undefined}
                aria-invalid={!!validationError}
              />
              {validationError && (
                <p id="api-key-error" className="mt-1 text-sm text-red-600" role="alert">
                  {validationError}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </form>
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
