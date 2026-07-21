# Winserve Brand Kit

Digital brand assets for Winserve Care Services Ltd. See **[winserve-brand-guidelines.md](./winserve-brand-guidelines.md)** for the full system.

## Contents

- `winserve-brand-guidelines.md` — full brand guide (colour, type, voice, usage)
- `svg/` — logo lockups, favicon, pattern, and icon set

## Quick start — CSS tokens

Drop these into `src/styles.css` inside `:root` to adopt the brand palette in the TanStack Start app:

```css
:root {
  /* Brand */
  --brand-primary:  oklch(0.505 0.153 258);   /* #1E5FAD Trust Blue  */
  --brand-accent:   oklch(0.665 0.174 32);    /* #E8624B Warm Coral  */
  --brand-ink:      oklch(0.245 0.062 258);   /* #0F2340 Deep Ink    */
  --brand-surface:  oklch(0.960 0.012 78);    /* #F6F1EA Soft Sand   */
  --brand-sage:     oklch(0.680 0.052 155);   /* #7FA894 Sage        */
  --brand-mist:     oklch(0.910 0.014 245);   /* #DDE4EC Mist        */

  /* Map to shadcn semantic tokens */
  --background: var(--brand-surface);
  --foreground: var(--brand-ink);
  --primary: var(--brand-primary);
  --primary-foreground: oklch(1 0 0);
  --accent: var(--brand-accent);
  --accent-foreground: oklch(1 0 0);
  --border: var(--brand-mist);
}
```

## Quick start — fonts

Add to `src/routes/__root.tsx` `head().links`:

```ts
{ rel: "preconnect", href: "https://fonts.googleapis.com" },
{ rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
{
  rel: "stylesheet",
  href: "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap",
},
```

Then in `src/styles.css`:

```css
@theme inline {
  --font-serif: "Fraunces", ui-serif, Georgia, serif;
  --font-sans:  "Inter", ui-sans-serif, system-ui, sans-serif;
}
```

## Quick start — using SVGs

```tsx
import LogoPrimary from "@/../brand/svg/logo-primary.svg?url";
import IconHeart from "@/../brand/svg/icon-heart.svg?react";

<img src={LogoPrimary} alt="Winserve Care Services" width={200} />
<IconHeart className="h-6 w-6 text-[color:var(--brand-accent)]" />
```

Mono logos and all icons use `currentColor`, so they inherit CSS `color`.
