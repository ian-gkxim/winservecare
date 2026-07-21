
export interface CompletionNotificationProps {
  score: number;
  onDismiss: () => void;
}

export function CompletionNotification({ score, onDismiss }: CompletionNotificationProps) {
  return (
    <div
      className="rounded-lg border border-green-200 bg-green-50 p-4 shadow-sm"
      role="status"
      aria-label="Optimisation complete"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-green-600 text-lg" aria-hidden="true">✓</span>
          <div>
            <h3 className="text-sm font-semibold text-green-800">
              Optimisation Complete
            </h3>
            <p className="mt-1 text-sm text-green-700">
              Final objective score: <span className="font-semibold">{score.toFixed(2)}</span>
            </p>
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="rounded-md p-1 text-green-600 hover:bg-green-100 hover:text-green-800 transition-colors"
          aria-label="Dismiss notification"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default CompletionNotification;
