import { readFileSync } from 'fs';
import { resolve } from 'path';
import { describe, it, expect } from 'vitest';

/**
 * SplashPage Brand Token Test
 *
 * Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8
 *
 * Verifies the SplashPage component uses brand token utility classes
 * instead of inline style declarations, and applies the correct brand tokens.
 * SVG inline attributes (fill, stroke) are excluded per Requirement 5.1.
 */

const componentSource = readFileSync(
  resolve(__dirname, '../pages/SplashPage.tsx'),
  'utf-8'
);

describe('SplashPage brand tokens', () => {
  describe('No inline style attributes for colour or fontFamily on non-SVG elements (Requirement 5.1)', () => {
    it('has no inline style attributes on non-SVG HTML elements', () => {
      // Extract only the non-SVG sections of the component.
      // We remove everything between <svg ...> and </svg> tags (inclusive)
      // to avoid flagging legitimate SVG inline attributes like fill/stroke.
      const withoutSvg = componentSource.replace(/<svg[\s\S]*?<\/svg>/g, '');

      // Check that no style={{ ... }} patterns remain for colour or fontFamily
      const inlineStylePattern = /style=\{\{[^}]*?(color|backgroundColor|fontFamily)[^}]*?\}\}/g;
      const matches = withoutSvg.match(inlineStylePattern);
      expect(matches).toBeNull();
    });

    it('has no inline style attribute at all on non-SVG elements', () => {
      const withoutSvg = componentSource.replace(/<svg[\s\S]*?<\/svg>/g, '');
      // Check for any style={{ ... }} pattern on non-SVG elements
      const anyInlineStyle = /style=\{\{/g;
      const matches = withoutSvg.match(anyInlineStyle);
      expect(matches).toBeNull();
    });
  });

  describe('Brand token class usage (Requirements 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8)', () => {
    it('uses bg-brand-sand on root container (Requirement 5.2)', () => {
      expect(componentSource).toContain('bg-brand-sand');
    });

    it('uses text-brand-ink for tagline heading (Requirement 5.3)', () => {
      expect(componentSource).toContain('text-brand-ink');
    });

    it('uses bg-brand-primary and text-brand-cloud on CTA button (Requirement 5.4)', () => {
      expect(componentSource).toContain('bg-brand-primary');
      expect(componentSource).toContain('text-brand-cloud');
    });

    it('uses font-display on tagline heading (Requirement 5.5)', () => {
      expect(componentSource).toContain('font-display');
    });

    it('uses font-body for body text and footer (Requirement 5.6)', () => {
      expect(componentSource).toContain('font-body');
    });

    it('uses text-brand-sage for footer copyright text (Requirement 5.7)', () => {
      expect(componentSource).toContain('text-brand-sage');
    });

    it('uses text-brand-primary for subtitle text (Requirement 5.8)', () => {
      expect(componentSource).toContain('text-brand-primary');
    });
  });
});
