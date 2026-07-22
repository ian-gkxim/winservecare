# Implementation Plan: Winserve Care Brand System

## Overview

This plan implements a centralised design-token architecture for the WinServe Care frontend. Tokens are declared as CSS custom properties in `index.css`, surfaced through Tailwind CSS v3.4 theme extensions in `tailwind.config.js`, and then consumed by migrated React components. Testing validates configuration integrity, component migration, and accessibility contrast ratios.

## Tasks

- [x] 1. Define CSS custom properties and base layer styles in index.css
  - [x] 1.1 Add `:root` block with all brand tokens (colours, fonts, radii, spacing, motion)
    - Declare `--brand-primary`, `--brand-coral`, `--brand-ink`, `--brand-sand`, `--brand-sage`, `--brand-cloud`, `--brand-mist` colour tokens
    - Declare `--font-display`, `--font-body` font-stack tokens
    - Declare `--radius-brand`, `--radius-brand-lg`, `--spacing-block` tokens
    - Declare `--duration-fast`, `--duration-normal`, `--ease-brand` motion tokens
    - Add `--brand-surface` semantic alias (defaults to Sand in light, Ink in dark)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.2 Add `@layer base` rules for body defaults, typography scale, and focus states
    - Set body background to `var(--brand-surface)`, text colour to `var(--brand-ink)`, font-family to `var(--font-body)`
    - Apply `-webkit-font-smoothing: antialiased` and `-moz-osx-font-smoothing: grayscale`
    - Include comment documenting `lang="en-GB"` requirement on html element
    - Apply Display_Font to h1–h6 with weight 500
    - Define heading size scale (h1: 3rem/1.1, h2: 2.25rem/1.15, h3: 1.5rem/1.25, h4: 1.25rem/1.3, h5: 1.125rem/1.4, h6: 1rem/1.5)
    - Set letter-spacing -0.01em for h1/h2, 0 for h3–h6
    - Apply Body_Font to p, label, span, li, ul, ol
    - Add `:focus-visible` rule for all interactive elements: 2px solid Trust Blue outline, 2px offset
    - Add default transition properties for colour, background-color, border-color, opacity, transform
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.1, 7.2, 7.3, 7.5, 9.1, 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 1.3 Add `@media (prefers-reduced-motion: reduce)` rule within `@layer base`
    - Set `transition-duration: 0ms` and `animation-duration: 0ms` on all elements
    - Reset `transform: none` on hover states
    - _Requirements: 9.2, 9.3, 9.4, 9.5_

  - [x] 1.4 Add `@media (prefers-color-scheme: dark)` rule overriding `:root` tokens
    - Remap `--brand-surface` to Deep Ink (#0F2340)
    - Remap `--brand-ink` to Soft Sand (#F6F1EA)
    - Add `--brand-focus-dark: #4A8BD4` for dark-mode focus outline
    - Adjust focus-visible outline colour in dark mode to use `--brand-focus-dark`
    - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6_

- [x] 2. Extend Tailwind configuration with brand tokens
  - [x] 2.1 Update `tailwind.config.js` with brand colour, font, radius, spacing, and motion extensions
    - Add `colors.brand` with all seven colour keys referencing CSS variables via `var()`
    - Add `fontFamily.display` and `fontFamily.body` arrays
    - Add `borderRadius.brand` (12px) and `borderRadius['brand-lg']` (16px)
    - Add `spacing.block` (32px)
    - Add `transitionDuration.fast` (200ms) and `transitionDuration.normal` (300ms)
    - Add `transitionTimingFunction.brand` referencing `var(--ease-brand)`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 3. Update index.html lang attribute
  - [x] 3.1 Change `<html lang="en">` to `<html lang="en-GB">` in `frontend/index.html`
    - _Requirements: 3.5_

- [x] 4. Checkpoint — Verify token layer and config
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Migrate NavSidebar component to brand tokens
  - [x] 5.1 Replace generic colour utilities with brand token classes in NavSidebar.tsx
    - Replace `bg-gray-900` with `bg-brand-ink`
    - Replace `bg-blue-600` (active state) with `bg-brand-primary`
    - Replace `hover:bg-gray-800` with `hover:bg-brand-ink/80`
    - Replace `text-white` / `text-gray-300` with `text-brand-cloud`
    - Replace `text-gray-400` subtitle with `text-brand-mist/70`
    - Replace `border-gray-700` with `border-brand-mist`
    - Replace inactive item `text-gray-300` with `text-brand-mist/70`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 6. Migrate SplashPage to brand tokens
  - [x] 6.1 Remove inline style declarations and apply brand utility classes in SplashPage.tsx
    - Replace `style={{ backgroundColor: '#F6F1EA' }}` with `bg-brand-sand` class
    - Replace inline `color: '#0F2340'` with `text-brand-ink` class on tagline
    - Replace inline `color: '#1E5FAD'` with `text-brand-primary` class on subtitle
    - Replace inline `backgroundColor: '#1E5FAD'` on button with `bg-brand-primary text-brand-cloud` classes
    - Replace inline fontFamily for Fraunces with `font-display` class
    - Replace inline fontFamily for Inter with `font-body` class
    - Replace inline `color: '#7FA894'` on footer with `text-brand-sage` class
    - Remove `focus:ring-2 focus:ring-blue-600` (now handled by base layer focus-visible rule)
    - Ensure no inline `style` attributes remain on non-SVG HTML elements for colour/font
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [x] 7. Migrate DashboardPage to brand tokens
  - [x] 7.1 Replace generic colour utilities with brand token classes in DashboardPage.tsx
    - Replace `bg-blue-600` on Run Optimisation button with `bg-brand-primary text-brand-cloud`
    - Replace `hover:bg-blue-700` with `hover:bg-brand-primary/90` (darkened variant)
    - Replace `text-gray-900` on h1 with `text-brand-ink`
    - Replace `border-gray-200` on card borders with `border-brand-mist`
    - Replace `text-gray-700` label colour with `text-brand-ink`
    - Replace `focus:ring-blue-500` with brand focus handled by base layer
    - Remove any `bg-gray-50` page background classes (inherit from body)
    - Ensure no generic blue-600, gray-900, gray-200, gray-50 utilities remain for branded elements
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [x] 8. Checkpoint — Verify component migrations
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Write configuration and token verification tests
  - [x]* 9.1 Write Tailwind config smoke test
    - Verify all brand colour keys exist and reference `var(--brand-*)` syntax
    - Verify fontFamily.display and fontFamily.body are defined
    - Verify borderRadius.brand and borderRadius['brand-lg'] values
    - Verify spacing.block equals 32px
    - Verify transitionDuration.fast (200ms) and transitionDuration.normal (300ms)
    - Verify transitionTimingFunction.brand is defined
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 9.2 Write CSS token verification test
    - Parse `index.css` and verify all 7 brand colour tokens exist in `:root`
    - Verify font, radius, spacing, and motion tokens are declared
    - Verify `prefers-reduced-motion` media query is present
    - Verify `prefers-color-scheme: dark` media query is present
    - Verify `@layer base` block exists with body defaults
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 9.5, 10.5_

- [x] 10. Write component migration and accessibility tests
  - [x]* 10.1 Write NavSidebar brand token test
    - Verify sidebar uses `bg-brand-ink` class
    - Verify active nav item uses `bg-brand-primary` class
    - Verify no instances of `bg-gray-900`, `bg-blue-600`, or `text-gray-300`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x]* 10.2 Write SplashPage brand token test
    - Verify no inline `style` attributes for colour or fontFamily on non-SVG elements
    - Verify `bg-brand-sand` on root container
    - Verify `font-display` on tagline heading
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [x]* 10.3 Write DashboardPage brand token test
    - Verify `bg-brand-primary` on primary action buttons
    - Verify no generic colour utilities (blue-600, gray-900) remain on branded elements
    - _Requirements: 6.1, 6.2, 6.3, 6.7_

  - [x]* 10.4 Write WCAG contrast ratio tests
    - Create a contrast-ratio utility function
    - Verify Deep Ink on Soft Sand >= 4.5:1
    - Verify Cloud on Trust Blue >= 4.5:1
    - Verify Trust Blue on Soft Sand >= 3:1 (focus outline)
    - Verify Warm Coral on Soft Sand >= 3:1 (large text only)
    - Verify Soft Sand on Deep Ink >= 4.5:1 (dark mode)
    - Verify dark mode focus outline (#4A8BD4) against Deep Ink >= 3:1
    - _Requirements: 7.4, 8.2, 8.3, 8.5, 10.4, 10.6_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The design explicitly states property-based testing is not applicable — all tests are example-based
- Test runner: `npm run test` (vitest run) in the `frontend/` directory
- fast-check is available but not needed for this feature
- SVG inline attributes (fill, stroke) are excluded from the "no inline styles" migration per Requirement 5.1

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "2.1"] },
    { "id": 2, "tasks": ["5.1", "6.1", "7.1"] },
    { "id": 3, "tasks": ["9.1", "9.2"] },
    { "id": 4, "tasks": ["10.1", "10.2", "10.3", "10.4"] }
  ]
}
```
