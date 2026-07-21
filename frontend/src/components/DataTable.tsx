import { useState, useCallback } from 'react';

export interface Column<T> {
  key: keyof T & string;
  label: string;
  sortable?: boolean;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
}

export interface DataTableProps<T extends { id: number | string }> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
}

type SortDirection = 'asc' | 'desc';

interface SortState {
  column: string | null;
  direction: SortDirection;
}

export function DataTable<T extends { id: number | string }>({
  columns,
  data,
  onRowClick,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<SortState>({ column: null, direction: 'asc' });

  const handleSort = useCallback((columnKey: string) => {
    setSort((prev) => {
      if (prev.column === columnKey) {
        return { column: columnKey, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { column: columnKey, direction: 'asc' };
    });
  }, []);

  const sortedData = (() => {
    if (!sort.column) return data;

    return [...data].sort((a, b) => {
      const aVal = a[sort.column as keyof T];
      const bVal = b[sort.column as keyof T];

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return sort.direction === 'asc' ? -1 : 1;
      if (bVal == null) return sort.direction === 'asc' ? 1 : -1;

      let comparison = 0;
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        comparison = aVal.localeCompare(bVal);
      } else if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal;
      } else {
        comparison = String(aVal).localeCompare(String(bVal));
      }

      return sort.direction === 'asc' ? comparison : -comparison;
    });
  })();

  const formatCellValue = (value: T[keyof T]): React.ReactNode => {
    if (value == null) return '—';
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    return String(value);
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200" role="grid">
        <thead className="bg-gray-50">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={`px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider ${
                  col.sortable ? 'cursor-pointer select-none hover:bg-gray-100' : ''
                }`}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
                aria-sort={
                  sort.column === col.key
                    ? sort.direction === 'asc'
                      ? 'ascending'
                      : 'descending'
                    : undefined
                }
              >
                <span className="flex items-center gap-1">
                  {col.label}
                  {col.sortable && sort.column === col.key && (
                    <span aria-hidden="true">
                      {sort.direction === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {sortedData.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-sm text-gray-500"
              >
                No data available
              </td>
            </tr>
          ) : (
            sortedData.map((row, rowIndex) => (
              <tr
                key={row.id}
                className={`${
                  rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'
                } ${onRowClick ? 'cursor-pointer hover:bg-blue-50' : 'hover:bg-gray-100'}`}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                role={onRowClick ? 'button' : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap"
                  >
                    {col.render
                      ? col.render(row[col.key], row)
                      : formatCellValue(row[col.key])}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
