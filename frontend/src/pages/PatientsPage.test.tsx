import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PatientsPage from './PatientsPage';

const mockPatients = [
  {
    id: 1,
    name: 'John Doe',
    address: '10 High Street, London',
    lat: 51.5074,
    lng: -0.1278,
    preferences: ['morning', 'female carer'],
    priority: 'high' as const,
    continuityScore: 85,
    usualCarerId: 1,
    preferredCarerId: null,
  },
  {
    id: 2,
    name: 'Jane Roe',
    address: '5 Park Lane, Reading',
    lat: 51.4545,
    lng: -0.9781,
    preferences: ['afternoon'],
    priority: 'low' as const,
    continuityScore: 60,
    usualCarerId: null,
    preferredCarerId: 2,
  },
];

vi.mock('../services/api', () => ({
  getPatients: vi.fn(),
  updatePatient: vi.fn(),
  getPatientContract: vi.fn(),
  savePatientContract: vi.fn(),
  deletePatientContract: vi.fn(),
  getSkills: vi.fn(),
}));

import { getPatients, updatePatient, getPatientContract, getSkills } from '../services/api';

const mockedGetPatients = vi.mocked(getPatients);
const mockedUpdatePatient = vi.mocked(updatePatient);
const mockedGetPatientContract = vi.mocked(getPatientContract);
const mockedGetSkills = vi.mocked(getSkills);

describe('PatientsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetPatients.mockResolvedValue(mockPatients);
    mockedGetPatientContract.mockResolvedValue(null);
    mockedGetSkills.mockResolvedValue([]);
  });

  it('renders the page heading', async () => {
    render(<PatientsPage />);
    expect(screen.getByText('Patients')).toBeInTheDocument();
  });

  it('displays loading state initially then shows patient data', async () => {
    render(<PatientsPage />);
    expect(screen.getByText('Loading patients...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
    expect(screen.getByText('Jane Roe')).toBeInTheDocument();
  });

  it('displays preferences as comma-separated values', async () => {
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText('morning, female carer')).toBeInTheDocument();
    });
    expect(screen.getByText('afternoon')).toBeInTheDocument();
  });

  it('displays continuity score with percentage', async () => {
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText('85%')).toBeInTheDocument();
    });
    expect(screen.getByText('60%')).toBeInTheDocument();
  });

  it('shows error banner when data fetch fails', async () => {
    mockedGetPatients.mockRejectedValue(new Error('Network error'));
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load patients data.')).toBeInTheDocument();
    });
  });

  it('opens edit modal on row click', async () => {
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('John Doe'));

    await waitFor(() => {
      expect(screen.getByText('Edit Patient')).toBeInTheDocument();
    });
  });

  it('shows continuity score as read-only in modal', async () => {
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('John Doe'));

    await waitFor(() => {
      expect(screen.getByText('Edit Patient')).toBeInTheDocument();
    });

    const continuityInput = screen.getByLabelText('Continuity Score') as HTMLInputElement;
    expect(continuityInput).toHaveAttribute('readonly');
  });

  it('shows confirmation toast on successful update', async () => {
    mockedUpdatePatient.mockResolvedValue(mockPatients[0]);
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('John Doe'));

    await waitFor(() => {
      expect(screen.getByText('Edit Patient')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByText('Patient updated successfully.')).toBeInTheDocument();
    });
  });

  it('shows error banner on failed update', async () => {
    mockedUpdatePatient.mockRejectedValue(new Error('Server error'));
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('John Doe'));

    await waitFor(() => {
      expect(screen.getByText('Edit Patient')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByText('Failed to update patient. Please try again.')).toBeInTheDocument();
    });
  });
});
