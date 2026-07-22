/**
 * WCAG 2.1 Contrast Ratio Utility
 *
 * Implements the relative luminance and contrast ratio calculations
 * per WCAG 2.1 specification:
 * https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
 * https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
 */

/**
 * Parse a hex colour string (#RRGGBB) into [R, G, B] values (0–255).
 */
export function hexToRgb(hex: string): [number, number, number] {
  const sanitised = hex.replace('#', '');
  if (sanitised.length !== 6) {
    throw new Error(`Invalid hex colour: ${hex}`);
  }
  const r = parseInt(sanitised.slice(0, 2), 16);
  const g = parseInt(sanitised.slice(2, 4), 16);
  const b = parseInt(sanitised.slice(4, 6), 16);
  return [r, g, b];
}

/**
 * Convert an 8-bit sRGB channel value to its linear component.
 * Per WCAG: if value <= 0.04045, linear = value / 12.92
 *           else linear = ((value + 0.055) / 1.055) ^ 2.4
 */
function linearise(channel: number): number {
  const srgb = channel / 255;
  return srgb <= 0.04045
    ? srgb / 12.92
    : Math.pow((srgb + 0.055) / 1.055, 2.4);
}

/**
 * Calculate the relative luminance of a colour.
 * L = 0.2126 * R + 0.7152 * G + 0.0722 * B
 */
export function relativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * linearise(r) + 0.7152 * linearise(g) + 0.0722 * linearise(b);
}

/**
 * Calculate the WCAG contrast ratio between two colours.
 * Returns a value >= 1 (e.g. 4.5 means 4.5:1).
 */
export function getContrastRatio(foreground: string, background: string): number {
  const l1 = relativeLuminance(foreground);
  const l2 = relativeLuminance(background);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}
