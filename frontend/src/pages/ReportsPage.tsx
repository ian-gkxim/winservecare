import { useState, useEffect } from 'react';
import { getLatestReport } from '../services/api';
import type { Report } from '../types';

export default function ReportsPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        const data = await getLatestReport();
        setReport(data);
      } catch {
        setError('Failed to load report data.');
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, []);

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
        <p className="mt-4 text-gray-500">Loading report...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
        <p className="mt-4 text-red-600">{error}</p>
      </div>
    );
  }

  if (!report || !report.available) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
        <div className="mt-6 bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-500 text-lg">
            {report?.message || 'No optimisation results are available.'}
          </p>
        </div>
      </div>
    );
  }

  const { before, after, differences } = report;

  const metrics = [
    { label: 'Travel Hours', beforeVal: before!.totalTravelHours, afterVal: after!.totalTravelHours, diff: differences!.travelHours, unit: 'hrs' },
    { label: 'Mileage', beforeVal: before!.totalMileage, afterVal: after!.totalMileage, diff: differences!.mileage, unit: 'mi' },
    { label: 'Overtime Hours', beforeVal: before!.totalOvertimeHours, afterVal: after!.totalOvertimeHours, diff: differences!.overtime, unit: 'hrs' },
    { label: 'Continuity Score', beforeVal: before!.continuityScore, afterVal: after!.continuityScore, diff: differences!.continuityScore, unit: '%' },
  ];

  return (
    <div className="p-6 print-content">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Optimisation Report</h1>
        <button
          onClick={handlePrint}
          className="print-hide px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          Print
        </button>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="px-6 py-3 text-left font-semibold text-gray-700">Metric</th>
              <th className="px-6 py-3 text-right font-semibold text-gray-700">Before</th>
              <th className="px-6 py-3 text-right font-semibold text-gray-700">After</th>
              <th className="px-6 py-3 text-right font-semibold text-gray-700">Difference</th>
              <th className="px-6 py-3 text-right font-semibold text-gray-700">% Change</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => {
              const isImprovement =
                m.label === 'Continuity Score'
                  ? m.diff.absolute > 0
                  : m.diff.absolute < 0;

              return (
                <tr key={m.label} className="border-b border-gray-100 last:border-b-0">
                  <td className="px-6 py-4 font-medium text-gray-900">{m.label}</td>
                  <td className="px-6 py-4 text-right text-gray-700">
                    {m.beforeVal.toFixed(1)} {m.unit}
                  </td>
                  <td className="px-6 py-4 text-right text-gray-700">
                    {m.afterVal.toFixed(1)} {m.unit}
                  </td>
                  <td className={`px-6 py-4 text-right font-medium ${isImprovement ? 'text-green-600' : 'text-red-600'}`}>
                    {m.diff.absolute > 0 ? '+' : ''}{m.diff.absolute.toFixed(1)} {m.unit}
                  </td>
                  <td className={`px-6 py-4 text-right font-medium ${isImprovement ? 'text-green-600' : 'text-red-600'}`}>
                    {m.diff.percentage > 0 ? '+' : ''}{m.diff.percentage.toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
