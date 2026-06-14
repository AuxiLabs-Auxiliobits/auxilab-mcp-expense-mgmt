---
name: Auxilio Compliance
colors:
  surface: '#fbf9f8'
  surface-dim: '#dcd9d9'
  surface-bright: '#fbf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f2'
  surface-container: '#f0eded'
  surface-container-high: '#eae8e7'
  surface-container-highest: '#e4e2e1'
  on-surface: '#1b1c1c'
  on-surface-variant: '#603e39'
  inverse-surface: '#303030'
  inverse-on-surface: '#f3f0f0'
  outline: '#956d67'
  outline-variant: '#ebbbb4'
  surface-tint: '#c00100'
  primary: '#bc0100'
  on-primary: '#ffffff'
  primary-container: '#ea0100'
  on-primary-container: '#fffbff'
  inverse-primary: '#ffb4a8'
  secondary: '#5f5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e2dfde'
  on-secondary-container: '#636262'
  tertiary: '#006480'
  on-tertiary: '#ffffff'
  tertiary-container: '#1c7e9e'
  on-tertiary-container: '#fbfdff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdad4'
  primary-fixed-dim: '#ffb4a8'
  on-primary-fixed: '#410000'
  on-primary-fixed-variant: '#930100'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474746'
  tertiary-fixed: '#bde9ff'
  tertiary-fixed-dim: '#7fd1f5'
  on-tertiary-fixed: '#001f2a'
  on-tertiary-fixed-variant: '#004d64'
  background: '#fbf9f8'
  on-background: '#1b1c1c'
  surface-variant: '#e4e2e1'
  signal-red: '#FF0100'
  deep-onyx: '#111110'
  slate-muted: '#69727D'
  surface-alt: '#F6F6F6'
  success-green: '#61CE70'
typography:
  headline-xl:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-page: 40px
  margin-mobile: 16px
  container-max: 1440px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

This design system is engineered for high-stakes financial environments where precision, transparency, and authority are paramount. It adopts a **Corporate Modern** aesthetic characterized by structural rigour and a "tech-forward" enterprise feel.

The visual language balances the stark, high-contrast energy of a fintech startup with the sober, reliable architecture required for global governance. This is achieved through a strict monochromatic foundation punctuated by a singular, aggressive "Signal Red" that highlights critical actions and compliance status. The interface relies on deep blacks and pure whites to establish a clear hierarchy, utilizing subtle structural lines rather than heavy shadows to maintain a clean, performant workspace.

## Colors

The palette is driven by "Signal Red," a high-chroma primary used sparingly for brand presence, primary calls to action, and critical alerts. The majority of the interface operates on a grayscale spectrum to ensure maximum readability and long-session comfort.

- **Primary:** Reserved for the logo, primary buttons, and active indicators.
- **Secondary:** Used for global navigation and high-level structural containers.
- **Tertiary:** A secondary blue-sky accent used specifically for information-level highlights or secondary data points to avoid "red-fatigue."
- **Neutrals:** A range of grays from `#111110` (Deep Onyx) for text to `#F6F6F6` for background layering.

## Typography

The system utilizes **Hanken Grotesk** as the primary typeface for its sharp, contemporary geometry which reflects a professional, tech-forward identity. It offers excellent legibility in dense data environments. 

For technical metadata, compliance codes, and status labels, **JetBrains Mono** is employed. This monospaced choice introduces a "developer-grade" precision to the governance platform, signaling that the data is structured and system-verified. All headlines use tighter letter-spacing to maintain a compact, authoritative feel.

## Layout & Spacing

This design system uses a **Fixed Grid** model for desktop to ensure data density remains predictable across large monitors. A 12-column grid is standard, with a focus on "Stacking" logic for vertical rhythm.

- **Desktop:** 12-column grid, 24px gutters, 40px minimum side margins.
- **Tablet:** 8-column grid, 16px gutters, 24px side margins.
- **Mobile:** 4-column fluid grid, 16px gutters, 16px side margins.

The spacing system is built on a 4px base unit. Alignment is strictly enforced to create a sense of order—essential for financial compliance tools where misalignment can be interpreted as a lack of technical integrity.

## Elevation & Depth

To maintain a "flat" professional aesthetic, depth is communicated through **Tonal Layering** and **Low-Contrast Outlines** rather than heavy shadows.

- **Level 0 (Background):** Pure White (#FFFFFF) or Surface Alt (#F6F6F6).
- **Level 1 (Cards/Containers):** White background with a 1px solid border (#E1E1E1). No shadow.
- **Level 2 (Dropdowns/Modals):** White background with a thin border and a "Hard" ambient shadow (8px blur, 4% opacity, #000000) to distinguish it from the base layout.
- **Interactions:** Hover states should utilize subtle shifts in background color (e.g., White to #F6F6F6) rather than elevation changes.

## Shapes

The shape language is **Soft (0.25rem)**. This slight rounding takes the "edge" off the brutalist monochromatic palette, making the software feel modern and accessible without losing its serious, institutional character.

- **Small elements (Buttons, Inputs, Chips):** 4px (rounded-sm)
- **Medium elements (Cards, Modals):** 8px (rounded-lg)
- **Large elements (Outer containers):** 12px (rounded-xl)
- **Icons:** Should follow a geometric, 2px stroke weight style to match the typography.

## Components

### Buttons
- **Primary:** Solid Signal Red (#FF0100) with White text. Rectangular with 4px corner radius.
- **Secondary:** Solid Deep Onyx (#111110) with White text.
- **Ghost:** 1px border (#333333) with matching text.

### Input Fields
- **Default:** White background, 1px border (#BABABA), Hanken Grotesk Body-sm text.
- **Focus:** 1px border becomes Signal Red (#FF0100) with a faint 2px outer glow of the same color.
- **Labels:** Always use JetBrains Mono Label-md in Slate-muted (#69727D) above the field.

### Chips & Tags
- **Compliance Tag:** Small JetBrains Mono text. Uses light tints of gray (#E1E1E1) for neutral states and Success Green (#61CE70) for "Verified" states.

### Cards
- White fill, 1px border (#E1E1E1), no shadow. Headers within cards should have a subtle #F6F6F6 bottom-border to separate title from content.

### Data Tables
- Header row uses Deep Onyx (#111110) background with White JetBrains Mono text.
- Alternating row stripes are not used; instead, use 1px horizontal dividers (#E1E1E1).