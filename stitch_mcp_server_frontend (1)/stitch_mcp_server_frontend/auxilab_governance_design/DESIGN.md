---
name: Auxilab Governance Design
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#0051d5'
  on-secondary: '#ffffff'
  secondary-container: '#316bf3'
  on-secondary-container: '#fefcff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#0b1c30'
  on-tertiary-container: '#75859d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#d3e4fe'
  tertiary-fixed-dim: '#b7c8e1'
  on-tertiary-fixed: '#0b1c30'
  on-tertiary-fixed-variant: '#38485d'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
  status-success: '#10B981'
  status-error: '#EF4444'
  status-warning: '#F59E0B'
  status-info: '#3B82F6'
  status-manual: '#8B5CF6'
  agency-isolation-border: '#E2E8F0'
  grid-selection: '#EFF6FF'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  label-caps:
    fontFamily: Hanken Grotesk
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  container-max: 1440px
  grid-gutter: 1rem
  dashboard-padding: 2rem
  density-compact: 0.25rem
  density-default: 0.75rem
---

## Brand & Style

This design system is engineered for **Auxilab Expense Management**, an enterprise-grade platform where rigor, auditability, and deterministic accuracy are paramount. The brand personality is **authoritative, precise, and transparent**. It targets finance directors, auditors, and employees who require a high-trust environment to manage complex fiscal workflows.

The visual style is **Corporate / Modern**, leaning into functional minimalism. Every design decision serves the clarity of data and the "Defense-in-Depth" strategy. The UI avoids unnecessary ornamentation to prioritize the **Citation-First** approach—ensuring that AI-generated verdicts are always anchored by visible policy citations and audit trails. The result is a workspace that feels like a professional tool rather than a consumer app, emphasizing speed, compliance, and multi-agency isolation.

## Colors

The palette is anchored in a "Deep Navy" (`#0F172A`) to establish institutional trust. "Crisp White" backgrounds provide a clean canvas for dense data, while "Accent Blue" (`#2563EB`) guides user interaction and focus. 

The color system is heavily **semantic**, mapping directly to the platform’s state machine:
- **Success:** Used for approved and paid statuses.
- **Error:** High-visibility red for rejections and policy failures.
- **Warning:** Amber for info requests or uncertain policy flags.
- **Manual:** A distinct violet used exclusively for "Route-to-Human" operations, signaling a departure from automated workflows.
- **Neutral:** A slate-gray scale used for structural elements, secondary labels, and meta-data.

## Typography

This design system utilizes **Hanken Grotesk** as its primary typeface, chosen for its sharp, contemporary geometry that maintains high legibility in professional contexts. 

- **Primary Typeface:** Used for all standard UI elements, buttons, and navigation.
- **Data Monospace:** **JetBrains Mono** is introduced for IDs (Sheet ID, Line Item ID), currency values, and technical citations. This provides a clear visual distinction between descriptive text and "immutable" data tokens.
- **Scale Strategy:** Font sizes are kept tight (13px–16px for body) to facilitate high information density in AG Grid views. Large displays are reserved for high-level KPI tiles, while data grids prioritize compact vertical rhythm.

## Layout & Spacing

The layout employs a **Fixed Grid** philosophy for dashboards, ensuring consistent data visualization across desktop views, while allowing for fluid behavior within internal components.

- **Grid Strategy:** Built around **AG Grid Enterprise**, utilizing a **Master-Detail** layout. This allows users to view high-level expense sheets while simultaneously drilling into line items without losing context.
- **Density:** Optimized for "Compact" settings. Spacing between grid rows is minimized (4px–8px) to maximize the "above-the-fold" data points.
- **Responsive Behavior:** 
  - **Desktop (1280px+):** Full 12-column visibility with persistent sidebar navigation.
  - **Tablet (768px - 1279px):** Collapsible sidebar, transition to 2-column KPI stacks.
  - **Mobile (<768px):** Stacked cards replacing grids; "Master-Detail" transitions to a drill-down navigation flow.

## Elevation & Depth

To maintain a "flat but layered" professional look, the design system avoids heavy shadows in favor of **Tonal Layers** and **Low-Contrast Outlines**.

1.  **Background (Level 0):** Used for the main portal canvas (`#F8FAFC`).
2.  **Surface (Level 1):** White cards (`#FFFFFF`) with a 1px border (`#E2E8F0`) for forms, grids, and KPI tiles.
3.  **Raised (Level 2):** Subtle shadows (4px blur, 2% opacity) are used only for active state overlays, such as "Manual Intervention" side panels or context menus.
4.  **Isolation:** Thick vertical dividers are used to visually separate agency contexts in multi-tenant views, ensuring the user is always aware of their current fiscal environment.

## Shapes

The shape language is **Soft (0.25rem)**, reflecting a professional balance between modern friendliness and corporate structure.

- **Buttons & Inputs:** Use the standard `rounded` (4px) corner radius.
- **Status Badges:** Use `rounded-full` (pill-shaped) to distinguish status indicators from clickable interactive elements.
- **KPI Tiles:** Use `rounded-lg` (8px) to provide a soft container for high-level metrics.
- **Data Selection:** Square selection indicators within grids to reinforce the technical, precise nature of the platform.

## Components

- **AG Grid Enterprise:** The core of the platform. Use the "Alpine" theme with custom primary colors. Enable filtering, sorting, and row-grouping by default.
- **Status Badges:** Compact, pill-shaped labels using low-saturation backgrounds with high-saturation text of the same hue (e.g., Success: light green bg, dark green text).
- **KPI Tiles (Tremor-inspired):** Use bold display typography for the metric, a sub-label for the description, and a sparkline for trend visualization.
- **AI Citation Links:** Specialized components that combine a Lucide "Link" icon with a monospaced "Policy ID" tag. These must appear adjacent to any AI-generated text.
- **Action Buttons:**
    - **Primary:** Deep navy with white text for main actions (e.g., "Submit Sheet").
    - **Destructive:** Solid status-error for "Reject".
    - **Ghost:** Minimal borderless buttons for secondary grid actions like "View Receipt".
- **Inputs:** Crisp, 1px bordered fields that focus with the Accent Blue highlight. Use `placeholder` text sparingly to maintain density.
- **Role-Cues:** Visual headers or subtle background tints that change based on whether the user is in "Employee," "Manager," or "Finance" role view.