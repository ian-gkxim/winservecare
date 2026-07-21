
export interface MapControlsProps {
  isPaused: boolean;
  isRunning: boolean;
  currentStep: number;
  stepName: string;
  onPause: () => void;
  onResume: () => void;
}

const TOTAL_STEPS = 8;

export function MapControls({
  isPaused,
  isRunning,
  currentStep,
  stepName,
  onPause,
  onResume,
}: MapControlsProps) {
  return (
    <div
      className="flex items-center gap-4 rounded-lg bg-white px-4 py-3 shadow-sm border border-gray-100"
      role="toolbar"
      aria-label="Map animation controls"
    >
      {/* Play/Pause toggle */}
      <button
        onClick={isPaused ? onResume : onPause}
        disabled={!isRunning}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        aria-label={isPaused ? 'Resume animation' : 'Pause animation'}
      >
        {isPaused ? '▶' : '⏸'}
      </button>

      {/* Step indicator dots */}
      <div className="flex items-center gap-1.5" aria-label={`Step ${currentStep} of ${TOTAL_STEPS}`}>
        {Array.from({ length: TOTAL_STEPS }, (_, i) => {
          const stepNum = i + 1;
          const isCompleted = stepNum < currentStep;
          const isCurrent = stepNum === currentStep;

          return (
            <div
              key={stepNum}
              className={`h-2.5 w-2.5 rounded-full transition-colors ${
                isCurrent
                  ? 'bg-blue-600 ring-2 ring-blue-200'
                  : isCompleted
                  ? 'bg-blue-400'
                  : 'bg-gray-200'
              }`}
              aria-hidden="true"
            />
          );
        })}
      </div>

      {/* Step number and name */}
      <div className="flex items-center gap-2 text-sm">
        <span className="font-medium text-gray-700">
          Step {currentStep} of {TOTAL_STEPS}
        </span>
        <span className="text-gray-400">|</span>
        <span className="text-gray-600">{stepName}</span>
      </div>
    </div>
  );
}

export default MapControls;
