import { readFileSync } from 'fs';
import { resolve } from 'path';
import { describe, it, expect } from 'vitest';

/**
 * NavSidebar Brand Token Test
 *
 * Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
 *
 * Verifies the NavSidebar component uses brand token classes
 * and does not contain legacy generic colour utilities.
 */

const componentSource = readFileSync(
  resolve(__dirname, '../components/NavSidebar.tsx'),
  'utf-8'
);

describe('NavSidebar brand tokens', () => {
  describe('Brand token usage (Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6)', () => {
    it('uses bg-brand-ink for sidebar background (Requirement 4.1)', () => {
      expect(componentSource).toContain('bg-brand-ink');
    });

    it('uses bg-brand-primary for active nav item (Requirement 4.2)', () => {
      expect(componentSource).toContain('bg-brand-primary');
    });

    it('uses hover:bg-brand-ink/80 for hover state (Requirement 4.3)', () => {
      expect(componentSource).toContain('hover:bg-brand-ink/80');
    });

    it('uses text-brand-cloud for primary text colour (Requirement 4.4)', () => {
      expect(componentSource).toContain('text-brand-cloud');
    });

    it('uses border-brand-mist for header separator (Requirement 4.5)', () => {
      expect(componentSource).toContain('border-brand-mist');
    });

    it('uses text-brand-mist/70 for secondary text colour (Requirement 4.6)', () => {
      expect(componentSource).toContain('text-brand-mist/70');
    });
  });

  describe('No legacy generic colour utilities', () => {
    it('does not contain bg-gray-900', () => {
      expect(componentSource).not.toContain('bg-gray-900');
    });

    it('does not contain bg-blue-600', () => {
      expect(componentSource).not.toContain('bg-blue-600');
    });

    it('does not contain text-gray-300', () => {
      expect(componentSource).not.toContain('text-gray-300');
    });

    it('does not contain text-gray-400', () => {
      expect(componentSource).not.toContain('text-gray-400');
    });

    it('does not contain border-gray-700', () => {
      expect(componentSource).not.toContain('border-gray-700');
    });

    it('does not contain hover:bg-gray-800', () => {
      expect(componentSource).not.toContain('hover:bg-gray-800');
    });
  });
});
