
export interface ProgressPanelProps {
  currentStep: number;
  stepName: string;
  score: number;
  isRunning: boolean;
  error?: { step: number; message: string } | null;
}

const TOTAL_STEPS = 8;

export function ProgressPanel({
  currentStep,
  stepName,
  score,
  isRunning,
  error,
}: ProgressPanelProps) {
  if (error) {
    return (
      <div
        className="rounded-lg border border-red-200 bg-red-50 p-4"
        role="alert"
        aria-label="Optimisation error"
      >
        <div className="flex items-center gap-2 mb-2">
          <span className="text-red-600 text-lg" aria-hidden="true">⚠</span>
          <h3 className="text-sm font-semibold text-red-800">
            Optimisation Failed at Step {error.step}
          </h3>
        </div>
        <p className="text-sm text-red-700 mb-3">{error.message}</p>
        <div className="text-xs text-red-600">
          Last known score: <span className="font-medium">{score.toFixed(2)}</span>
        </div>
      </div>
    );
  }

  return (
    <div
      className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm"
      role="status"
      aria-label="Optimisation progress"
      aria-live="polite"
    >
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Optimisation Progress
      </h3>

      {/* Step info */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Current Step
        </span>
        <span className="text-xs text-gray-500">
          {currentStep}/{TOTAL_STEPS}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 w-full rounded-full bg-gray-100 mb-2" aria-hidden="true">
        <div
          className="h-2 rounded-full bg-blue-600 transition-all duration-300"
          style={{ width: `${(currentStep / TOTAL_STEPS) * 100}%` }}
        />
      </div>

      {/* Step name */}
      <p className="text-sm text-gray-800 font-medium mb-4">{stepName}</p>

      {/* Score */}
      <div className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Objective Score
        </span>
        <span
          className={`text-lg font-semibold ${isRunning ? 'text-blue-600' : 'text-gray-900'}`}
          aria-label={`Objective score: ${score.toFixed(2)}`}
        >
          {score.toFixed(2)}
        </span>
      </div>

      {/* Running indicator */}
      {isRunning && (
        <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
          <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" aria-hidden="true" />
          Optimising...
        </div>
      )}
    </div>
  );
}

export default ProgressPanel;
