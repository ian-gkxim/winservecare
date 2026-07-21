import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MapControls from './MapControls';

describe('MapControls', () => {
  const defaultProps = {
    isPaused: false,
    isRunning: true,
    currentStep: 3,
    stepName: 'Assignment Graph',
    onPause: vi.fn(),
    onResume: vi.fn(),
  };

  it('renders the current step number and total', () => {
    render(<MapControls {...defaultProps} />);
    expect(screen.getByText('Step 3 of 8')).toBeInTheDocument();
  });

  it('renders the step name', () => {
    render(<MapControls {...defaultProps} />);
    expect(screen.getByText('Assignment Graph')).toBeInTheDocument();
  });

  it('shows pause button when running and not paused', () => {
    render(<MapControls {...defaultProps} isPaused={false} isRunning={true} />);
    const button = screen.getByLabelText('Pause animation');
    expect(button).toBeInTheDocument();
    expect(button.textContent).toBe('⏸');
  });

  it('shows play button when paused', () => {
    render(<MapControls {...defaultProps} isPaused={true} isRunning={true} />);
    const button = screen.getByLabelText('Resume animation');
    expect(button).toBeInTheDocument();
    expect(button.textContent).toBe('▶');
  });

  it('calls onPause when pause button is clicked', () => {
    const onPause = vi.fn();
    render(<MapControls {...defaultProps} isPaused={false} onPause={onPause} />);
    fireEvent.click(screen.getByLabelText('Pause animation'));
    expect(onPause).toHaveBeenCalledOnce();
  });

  it('calls onResume when play button is clicked while paused', () => {
    const onResume = vi.fn();
    render(<MapControls {...defaultProps} isPaused={true} onResume={onResume} />);
    fireEvent.click(screen.getByLabelText('Resume animation'));
    expect(onResume).toHaveBeenCalledOnce();
  });

  it('disables the button when not running', () => {
    render(<MapControls {...defaultProps} isRunning={false} />);
    const button = screen.getByLabelText('Pause animation');
    expect(button).toBeDisabled();
  });

  it('renders 8 step indicator dots', () => {
    const { container } = render(<MapControls {...defaultProps} currentStep={5} />);
    const dots = container.querySelectorAll('[aria-hidden="true"]');
    expect(dots).toHaveLength(8);
  });

  it('has toolbar role for accessibility', () => {
    render(<MapControls {...defaultProps} />);
    expect(screen.getByRole('toolbar')).toBeInTheDocument();
  });
});
