import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import DashboardPage from './DashboardPage';

// Mock the API services
vi.mock('../services/api', () => ({
  getKpis: vi.fn().mockResolvedValue({ totalVisits: 10, carersAvailable: 5 }),
  generateVisits: vi.fn().mockResolvedValue({ visits: [] }),
  getVisitsByDate: vi.fn().mockResolvedValue([]),
}));

// Mock the useOptimisation hook
vi.mock('../hooks/useOptimisation', () => ({
  useOptimisation: () => ({
    isRunning: false,
    isPaused: false,
    currentStep: 0,
    steps: [],
    progress: 0,
    result: null,
    error: null,
    solverProgress: null,
    startOptimisation: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
  }),
}));

/**
 * DashboardPage brand token tests
 * Validates: Requirements 6.1, 6.2, 6.3, 6.7
 */
describe('DashboardPage brand tokens', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses bg-brand-primary on primary action buttons', () => {
    render(<DashboardPage />);

    const runButton = screen.getByRole('button', { name: /run optimisation/i });
    expect(runButton.className).toContain('bg-brand-primary');
    expect(runButton.className).toContain('text-brand-cloud');
  });

  it('uses text-brand-ink on heading elements', () => {
    const { container } = render(<DashboardPage />);

    const h1 = container.querySelector('h1');
    expect(h1).not.toBeNull();
    expect(h1!.className).toContain('text-brand-ink');
  });

  it('uses border-brand-mist on card borders', () => {
    const { container } = render(<DashboardPage />);

    // The map container and input border use border-brand-mist
    const borderedElements = container.querySelectorAll('[class*="border-brand-mist"]');
    expect(borderedElements.length).toBeGreaterThan(0);
  });

  it('does not contain generic colour utilities (blue-600, gray-900) in DashboardPage source', () => {
    const source = readFileSync(
      resolve(__dirname, './DashboardPage.tsx'),
      'utf-8'
    );

    // These generic utilities should have been replaced with brand tokens
    // in the DashboardPage component itself (Requirement 6.7)
    const forbiddenPatterns = [
      { pattern: /bg-blue-600/, description: 'bg-blue-600 (should be bg-brand-primary)' },
      { pattern: /hover:bg-blue-700/, description: 'hover:bg-blue-700 (should be hover:bg-brand-primary/90)' },
      { pattern: /text-gray-900/, description: 'text-gray-900 (should be text-brand-ink)' },
      { pattern: /border-gray-200/, description: 'border-gray-200 (should be border-brand-mist)' },
      { pattern: /bg-gray-50/, description: 'bg-gray-50 (should inherit from body)' },
      { pattern: /focus:ring-blue-500/, description: 'focus:ring-blue-500 (handled by base layer)' },
      { pattern: /focus:ring-blue-600/, description: 'focus:ring-blue-600 (handled by base layer)' },
    ];

    const violations: string[] = [];

    for (const { pattern, description } of forbiddenPatterns) {
      if (pattern.test(source)) {
        violations.push(`Found forbidden generic utility: ${description}`);
      }
    }

    expect(violations).toEqual([]);
  });
});
