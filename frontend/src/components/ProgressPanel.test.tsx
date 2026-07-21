import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ProgressPanel from './ProgressPanel';

describe('ProgressPanel', () => {
  const defaultProps = {
    currentStep: 4,
    stepName: 'Constraint Pruning',
    score: 87.45,
    isRunning: true,
    error: null,
  };

  it('renders the step name', () => {
    render(<ProgressPanel {...defaultProps} />);
    expect(screen.getByText('Constraint Pruning')).toBeInTheDocument();
  });

  it('renders the current step number', () => {
    render(<ProgressPanel {...defaultProps} />);
    expect(screen.getByText('4/8')).toBeInTheDocument();
  });

  it('renders the objective score formatted to 2 decimal places', () => {
    render(<ProgressPanel {...defaultProps} score={87.4} />);
    expect(screen.getByText('87.40')).toBeInTheDocument();
  });

  it('shows running indicator when isRunning is true', () => {
    render(<ProgressPanel {...defaultProps} isRunning={true} />);
    expect(screen.getByText('Optimising...')).toBeInTheDocument();
  });

  it('does not show running indicator when isRunning is false', () => {
    render(<ProgressPanel {...defaultProps} isRunning={false} />);
    expect(screen.queryByText('Optimising...')).not.toBeInTheDocument();
  });

  it('displays error state when error is provided', () => {
    render(
      <ProgressPanel
        {...defaultProps}
        error={{ step: 3, message: 'Google Maps API timeout' }}
      />
    );
    expect(screen.getByText('Optimisation Failed at Step 3')).toBeInTheDocument();
    expect(screen.getByText('Google Maps API timeout')).toBeInTheDocument();
  });

  it('shows last known score in error state', () => {
    render(
      <ProgressPanel
        {...defaultProps}
        score={65.23}
        error={{ step: 5, message: 'Solver error' }}
      />
    );
    expect(screen.getByText('65.23')).toBeInTheDocument();
  });

  it('has alert role in error state', () => {
    render(
      <ProgressPanel
        {...defaultProps}
        error={{ step: 2, message: 'Connection lost' }}
      />
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('has status role in normal state', () => {
    render(<ProgressPanel {...defaultProps} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has aria-live polite for real-time updates', () => {
    render(<ProgressPanel {...defaultProps} />);
    const panel = screen.getByRole('status');
    expect(panel).toHaveAttribute('aria-live', 'polite');
  });
});
