# Requirements Document

## Introduction

This feature establishes the Winserve Care brand design system across the entire frontend application. It replaces hardcoded inline styles and generic Tailwind utility classes with a centralised design-token architecture — CSS custom properties exposed through the Tailwind config — ensuring visual cohesion, accessibility compliance, and maintainability. The system covers colour, typography, spacing, radii, motion, and interaction patterns derived from the Winserve Care brand guidelines.

## Glossary

- **Token_System**: The combination of CSS custom properties defined in index.css and corresponding Tailwind theme extensions in tailwind.config.js that expose brand values as reusable utility classes
- **Brand_Palette**: The set of named colours: Trust Blue (#1E5FAD), Warm Coral (#E8624B), Deep Ink (#0F2340), Soft Sand (#F6F1EA), Sage (#7FA894), Cloud (#FFFFFF), Mist (#DDE4EC)
- **Tailwind_Config**: The tailwind.config.js file that extends the default Tailwind theme with brand-specific tokens
- **Base_Layer**: Styles declared within the Tailwind `@layer base` directive in index.css that apply default document-level styling
- **Interactive_Element**: Any clickable or focusable UI control including buttons, links, form inputs, and navigation items
- **NavSidebar**: The persistent left-hand navigation component (NavSidebar.tsx)
- **SplashPage**: The initial full-screen branded landing page (SplashPage.tsx)
- **DashboardPage**: The primary scheduling optimisation interface (DashboardPage.tsx)
- **Display_Font**: Fraunces, used for headings and display text (H1–H6)
- **Body_Font**: Inter, used for body copy, labels, and UI elements
- **Reduced_Motion**: The user preference indicated by the `prefers-reduced-motion: reduce` media query

## Requirements

### Requirement 1: CSS Custom Property Foundation

**User Story:** As a developer, I want brand values declared as CSS custom properties, so that tokens are defined in one place and can be consumed by Tailwind and any future tooling.

#### Acceptance Criteria

1. THE Token_System SHALL declare CSS custom properties for all seven Brand_Palette colours (--brand-primary, --brand-coral, --brand-ink, --brand-sand, --brand-sage, --brand-cloud, --brand-mist) inside a `:root` selector in index.css
2. THE Token_System SHALL declare CSS custom properties for Display_Font (--font-display: 'Fraunces', Georgia, serif) and Body_Font (--font-body: 'Inter', system-ui, sans-serif) font stacks inside the `:root` selector
3. THE Token_System SHALL declare CSS custom properties for border-radius values (--radius-brand: 12px and --radius-brand-lg: 16px) inside the `:root` selector
4. THE Token_System SHALL declare a CSS custom property for the minimum block spacing value (--spacing-block: 32px) inside the `:root` selector
5. THE Token_System SHALL declare CSS custom properties for transition duration (--duration-fast: 200ms, --duration-normal: 300ms) and easing (--ease-brand: ease-out) inside the `:root` selector

### Requirement 2: Tailwind Configuration Extension

**User Story:** As a developer, I want brand tokens available as Tailwind utility classes, so that I can style components with classes like `bg-brand-primary` and `font-display` instead of arbitrary values.

#### Acceptance Criteria

1. THE Tailwind_Config SHALL extend the colour palette with named keys (brand-primary, brand-coral, brand-ink, brand-sand, brand-sage, brand-cloud, brand-mist) where each key references the corresponding CSS custom property declared in Requirement 1 using `var()` syntax
2. THE Tailwind_Config SHALL extend the fontFamily configuration with `display` mapped to the Display_Font (Fraunces) followed by a serif fallback, and `body` mapped to the Body_Font (Inter) followed by a sans-serif fallback
3. THE Tailwind_Config SHALL extend the borderRadius configuration with `brand` mapped to 12px and `brand-lg` mapped to 16px
4. THE Tailwind_Config SHALL extend the spacing configuration with a `block` key mapped to exactly 32px (the fixed block spacing value)
5. THE Tailwind_Config SHALL extend the transitionDuration configuration with `fast` mapped to 200ms and `normal` mapped to 300ms
6. THE Tailwind_Config SHALL extend the transitionTimingFunction configuration with `brand` mapped to the ease-out easing token declared in Requirement 1

### Requirement 3: Base Layer Defaults

**User Story:** As a user, I want the application to have consistent baseline styling, so that every page inherits the brand look without requiring per-component overrides.

#### Acceptance Criteria

1. THE Base_Layer SHALL set the document body background colour to the Soft Sand CSS custom property token value
2. THE Base_Layer SHALL set the document default text colour to the Deep Ink CSS custom property token value
3. THE Base_Layer SHALL set the document default font family to the Body_Font CSS custom property token value
4. THE Base_Layer SHALL apply `-webkit-font-smoothing: antialiased` and `-moz-osx-font-smoothing: grayscale` to the document body
5. THE Base_Layer SHALL include a code comment in the `@layer base` block documenting that the html element in index.html must have the `lang` attribute set to `en-GB`

### Requirement 4: Navigation Sidebar Brand Application

**User Story:** As a user, I want the navigation sidebar to reflect the Winserve Care brand, so that the interface feels cohesive with the brand identity.

#### Acceptance Criteria

1. WHEN the NavSidebar renders, THE NavSidebar SHALL use the Deep Ink brand token (bg-brand-ink) as its background colour instead of generic gray-900
2. WHEN a navigation item is in the active state, THE NavSidebar SHALL use the Trust Blue brand token (bg-brand-primary) as the active item background colour instead of generic blue-600
3. WHEN a navigation item is hovered, THE NavSidebar SHALL use the Deep Ink brand token with 80% opacity (bg-brand-ink/80) as the hover background colour instead of generic gray-800
4. THE NavSidebar SHALL use the Cloud brand token (text-brand-cloud) as the primary text colour for navigation items and active-state text
5. THE NavSidebar SHALL use the Mist brand token (border-brand-mist) as the border colour for the header separator instead of generic gray-700
6. THE NavSidebar SHALL use the Mist brand token with reduced opacity (text-brand-mist/70) as the secondary text colour for the subtitle and inactive navigation item labels instead of generic gray-300 and gray-400

### Requirement 5: SplashPage Token Migration

**User Story:** As a developer, I want the SplashPage to consume brand tokens from the design system, so that inline style overrides are eliminated and the page stays synchronised with any future token updates.

#### Acceptance Criteria

1. WHEN the SplashPage renders, THE SplashPage SHALL use brand utility classes for all CSS colour and font-family values applied to HTML elements instead of inline style declarations, excluding colour attributes embedded within SVG markup
2. THE SplashPage SHALL use the Soft Sand brand token (`bg-brand-sand`) for the root container background colour
3. THE SplashPage SHALL use the Deep Ink brand token (`text-brand-ink`) for the tagline heading text colour
4. THE SplashPage SHALL use the Trust Blue brand token (`bg-brand-primary`) for the call-to-action button background and the Cloud brand token (`text-brand-cloud`) for the button text colour
5. THE SplashPage SHALL use the `font-display` utility class for the tagline heading instead of inline fontFamily styles
6. THE SplashPage SHALL use the `font-body` utility class for body text and the footer paragraph instead of inline fontFamily styles
7. THE SplashPage SHALL use the Sage brand token (`text-brand-sage`) for the footer copyright text colour
8. THE SplashPage SHALL use the Trust Blue brand token (`text-brand-primary`) for the subtitle text colour

### Requirement 6: Dashboard and Page Brand Application

**User Story:** As a user, I want all application pages to use the Winserve Care brand palette, so that the interface looks polished and cohesive throughout.

#### Acceptance Criteria

1. WHEN the DashboardPage renders, THE DashboardPage SHALL use the Trust Blue brand token for all primary action button backgrounds instead of generic blue-600, with Cloud brand token for button text
2. WHEN the DashboardPage renders, THE DashboardPage SHALL use the Deep Ink brand token for all heading elements (h1–h6) instead of generic gray-900
3. THE DashboardPage SHALL use the Mist brand token for card borders (1px solid) and horizontal dividers instead of generic gray-200
4. THE DashboardPage SHALL NOT apply an inline or component-level background colour class, allowing the Soft Sand body background (set in Base_Layer) to inherit through instead of overriding with bg-gray-50
5. WHEN any application page renders a primary call-to-action button, THE page SHALL apply the Trust Blue brand token for the button background with Cloud brand token for button text
6. WHEN a user hovers over a primary action button, THE page SHALL display a darkened Trust Blue variant as the hover background colour to indicate interactivity
7. THE DashboardPage SHALL contain zero instances of generic Tailwind colour utilities (blue-600, gray-900, gray-200, gray-50) for any element that has a corresponding brand token mapping

### Requirement 7: Accessibility — Focus States

**User Story:** As a keyboard user, I want clearly visible focus indicators on all interactive elements, so that I can navigate the application without a mouse.

#### Acceptance Criteria

1. WHEN an Interactive_Element receives keyboard focus, THE Token_System SHALL display a 2px solid outline using the Trust Blue brand token
2. WHEN an Interactive_Element receives keyboard focus, THE Token_System SHALL apply a 2px offset between the element edge and the focus outline
3. THE Token_System SHALL define the focus style as a reusable Tailwind utility or base-layer rule that applies to all Interactive_Elements without requiring per-component configuration
4. THE Token_System SHALL ensure the Trust Blue focus outline achieves a minimum 3:1 contrast ratio against both Soft Sand and Cloud background colours as required by WCAG 2.1 Success Criterion 1.4.11
5. THE Token_System SHALL apply focus outlines only on keyboard-initiated focus (using the :focus-visible selector) so that mouse-click interactions do not display the outline

### Requirement 8: Accessibility — Tap Targets and Contrast

**User Story:** As a mobile user, I want touch targets to be large enough to tap reliably, and as any user, I want text to be readable against its background.

#### Acceptance Criteria

1. THE Token_System SHALL ensure all Interactive_Elements have a minimum tap-target size of 44×44 CSS pixels, measured as the total clickable area including padding
2. THE Token_System SHALL ensure Deep Ink text on Soft Sand background meets WCAG AA contrast (minimum 4.5:1 ratio for text below 18px, minimum 3:1 ratio for text at or above 18px or bold text at or above 14px)
3. THE Token_System SHALL ensure Cloud text on Trust Blue background meets WCAG AA contrast (minimum 4.5:1 ratio for text below 18px, minimum 3:1 ratio for text at or above 18px or bold text at or above 14px)
4. THE Token_System SHALL NOT use Warm Coral for text below 18px rendered on a Soft Sand background
5. IF Warm Coral is used for text at or above 18px on a Soft Sand background, THEN THE Token_System SHALL ensure a minimum contrast ratio of 3:1
6. THE Token_System SHALL restrict Warm Coral usage to icons, decorative underlines, and non-text shapes when rendered on a Soft Sand background for elements below 18px text size
7. THE Token_System SHALL ensure a minimum spacing of 8 CSS pixels between adjacent Interactive_Elements to prevent accidental activation

### Requirement 9: Motion and Reduced-Motion Support

**User Story:** As a user who is sensitive to motion, I want animations to respect my operating-system preference, so that the interface does not cause discomfort.

#### Acceptance Criteria

1. THE Base_Layer SHALL define default transition properties using the brand duration (200–300ms) and easing (ease-out) tokens for colour, background-color, border-color, opacity, and transform properties
2. WHEN the user has enabled Reduced_Motion, THE Token_System SHALL set all transition-duration values to 0ms via the `@media (prefers-reduced-motion: reduce)` rule
3. WHEN the user has enabled Reduced_Motion, THE Token_System SHALL set all animation-duration values to 0ms via the same media query rule
4. WHEN the user has enabled Reduced_Motion, THE Token_System SHALL disable transform-based hover effects (such as scale) by resetting transform to none
5. THE Token_System SHALL implement Reduced_Motion support using a `@media (prefers-reduced-motion: reduce)` rule in index.css within the `@layer base` directive

### Requirement 10: Dark Mode Foundation (prefers-color-scheme)

**User Story:** As a user who prefers dark interfaces, I want the application to respect my system colour-scheme preference, so that the brand adapts to my environment.

#### Acceptance Criteria

1. WHEN the user has `prefers-color-scheme: dark` enabled, THE Token_System SHALL override the `:root` custom properties for background, text, and surface colours with dark-mode values, at minimum remapping `--brand-surface` to Deep Ink and `--brand-ink` to Soft Sand
2. WHEN in dark mode, THE Token_System SHALL set the body background colour to the Deep Ink token value (#0F2340)
3. WHEN in dark mode, THE Token_System SHALL set the default text colour to the Soft Sand token value (#F6F1EA)
4. WHEN in dark mode, THE Token_System SHALL maintain a minimum contrast ratio of 4.5:1 for normal text (below 18px) and 3:1 for large text (18px and above) on their respective background colours across all Brand_Palette pairings used in the interface
5. THE Token_System SHALL implement dark-mode overrides using a `@media (prefers-color-scheme: dark)` rule in index.css
6. WHEN in dark mode, THE Token_System SHALL ensure the focus outline (Trust Blue) remains visible against the Deep Ink background with a minimum contrast ratio of 3:1 between the outline colour and the adjacent background

### Requirement 11: Typography Scale

**User Story:** As a user, I want a consistent heading hierarchy using the brand display font, so that content structure is clear and visually appealing.

#### Acceptance Criteria

1. THE Base_Layer SHALL apply the Display_Font family to all heading elements (h1 through h6) with font-weight set to 500
2. THE Base_Layer SHALL apply the Body_Font family to paragraph, label, span, and list elements
3. THE Base_Layer SHALL define a heading font-size scale: h1 at 3rem (line-height 1.1), h2 at 2.25rem (line-height 1.15), h3 at 1.5rem (line-height 1.25), h4 at 1.25rem (line-height 1.3), h5 at 1.125rem (line-height 1.4), h6 at 1rem (line-height 1.5)
4. THE Token_System SHALL ensure the Body_Font uses weight 400 for body text, 500 for labels and captions, and 600–700 for emphasis and interactive element text
5. THE Base_Layer SHALL set heading letter-spacing to -0.01em for h1 and h2, and 0 for h3 through h6
