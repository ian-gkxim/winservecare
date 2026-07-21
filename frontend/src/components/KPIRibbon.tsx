import { KPIMetrics } from '../types';

export interface KPIRibbonProps {
  metrics: KPIMetrics | null;
}

interface MetricCardProps {
  label: string;
  value: string | null;
  ariaLabel: string;
}

function MetricCard({ label, value, ariaLabel }: MetricCardProps) {
  return (
    <div
      className="flex flex-col items-center rounded-lg bg-white px-4 py-3 shadow-sm border border-gray-100 min-w-[120px]"
      aria-label={ariaLabel}
      role="status"
    >
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </span>
      {value !== null ? (
        <span className="mt-1 text-xl font-semibold text-gray-900">
          {value}
        </span>
      ) : (
        <span className="mt-1 text-xl font-semibold text-gray-300" aria-label="Data unavailable">
          —
        </span>
      )}
    </div>
  );
}

export function formatMetricValue(
  key: keyof KPIMetrics,
  value: number
): string {
  if (value == null || isNaN(value)) return '—';
  switch (key) {
    case 'totalVisits':
    case 'carersAvailable':
      return Math.round(value).toString();
    case 'travelHours':
      return `${value.toFixed(1)} hrs`;
    case 'mileage':
      return `${value.toFixed(1)} mi`;
    case 'overtime':
      return `${value.toFixed(1)} hrs`;
    case 'continuityScore':
      return `${Math.round(value)}%`;
    default:
      return value.toString();
  }
}

const metricConfig: { key: keyof KPIMetrics; label: string }[] = [
  { key: 'totalVisits', label: 'Total Visits' },
  { key: 'carersAvailable', label: 'Carers Available' },
  { key: 'travelHours', label: 'Travel Hours' },
  { key: 'mileage', label: 'Mileage' },
  { key: 'overtime', label: 'Overtime' },
  { key: 'continuityScore', label: 'Continuity Score' },
];

export function KPIRibbon({ metrics }: KPIRibbonProps) {
  return (
    <div className="flex flex-wrap gap-3 p-4 bg-gray-50 rounded-xl" role="region" aria-label="Key Performance Indicators">
      {metricConfig.map(({ key, label }) => {
        const value = metrics !== null ? formatMetricValue(key, metrics[key]) : null;
        const ariaLabel = metrics !== null
          ? `${label}: ${value}`
          : `${label}: Data unavailable`;

        return (
          <MetricCard
            key={key}
            label={label}
            value={value}
            ariaLabel={ariaLabel}
          />
        );
      })}
    </div>
  );
}

export default KPIRibbon;
