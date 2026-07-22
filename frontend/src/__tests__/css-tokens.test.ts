import { readFileSync } from 'fs';
import { resolve } from 'path';

/**
 * CSS Token Verification Test
 *
 * Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 9.5, 10.5
 *
 * Parses index.css and verifies that all required brand tokens,
 * media queries, and base layer rules are declared.
 */

const css = readFileSync(resolve(__dirname, '../index.css'), 'utf-8');

describe('CSS custom properties in index.css', () => {
  describe('Brand colour tokens in :root (Requirement 1.1)', () => {
    const brandColourTokens = [
      '--brand-primary',
      '--brand-coral',
      '--brand-ink',
      '--brand-sand',
      '--brand-sage',
      '--brand-cloud',
      '--brand-mist',
    ];

    it('declares all 7 brand colour tokens in :root', () => {
      // Extract the top-level :root block (not nested inside media queries)
      const rootMatch = css.match(/:root\s*\{([^}]+)\}/);
      expect(rootMatch).not.toBeNull();
      const rootBlock = rootMatch![1];

      for (const token of brandColourTokens) {
        expect(rootBlock).toContain(token);
      }
    });
  });

  describe('Font tokens (Requirement 1.2)', () => {
    it('declares --font-display and --font-body tokens in :root', () => {
      const rootMatch = css.match(/:root\s*\{([^}]+)\}/);
      expect(rootMatch).not.toBeNull();
      const rootBlock = rootMatch![1];

      expect(rootBlock).toContain('--font-display');
      expect(rootBlock).toContain('--font-body');
    });
  });

  describe('Radius and spacing tokens (Requirements 1.3, 1.4)', () => {
    it('declares --radius-brand and --radius-brand-lg in :root', () => {
      const rootMatch = css.match(/:root\s*\{([^}]+)\}/);
      expect(rootMatch).not.toBeNull();
      const rootBlock = rootMatch![1];

      expect(rootBlock).toContain('--radius-brand');
      expect(rootBlock).toContain('--radius-brand-lg');
    });

    it('declares --spacing-block in :root', () => {
      const rootMatch = css.match(/:root\s*\{([^}]+)\}/);
      expect(rootMatch).not.toBeNull();
      const rootBlock = rootMatch![1];

      expect(rootBlock).toContain('--spacing-block');
    });
  });

  describe('Motion tokens (Requirement 1.5)', () => {
    it('declares --duration-fast, --duration-normal, and --ease-brand in :root', () => {
      const rootMatch = css.match(/:root\s*\{([^}]+)\}/);
      expect(rootMatch).not.toBeNull();
      const rootBlock = rootMatch![1];

      expect(rootBlock).toContain('--duration-fast');
      expect(rootBlock).toContain('--duration-normal');
      expect(rootBlock).toContain('--ease-brand');
    });
  });

  describe('Reduced motion media query (Requirement 9.5)', () => {
    it('includes @media (prefers-reduced-motion: reduce) rule', () => {
      expect(css).toContain('prefers-reduced-motion: reduce');
    });

    it('reduced motion rule is within @layer base', () => {
      // Find the @layer base block and check it contains the reduced motion query
      const layerBaseStart = css.indexOf('@layer base');
      expect(layerBaseStart).toBeGreaterThan(-1);

      const afterLayerBase = css.slice(layerBaseStart);
      expect(afterLayerBase).toContain('prefers-reduced-motion: reduce');
    });
  });

  describe('Dark mode media query (Requirement 10.5)', () => {
    it('includes @media (prefers-color-scheme: dark) rule', () => {
      expect(css).toContain('prefers-color-scheme: dark');
    });
  });

  describe('@layer base block with body defaults', () => {
    it('@layer base block exists', () => {
      expect(css).toContain('@layer base');
    });

    it('body defaults are set inside @layer base', () => {
      const layerBaseStart = css.indexOf('@layer base');
      expect(layerBaseStart).toBeGreaterThan(-1);

      const afterLayerBase = css.slice(layerBaseStart);
      expect(afterLayerBase).toContain('body {');
      expect(afterLayerBase).toContain('background-color: var(--brand-surface)');
      expect(afterLayerBase).toContain('color: var(--brand-ink)');
      expect(afterLayerBase).toContain('font-family: var(--font-body)');
    });
  });
});
