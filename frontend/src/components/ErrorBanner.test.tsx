import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ErrorBanner from './ErrorBanner';

describe('ErrorBanner', () => {
  it('renders the error message', () => {
    render(<ErrorBanner message="Something went wrong" />);
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('has alert role for accessibility', () => {
    render(<ErrorBanner message="Error" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('shows dismiss button when onDismiss provided', () => {
    const onDismiss = vi.fn();
    render(<ErrorBanner message="Error" onDismiss={onDismiss} />);
    const button = screen.getByLabelText('Dismiss error');
    fireEvent.click(button);
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it('does not show dismiss button when onDismiss not provided', () => {
    render(<ErrorBanner message="Error" />);
    expect(screen.queryByLabelText('Dismiss error')).not.toBeInTheDocument();
  });
});
