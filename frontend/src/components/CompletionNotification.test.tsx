import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CompletionNotification from './CompletionNotification';

describe('CompletionNotification', () => {
  const defaultProps = {
    score: 92.37,
    onDismiss: vi.fn(),
  };

  it('renders the final objective score formatted to 2 decimal places', () => {
    render(<CompletionNotification {...defaultProps} />);
    expect(screen.getByText('92.37')).toBeInTheDocument();
  });

  it('renders the completion message', () => {
    render(<CompletionNotification {...defaultProps} />);
    expect(screen.getByText('Optimisation Complete')).toBeInTheDocument();
  });

  it('calls onDismiss when dismiss button is clicked', () => {
    const onDismiss = vi.fn();
    render(<CompletionNotification score={80} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByLabelText('Dismiss notification'));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it('has status role for accessibility', () => {
    render(<CompletionNotification {...defaultProps} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('formats whole number scores with 2 decimal places', () => {
    render(<CompletionNotification score={100} onDismiss={vi.fn()} />);
    expect(screen.getByText('100.00')).toBeInTheDocument();
  });

  it('renders dismiss button', () => {
    render(<CompletionNotification {...defaultProps} />);
    expect(screen.getByLabelText('Dismiss notification')).toBeInTheDocument();
  });
});
