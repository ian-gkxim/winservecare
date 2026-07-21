import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ScenariosPage from './ScenariosPage';

const mockScenarios = [
  {
    id: 1,
    name: 'Baseline Optimisation',
    totalTravelHours: 12.5,
    totalMileage: 85.3,
    totalOvertimeHours: 2.1,
    continuityScore: 78,
    objectiveScore: 450.2,
    createdAt: '2024-01-15T10:30:00',
  },
  {
    id: 2,
    name: 'Cancellation Scenario',
    totalTravelHours: 10.2,
    totalMileage: 72.1,
    totalOvertimeHours: 1.5,
    continuityScore: 82,
    objectiveScore: 390.5,
    createdAt: '2024-01-16T14:20:00',
  },
  {
    id: 3,
    name: 'Third Scenario',
    totalTravelHours: 11.0,
    totalMileage: 78.0,
    totalOvertimeHours: 1.8,
    continuityScore: 80,
    objectiveScore: 420.0,
    createdAt: '2024-01-17T09:00:00',
  },
];

const mockComparison = {
  scenario1: {
    id: 1,
    name: 'Baseline Optimisation',
    totalTravelHours: 12.5,
    totalMileage: 85.3,
    totalOvertimeHours: 2.1,
    continuityScore: 78,
    objectiveScore: 450.2,
    assignments: [
      { visitId: 1, carerId: 1, startTime: '09:00', travelTime: 15, mileage: 5.0 },
      { visitId: 2, carerId: 2, startTime: '09:30', travelTime: 10, mileage: 3.0 },
      { visitId: 3, carerId: 1, startTime: '11:00', travelTime: 20, mileage: 7.0 },
    ],
    routes: [],
    createdAt: '2024-01-15T10:30:00',
  },
  scenario2: {
    id: 2,
    name: 'Cancellation Scenario',
    totalTravelHours: 10.2,
    totalMileage: 72.1,
    totalOvertimeHours: 1.5,
    continuityScore: 82,
    objectiveScore: 390.5,
    assignments: [
      { visitId: 1, carerId: 2, startTime: '09:00', travelTime: 12, mileage: 4.0 },
      { visitId: 2, carerId: 2, startTime: '09:30', travelTime: 10, mileage: 3.0 },
      { visitId: 3, carerId: 3, startTime: '11:00', travelTime: 18, mileage: 6.0 },
    ],
    routes: [],
    createdAt: '2024-01-16T14:20:00',
  },
  differences: [
    { metric: 'totalTravelHours', value1: 12.5, value2: 10.2, absoluteDiff: -2.3, percentageDiff: -18.4 },
    { metric: 'totalMileage', value1: 85.3, value2: 72.1, absoluteDiff: -13.2, percentageDiff: -15.5 },
    { metric: 'totalOvertimeHours', value1: 2.1, value2: 1.5, absoluteDiff: -0.6, percentageDiff: -28.6 },
    { metric: 'continuityScore', value1: 78, value2: 82, absoluteDiff: 4.0, percentageDiff: 5.1 },
  ],
  changedVisits: [1, 3],
};

vi.mock('../services/api', () => ({
  getScenarios: vi.fn(),
  compareScenarios: vi.fn(),
}));

import { getScenarios, compareScenarios } from '../services/api';

const mockedGetScenarios = vi.mocked(getScenarios);
const mockedCompareScenarios = vi.mocked(compareScenarios);

describe('ScenariosPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetScenarios.mockResolvedValue(mockScenarios);
    mockedCompareScenarios.mockResolvedValue(mockComparison);
  });

  it('renders the page heading', async () => {
    render(<ScenariosPage />);
    expect(screen.getByText('Scenarios')).toBeInTheDocument();
  });

  it('displays loading state initially then shows scenario data', async () => {
    render(<ScenariosPage />);
    expect(screen.getByText('Loading scenarios...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });
    expect(screen.getByText('Cancellation Scenario')).toBeInTheDocument();
  });

  it('displays scenario metrics in the table', async () => {
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('12.5 hrs')).toBeInTheDocument();
    });
    expect(screen.getByText('85.3 mi')).toBeInTheDocument();
    expect(screen.getByText('2.1 hrs')).toBeInTheDocument();
    expect(screen.getByText('78%')).toBeInTheDocument();
  });

  it('shows error banner when data fetch fails', async () => {
    mockedGetScenarios.mockRejectedValue(new Error('Network error'));
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load scenarios.')).toBeInTheDocument();
    });
  });

  it('disables compare button when fewer than 2 scenarios are selected', async () => {
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });

    const compareButton = screen.getByRole('button', { name: /compare/i });
    expect(compareButton).toBeDisabled();
  });

  it('enables compare button when exactly 2 scenarios are selected', async () => {
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);

    const compareButton = screen.getByRole('button', { name: /compare/i });
    expect(compareButton).not.toBeDisabled();
  });

  it('shows warning when fewer than 2 scenarios exist', async () => {
    mockedGetScenarios.mockResolvedValue([mockScenarios[0]]);
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(
        screen.getByText('At least two saved scenarios are required to use comparison.')
      ).toBeInTheDocument();
    });
  });

  it('shows empty state when no scenarios exist', async () => {
    mockedGetScenarios.mockResolvedValue([]);
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No scenarios saved yet/)
      ).toBeInTheDocument();
    });
  });

  it('navigates to comparison view when compare is clicked', async () => {
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);

    const compareButton = screen.getByRole('button', { name: /compare/i });
    fireEvent.click(compareButton);

    await waitFor(() => {
      expect(screen.getByText('Scenario Comparison')).toBeInTheDocument();
    });
  });

  it('displays metric differences in comparison view', async () => {
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole('button', { name: /compare/i }));

    await waitFor(() => {
      expect(screen.getByText('Metric Differences')).toBeInTheDocument();
    });
    // Travel Hours appears in both metric cards and in the differences table
    expect(screen.getAllByText('Travel Hours').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('-2.3 (-18.4%)')).toBeInTheDocument();
  });

  it('highlights changed visit assignments in comparison', async () => {
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole('button', { name: /compare/i }));

    await waitFor(() => {
      expect(screen.getByText('Changed Visit Assignments')).toBeInTheDocument();
    });
    // Text is split across elements, use a function matcher
    expect(screen.getByText((_content, element) =>
      element?.tagName === 'SPAN' && element.textContent?.includes('2 visit') === true
    )).toBeInTheDocument();
    expect(screen.getByText('Visit #1')).toBeInTheDocument();
    expect(screen.getByText('Visit #3')).toBeInTheDocument();
  });

  it('allows navigating back from comparison to list', async () => {
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole('button', { name: /compare/i }));

    await waitFor(() => {
      expect(screen.getByText('Scenario Comparison')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /back/i }));

    await waitFor(() => {
      expect(screen.getByText('Scenarios')).toBeInTheDocument();
    });
  });

  it('limits checkbox selection to 2 scenarios maximum', async () => {
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(checkboxes[2]);

    // After selecting 3rd, first should be deselected
    expect(checkboxes[0]).not.toBeChecked();
    expect(checkboxes[1]).toBeChecked();
    expect(checkboxes[2]).toBeChecked();
  });

  it('shows error banner when comparison API fails', async () => {
    mockedCompareScenarios.mockRejectedValue(new Error('Server error'));
    render(<ScenariosPage />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Optimisation')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole('button', { name: /compare/i }));

    await waitFor(() => {
      expect(screen.getByText('Failed to compare scenarios.')).toBeInTheDocument();
    });
  });
});
