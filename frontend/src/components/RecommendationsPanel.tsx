import { Recommendation } from '../types';

export interface RecommendationsPanelProps {
  items: Recommendation[];
}

const MAX_ITEMS = 10;

function RecommendationItem({ item }: { item: Recommendation }) {
  const isWarning = item.type === 'warning';
  const icon = isWarning ? '⚠️' : '💡';
  const borderClass = isWarning ? 'border-l-amber-400' : 'border-l-blue-400';

  return (
    <li
      className={`rounded-md border border-gray-100 border-l-4 ${borderClass} bg-white p-3 shadow-sm`}
      aria-label={`${isWarning ? 'Warning' : 'Recommendation'}: ${item.title}`}
    >
      <div className="flex items-start gap-2">
        <span className="text-base flex-shrink-0" aria-hidden="true">
          {icon}
        </span>
        <div className="min-w-0">
          <p className="font-semibold text-sm text-gray-900">{item.title}</p>
          <p className="mt-0.5 text-xs text-gray-600 line-clamp-3">
            {item.description.length > 200
              ? item.description.slice(0, 200)
              : item.description}
          </p>
        </div>
      </div>
    </li>
  );
}

export function RecommendationsPanel({ items }: RecommendationsPanelProps) {
  const sorted = [...items].sort((a, b) => b.impact - a.impact);
  const displayed = sorted.slice(0, MAX_ITEMS);

  if (displayed.length === 0) {
    return (
      <section
        className="rounded-xl bg-gray-50 p-4"
        role="region"
        aria-label="Recommendations"
      >
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Recommendations</h2>
        <p className="text-sm text-gray-500">No recommendations available</p>
      </section>
    );
  }

  return (
    <section
      className="rounded-xl bg-gray-50 p-4"
      role="region"
      aria-label="Recommendations"
    >
      <h2 className="text-sm font-semibold text-gray-700 mb-3">Recommendations</h2>
      <ul className="flex flex-col gap-2" role="list">
        {displayed.map((item) => (
          <RecommendationItem key={item.id} item={item} />
        ))}
      </ul>
    </section>
  );
}

export default RecommendationsPanel;
