import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DataTable, Column } from './DataTable';

interface TestRow {
  id: number;
  name: string;
  age: number;
  skills: string[];
}

const columns: Column<TestRow>[] = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'age', label: 'Age', sortable: true },
  { key: 'skills', label: 'Skills' },
];

const sampleData: TestRow[] = [
  { id: 1, name: 'Alice', age: 30, skills: ['cooking', 'driving'] },
  { id: 2, name: 'Bob', age: 25, skills: ['medication'] },
  { id: 3, name: 'Charlie', age: 35, skills: ['personal care', 'cooking'] },
];

describe('DataTable', () => {
  it('renders column headers', () => {
    render(<DataTable columns={columns} data={sampleData} />);
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Age')).toBeInTheDocument();
    expect(screen.getByText('Skills')).toBeInTheDocument();
  });

  it('renders data rows', () => {
    render(<DataTable columns={columns} data={sampleData} />);
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('Charlie')).toBeInTheDocument();
  });

  it('renders array values as comma-separated strings', () => {
    render(<DataTable columns={columns} data={sampleData} />);
    expect(screen.getByText('cooking, driving')).toBeInTheDocument();
  });

  it('shows empty state when no data', () => {
    render(<DataTable columns={columns} data={[]} />);
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  it('sorts ascending on first click', () => {
    render(<DataTable columns={columns} data={sampleData} />);
    fireEvent.click(screen.getByText('Name'));

    const rows = screen.getAllByRole('row');
    // Row 0 is header, sorted alphabetically: Alice, Bob, Charlie
    expect(rows[1]).toHaveTextContent('Alice');
    expect(rows[2]).toHaveTextContent('Bob');
    expect(rows[3]).toHaveTextContent('Charlie');
  });

  it('sorts descending on second click', () => {
    render(<DataTable columns={columns} data={sampleData} />);
    const nameHeader = screen.getByText('Name');
    fireEvent.click(nameHeader);
    fireEvent.click(nameHeader);

    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Charlie');
    expect(rows[2]).toHaveTextContent('Bob');
    expect(rows[3]).toHaveTextContent('Alice');
  });

  it('shows sort direction indicator', () => {
    render(<DataTable columns={columns} data={sampleData} />);
    fireEvent.click(screen.getByText('Name'));
    expect(screen.getByText('▲')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Name'));
    expect(screen.getByText('▼')).toBeInTheDocument();
  });

  it('sorts numeric columns correctly', () => {
    render(<DataTable columns={columns} data={sampleData} />);
    fireEvent.click(screen.getByText('Age'));

    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('25');
    expect(rows[2]).toHaveTextContent('30');
    expect(rows[3]).toHaveTextContent('35');
  });

  it('calls onRowClick when row is clicked', () => {
    const onClick = vi.fn();
    render(<DataTable columns={columns} data={sampleData} onRowClick={onClick} />);
    fireEvent.click(screen.getByText('Alice'));
    expect(onClick).toHaveBeenCalledWith(sampleData[0]);
  });

  it('supports keyboard navigation on clickable rows', () => {
    const onClick = vi.fn();
    render(<DataTable columns={columns} data={sampleData} onRowClick={onClick} />);
    const row = screen.getByText('Alice').closest('tr')!;
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(onClick).toHaveBeenCalledWith(sampleData[0]);
  });

  it('supports custom render function for columns', () => {
    const customColumns: Column<TestRow>[] = [
      {
        key: 'name',
        label: 'Name',
        render: (value) => <strong data-testid="custom">{String(value)}</strong>,
      },
    ];
    render(<DataTable columns={customColumns} data={sampleData} />);
    expect(screen.getAllByTestId('custom')).toHaveLength(3);
  });
});
