# Winserve Care Services — Brand Guidelines

**Version 1.0** · Digital brand system for winservecare.co.uk and related channels.

> *Care is at the heart of what we do.*

Winserve Care Services Ltd is a CQC-registered provider of domiciliary care, supported living, and complex care in Leeds and Cornwall. This document defines the visual and verbal system for the refreshed digital brand.

---

## 1. Brand story

**Who we are.** A team of 70+ caregivers working alongside local councils and the NHS to deliver personalised care in people's own homes.

**What we stand for.** Warmth, trust, competence, and dignity. Every service user is treated as an extended member of our family.

**How we sound.** Human, plain-spoken, calm, confident. We don't use clinical jargon when a plain word will do.

**Positioning line.** *Personalised care, trusted support — at home, where it matters most.*

---

## 2. Logo system

The mark is a caregiver figure enclosed by a heart — a protective embrace. It is redrawn from the legacy mark with cleaner geometry, a single stroke weight, and better performance at small sizes.

| Variant | File | Use |
| --- | --- | --- |
| Primary (horizontal) | `svg/logo-primary.svg` | Web headers, letterhead, primary applications |
| Stacked | `svg/logo-stacked.svg` | Social avatars, square placements, business cards |
| Mark only | `svg/logo-mark.svg` | Favicons, app icons, watermark |
| Wordmark only | `svg/wordmark.svg` | Where the mark already appears nearby |
| Mono — dark | `svg/logo-mono-dark.svg` | On light backgrounds, single-colour print |
| Mono — light | `svg/logo-mono-light.svg` | On photography, dark backgrounds |
| Favicon | `svg/favicon.svg` | Browser tab icon |

### Clear space

Maintain clear space equal to the height of the "W" in *WINSERVE* on all sides.

### Minimum sizes

- Primary lockup: **120 px** wide on screen, **28 mm** in print.
- Mark only: **24 px** on screen, **8 mm** in print.

### Misuse

Do not: recolour outside the palette · stretch or skew · add drop shadows or bevels · place on low-contrast photography without the mono-light variant · rotate · reconstruct with different type.

---

## 3. Colour system

Evolved from the current blue-and-red palette — warmer, more accessible, and better suited to long-form digital reading.

| Token | Name | Hex | RGB | oklch | Role |
| --- | --- | --- | --- | --- | --- |
| `--brand-primary` | Trust Blue | `#1E5FAD` | 30 95 173 | `oklch(0.505 0.153 258)` | Primary brand, links, CTAs |
| `--brand-accent` | Warm Coral | `#E8624B` | 232 98 75 | `oklch(0.665 0.174 32)` | Emphasis, highlights, hover states |
| `--brand-ink` | Deep Ink | `#0F2340` | 15 35 64 | `oklch(0.245 0.062 258)` | Headings, body text |
| `--brand-surface` | Soft Sand | `#F6F1EA` | 246 241 234 | `oklch(0.960 0.012 78)` | Page background, cards |
| `--brand-sage` | Sage | `#7FA894` | 127 168 148 | `oklch(0.680 0.052 155)` | Wellbeing, CSR, secondary |
| `--brand-cloud` | Cloud | `#FFFFFF` | 255 255 255 | `oklch(1 0 0)` | Surface, contrast base |
| `--brand-mist` | Mist | `#DDE4EC` | 221 228 236 | `oklch(0.910 0.014 245)` | Borders, dividers |

### Accessibility pairings (WCAG AA)

- Deep Ink on Soft Sand — **13.9 : 1** ✅ (body copy)
- Cloud on Trust Blue — **6.8 : 1** ✅ (buttons)
- Cloud on Warm Coral — **3.5 : 1** — large text / icons only
- Trust Blue on Soft Sand — **7.4 : 1** ✅ (links)

Never place Warm Coral text under 18 px on Soft Sand — use Deep Ink instead and reserve Coral for icons, underlines, and shapes.

---

## 4. Typography

| Role | Family | Weight | Notes |
| --- | --- | --- | --- |
| Display / H1–H2 | **Fraunces** | 500 · Soft optical size 96 | Humanist serif — warmth, editorial confidence |
| Headings H3–H6 | **Fraunces** | 500 | Same family, tighter tracking |
| Body / UI | **Inter** | 400 / 500 / 600 | High legibility, accessible at small sizes |
| Data / captions | **Inter** | 500 | Tabular numerals on figures |

Both fonts are free via Google Fonts. Load with a single `<link rel="stylesheet">` in the root document head. Do not `@import` remote fonts in CSS (Tailwind v4 constraint).

### Type scale (rem, base 16 px)

| Token | Size | Line-height | Use |
| --- | --- | --- | --- |
| `display` | 4.5 / 5.5 | 1.05 | Hero |
| `h1` | 3 | 1.1 | Page title |
| `h2` | 2.25 | 1.15 | Section |
| `h3` | 1.5 | 1.25 | Subsection |
| `h4` | 1.25 | 1.3 | Card title |
| `body-lg` | 1.125 | 1.6 | Lede |
| `body` | 1 | 1.6 | Default |
| `small` | 0.875 | 1.5 | Meta, captions |

---

## 5. Iconography

- 24 × 24 px grid, 1.75 px stroke, rounded caps and joins.
- Single stroke colour via `currentColor` — icons inherit their parent's `color`.
- No fills except where meaning demands it (e.g. filled heart).
- See `svg/icon-*.svg` for the starter set: home care, supported living, complex care, team, CQC, family, 24/7, Leeds & Cornwall, heart, shield.

---

## 6. Photography direction

- **Real people, real hands.** Prefer close crops of hands, cups of tea, doorsteps, gardens — moments over posed portraits.
- **Natural light**, warm white balance, no heavy filters.
- **Settings** reflect Leeds and Cornwall: terraced streets, coastal villages, kitchens, front rooms.
- Avoid: stock "medical" imagery, scrubs and clipboards, staged smiles, purple-tinted "healthcare" gradients.
- Always secure written consent from service users before use.

---

## 7. Voice & tone

**Principles:** plain English · active voice · first-person plural ("we") · reading age 12.

| Do | Don't |
| --- | --- |
| "We'll visit at a time that suits you." | "Service provision is scheduled at the user's convenience." |
| "Care at home, from people you know." | "Person-centric domiciliary solutions." |
| "Call us on 0113 …" | "Please do not hesitate to contact our office." |

Use the em-dash — sparingly — for warmth. Use British English throughout.

---

## 8. Digital applications

- **Web.** Trust Blue for interactive elements; Soft Sand as the default page surface; Deep Ink for text. Radius `12–16 px`. Generous whitespace (min. 32 px between blocks).
- **Favicon.** `svg/favicon.svg` — mark only, on transparent.
- **Social avatars.** `svg/logo-stacked.svg` in a Soft Sand circle.
- **Email signatures.** Wordmark 140 px wide, Deep Ink text, Trust Blue links.
- **Motion.** Subtle: 200–300 ms ease-out fades and 8 px slides. No parallax, no auto-playing video with sound. Honour `prefers-reduced-motion`.

---

## 9. Accessibility checklist

- All text meets WCAG **AA** contrast (4.5:1 body, 3:1 large).
- Every image has meaningful `alt` text; decorative images use `alt=""`.
- Focus states use a 2 px Trust Blue outline with 2 px offset.
- Tap targets ≥ 44 × 44 px.
- Language attribute set to `en-GB`.
- Respect `prefers-reduced-motion` and `prefers-color-scheme`.

---

## 10. File index

```
brand/
├── winserve-brand-guidelines.md    ← this document
├── README.md                       ← quick-start for developers
└── svg/
    ├── logo-primary.svg
    ├── logo-stacked.svg
    ├── logo-mark.svg
    ├── logo-mono-dark.svg
    ├── logo-mono-light.svg
    ├── wordmark.svg
    ├── favicon.svg
    ├── pattern-hearts.svg
    └── icon-*.svg (10 icons)
```

© Winserve Care Services Ltd. Brand system prepared 2026.
