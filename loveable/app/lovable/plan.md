## Goal

Create a modernised, cohesive digital brand system for **Winserve Care Services Ltd** — a CQC-registered domiciliary & supported-living care provider in Leeds and Cornwall — inspired by the existing site (winservecare.co.uk) but elevated for a new website and wider digital use (social, email, print-ready).

Deliverables land as project files so you can drop them straight into the new website repo (or download them).

## Brand direction

Evolved from the current identity (heart + figure mark, blue/red wordmark, warm serif tone), but tightened for digital:

- **Personality:** warm, trustworthy, professional, human. Not clinical, not corporate-cold.
- **Visual metaphor:** protective embrace — the heart & caregiver figure kept, redrawn with cleaner geometry and a single confident stroke weight.
- **Colour palette (proposed):**
  - Trust Blue `#1E5FAD` (primary — evolved from current blue)
  - Warm Coral `#E8624B` (accent — evolved from the current red, warmer & friendlier)
  - Soft Sand `#F6F1EA` (background surface)
  - Deep Ink `#0F2340` (text)
  - Sage `#7FA894` (secondary accent for wellbeing/CSR contexts)
- **Typography pairing:** *Fraunces* (display serif, humanist warmth) + *Inter* (UI/body, high legibility for accessibility). Both free, Google Fonts, WCAG-friendly.
- **Tone principles:** plain English, first-person plural, accessibility-first (AA contrast minimum).

## Deliverables

### 1. `brand/winserve-brand-guidelines.md`
A single Markdown brand guide covering:
- Brand story & positioning
- Logo usage (primary, stacked, mark-only, monochrome, clear-space, min sizes, misuse)
- Colour system with hex/RGB/HSL + accessibility pairings
- Typography scale (H1–H6, body, caption) with rem values
- Iconography rules & stroke system
- Photography direction (natural light, real hands, Leeds/Cornwall settings)
- Voice & tone with do/don't examples
- Digital application notes (web, favicon, social avatars, email signature)
- Accessibility checklist (contrast, alt text, motion)

### 2. `brand/svg/` — SVG asset set
- `logo-primary.svg` — horizontal wordmark + mark, full colour
- `logo-stacked.svg` — mark above wordmark
- `logo-mark.svg` — heart+caregiver mark only (favicon/avatar)
- `logo-mono-dark.svg` — single-colour dark
- `logo-mono-light.svg` — single-colour light (for photo overlays)
- `wordmark.svg` — type only
- `favicon.svg`
- `pattern-hearts.svg` — subtle repeating background pattern
- **Icon set** (24px grid, 1.75px stroke, rounded caps) covering the service areas:
  `icon-home-care.svg`, `icon-supported-living.svg`, `icon-complex-care.svg`, `icon-team.svg`, `icon-cqc.svg`, `icon-family.svg`, `icon-24-7.svg`, `icon-leeds-cornwall.svg`, `icon-heart.svg`, `icon-shield.svg`

### 3. `brand/README.md`
Short index + quick-start showing how to use the tokens in the new TanStack Start site (CSS variable snippets that mirror `src/styles.css` conventions).

## Out of scope (this task)

- No changes to app routes, components, or `src/styles.css` — this task produces the brand kit as files under `brand/`. Rolling the tokens into the live site is a follow-up.
- No raster exports (PNG/JPG). SVGs are source of truth; PNGs can be generated later if needed.
- No new photography — direction notes only.

## Technical notes

- All SVGs hand-authored, optimised, `viewBox`'d, no embedded rasters, `currentColor` where the mark should inherit CSS colour (mono variants).
- Colour tokens in the MD guide are provided in both hex and `oklch()` so they map cleanly onto the project's existing `src/styles.css` design-token pattern later.
- Fonts referenced by name only; loaded via `<link>` in `__root.tsx` when integrated (per project's Tailwind v4 rule against remote `@import` in CSS).

Approve and I'll generate the Markdown guide and the full SVG set.