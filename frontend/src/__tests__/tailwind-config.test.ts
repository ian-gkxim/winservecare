import { describe, it, expect } from 'vitest';
import config from '../../tailwind.config.js';

const theme = config.theme?.extend;

describe('Tailwind brand extension', () => {
  describe('brand colours', () => {
    const expectedColours = [
      'primary',
      'coral',
      'ink',
      'sand',
      'sage',
      'cloud',
      'mist',
    ] as const;

    it('defines all brand colour keys', () => {
      const brandColours = (theme?.colors as Record<string, Record<string, string>>)?.brand;
      expect(brandColours).toBeDefined();

      for (const key of expectedColours) {
        expect(brandColours).toHaveProperty(key);
      }
    });

    it('each brand colour references var(--brand-*) syntax', () => {
      const brandColours = (theme?.colors as Record<string, Record<string, string>>)?.brand;

      for (const key of expectedColours) {
        expect(brandColours[key]).toMatch(/^var\(--brand-/);
      }
    });
  });

  describe('fontFamily', () => {
    it('defines fontFamily.display', () => {
      const fontFamily = theme?.fontFamily as Record<string, string[]>;
      expect(fontFamily?.display).toBeDefined();
      expect(fontFamily.display[0]).toBe('Fraunces');
    });

    it('defines fontFamily.body', () => {
      const fontFamily = theme?.fontFamily as Record<string, string[]>;
      expect(fontFamily?.body).toBeDefined();
      expect(fontFamily.body[0]).toBe('Inter');
    });
  });

  describe('borderRadius', () => {
    it('defines borderRadius.brand as 12px', () => {
      const borderRadius = theme?.borderRadius as Record<string, string>;
      expect(borderRadius?.brand).toBe('12px');
    });

    it('defines borderRadius.brand-lg as 16px', () => {
      const borderRadius = theme?.borderRadius as Record<string, string>;
      expect(borderRadius?.['brand-lg']).toBe('16px');
    });
  });

  describe('spacing', () => {
    it('defines spacing.block as 32px', () => {
      const spacing = theme?.spacing as Record<string, string>;
      expect(spacing?.block).toBe('32px');
    });
  });

  describe('transitionDuration', () => {
    it('defines transitionDuration.fast as 200ms', () => {
      const transitionDuration = theme?.transitionDuration as Record<string, string>;
      expect(transitionDuration?.fast).toBe('200ms');
    });

    it('defines transitionDuration.normal as 300ms', () => {
      const transitionDuration = theme?.transitionDuration as Record<string, string>;
      expect(transitionDuration?.normal).toBe('300ms');
    });
  });

  describe('transitionTimingFunction', () => {
    it('defines transitionTimingFunction.brand', () => {
      const transitionTimingFunction = theme?.transitionTimingFunction as Record<string, string>;
      expect(transitionTimingFunction?.brand).toBeDefined();
      expect(transitionTimingFunction.brand).toMatch(/var\(--ease-brand\)/);
    });
  });
});
