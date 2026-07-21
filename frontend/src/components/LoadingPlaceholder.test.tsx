import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import LoadingPlaceholder from './LoadingPlaceholder';

describe('LoadingPlaceholder', () => {
  it('renders with default 3 lines', () => {
    const { container } = render(<LoadingPlaceholder />);
    const lines = container.querySelectorAll('.h-4');
    expect(lines).toHaveLength(3);
  });

  it('renders with custom line count', () => {
    const { container } = render(<LoadingPlaceholder lines={5} />);
    const lines = container.querySelectorAll('.h-4');
    expect(lines).toHaveLength(5);
  });

  it('has accessible label', () => {
    render(<LoadingPlaceholder />);
    expect(screen.getByLabelText('Loading content')).toBeInTheDocument();
  });
});
