import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CarersPage from './CarersPage';

const mockCarers = [
  {
    id: 1,
    name: 'Alice Smith',
    homeLat: 51.5074,
    homeLng: -0.1278,
    skills: ['medication', 'mobility'],
    maxWorkingHours: 8,
    maxContinuousHours: 4,
    minBreakMinutes: 30,
  },
  {
    id: 2,
    name: 'Bob Jones',
    homeLat: 51.4545,
    homeLng: -0.9781,
    skills: ['personal care'],
    maxWorkingHours: 6,
    maxContinuousHours: 3,
    minBreakMinutes: 20,
  },
];

const mockSkills = [
  { id: 1, name: 'medication', carerCount: 3, visitCount: 5 },
  { id: 2, name: 'mobility', carerCount: 2, visitCount: 4 },
  { id: 3, name: 'personal care', carerCount: 4, visitCount: 6 },
];

vi.mock('../services/api', () => ({
  getCarers: vi.fn(),
  getSkills: vi.fn(),
  updateCarer: vi.fn(),
}));

import { getCarers, getSkills, updateCarer } from '../services/api';

const mockedGetCarers = vi.mocked(getCarers);
const mockedGetSkills = vi.mocked(getSkills);
const mockedUpdateCarer = vi.mocked(updateCarer);

describe('CarersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetCarers.mockResolvedValue(mockCarers);
    mockedGetSkills.mockResolvedValue(mockSkills);
  });

  it('renders the page heading', async () => {
    render(<CarersPage />);
    expect(screen.getByText('Carers')).toBeInTheDocument();
  });

  it('displays loading state initially then shows carer data', async () => {
    render(<CarersPage />);
    expect(screen.getByText('Loading carers...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });
    expect(screen.getByText('Bob Jones')).toBeInTheDocument();
  });

  it('displays skills as comma-separated values', async () => {
    render(<CarersPage />);

    await waitFor(() => {
      expect(screen.getByText('medication, mobility')).toBeInTheDocument();
    });
    expect(screen.getByText('personal care')).toBeInTheDocument();
  });

  it('shows error banner when data fetch fails', async () => {
    mockedGetCarers.mockRejectedValue(new Error('Network error'));
    render(<CarersPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load carers data.')).toBeInTheDocument();
    });
  });

  it('opens edit modal on row click', async () => {
    render(<CarersPage />);

    await waitFor(() => {
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Alice Smith'));

    await waitFor(() => {
      expect(screen.getByText('Edit Carer')).toBeInTheDocument();
    });
  });

  it('shows confirmation toast on successful update', async () => {
    mockedUpdateCarer.mockResolvedValue(mockCarers[0]);
    render(<CarersPage />);

    await waitFor(() => {
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Alice Smith'));

    await waitFor(() => {
      expect(screen.getByText('Edit Carer')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByText('Carer updated successfully.')).toBeInTheDocument();
    });
  });

  it('shows error banner on failed update', async () => {
    mockedUpdateCarer.mockRejectedValue(new Error('Server error'));
    render(<CarersPage />);

    await waitFor(() => {
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Alice Smith'));

    await waitFor(() => {
      expect(screen.getByText('Edit Carer')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByText('Failed to update carer. Please try again.')).toBeInTheDocument();
    });
  });
});
