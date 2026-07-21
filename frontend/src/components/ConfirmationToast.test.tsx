import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ConfirmationToast from './ConfirmationToast';

describe('ConfirmationToast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the toast message', () => {
    render(<ConfirmationToast message="Saved!" onClose={vi.fn()} />);
    expect(screen.getByText('Saved!')).toBeInTheDocument();
  });

  it('has status role for accessibility', () => {
    render(<ConfirmationToast message="Done" onClose={vi.fn()} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('auto-hides after default duration (3s)', () => {
    const onClose = vi.fn();
    render(<ConfirmationToast message="Done" onClose={onClose} />);

    expect(screen.getByText('Done')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(onClose).toHaveBeenCalledOnce();
  });

  it('auto-hides after custom duration', () => {
    const onClose = vi.fn();
    render(<ConfirmationToast message="Done" onClose={onClose} duration={1000} />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(onClose).toHaveBeenCalledOnce();
  });
});
