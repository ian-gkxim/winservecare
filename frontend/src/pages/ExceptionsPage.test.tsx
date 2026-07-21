import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ExceptionsPage from './ExceptionsPage';
import * as api from '../services/api';
import type { Exception } from '../types';

vi.mock('../services/api', () => ({
  getExceptions: vi.fn(),
  resolveException: vi.fn(),
}));

const mockExceptions: Exception[] = [
  {
    id: 1,
    timestamp: '2024-01-15T10:30:00Z',
    description: 'Carer exceeds max working hours',
    constraintNames: ['max_working_hours'],
    affectedEntityType: 'carer',
    affectedEntityId: 5,
    isResolved: false,
    resolvedAt: null,
  },
  {
    id: 2,
    timestamp: '2024-01-15T09:00:00Z',
    description: 'Visit has no eligible carer',
    constraintNames: ['skill_match', 'availability'],
    affectedEntityType: 'visit',
    affectedEntityId: 12,
    isResolved: true,
    resolvedAt: '2024-01-15T11:00:00Z',
  },
];

describe('ExceptionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows empty state when no exceptions exist', async () => {
    vi.mocked(api.getExceptions).mockResolvedValue([]);

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByText('No exceptions have been recorded.')).toBeInTheDocument();
    });
  });

  it('displays exceptions ordered by timestamp descending', async () => {
    vi.mocked(api.getExceptions).mockResolvedValue(mockExceptions);

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Carer exceeds max working hours')).toBeInTheDocument();
    });

    const items = screen.getAllByText(/exceeds|no eligible/);
    expect(items[0]).toHaveTextContent('Carer exceeds max working hours');
    expect(items[1]).toHaveTextContent('Visit has no eligible carer');
  });

  it('shows affected entity type and ID', async () => {
    vi.mocked(api.getExceptions).mockResolvedValue(mockExceptions);

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Affected: carer #5/)).toBeInTheDocument();
      expect(screen.getByText(/Affected: visit #12/)).toBeInTheDocument();
    });
  });

  it('shows constraint names as tags', async () => {
    vi.mocked(api.getExceptions).mockResolvedValue(mockExceptions);

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByText('max_working_hours')).toBeInTheDocument();
      expect(screen.getByText('skill_match')).toBeInTheDocument();
      expect(screen.getByText('availability')).toBeInTheDocument();
    });
  });

  it('shows Acknowledge button for unresolved exceptions', async () => {
    vi.mocked(api.getExceptions).mockResolvedValue(mockExceptions);

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Acknowledge' })).toBeInTheDocument();
    });
  });

  it('shows Resolved badge for resolved exceptions', async () => {
    vi.mocked(api.getExceptions).mockResolvedValue(mockExceptions);

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Resolved/)).toBeInTheDocument();
    });
  });

  it('resolves an exception in-place without page reload', async () => {
    vi.mocked(api.getExceptions).mockResolvedValue([mockExceptions[0]]);
    vi.mocked(api.resolveException).mockResolvedValue({
      ...mockExceptions[0],
      isResolved: true,
      resolvedAt: '2024-01-15T12:00:00Z',
    });

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Acknowledge' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument();
      expect(screen.getByText(/Resolved/)).toBeInTheDocument();
    });

    expect(api.resolveException).toHaveBeenCalledWith(1);
    // Confirm getExceptions was only called once (initial load), not on resolve
    expect(api.getExceptions).toHaveBeenCalledTimes(1);
  });

  it('shows confirmation toast after successful resolution', async () => {
    vi.mocked(api.getExceptions).mockResolvedValue([mockExceptions[0]]);
    vi.mocked(api.resolveException).mockResolvedValue({
      ...mockExceptions[0],
      isResolved: true,
      resolvedAt: '2024-01-15T12:00:00Z',
    });

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Acknowledge' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }));

    await waitFor(() => {
      expect(screen.getByText('Exception resolved successfully.')).toBeInTheDocument();
    });
  });

  it('shows error message when loading fails', async () => {
    vi.mocked(api.getExceptions).mockRejectedValue(new Error('Network error'));

    render(<ExceptionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load exceptions.')).toBeInTheDocument();
    });
  });
});
