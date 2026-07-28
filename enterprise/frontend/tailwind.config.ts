import type { Config } from "tailwindcss";
import forms from "@tailwindcss/forms";
import containerQueries from "@tailwindcss/container-queries";
import animate from "tailwindcss-animate";

/**
 * Auxilab Expense Management — "Auxilio Compliance" design system.
 * Colors are CSS variables in channel format (`rgb(var(--x) / <alpha-value>)`)
 * so every token themes for light/dark (values in globals.css) while still
 * supporting opacity utilities like `bg-success-green/10`.
 */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const COLOR_NAMES = [
  "on-primary-fixed-variant",
  "surface-container",
  "surface-dim",
  "on-secondary-fixed-variant",
  "surface-variant",
  "secondary-fixed",
  "outline-variant",
  "inverse-primary",
  "on-error-container",
  "surface-alt",
  "primary-fixed",
  "tertiary-container",
  "on-surface",
  "on-secondary-container",
  "on-secondary",
  "surface-container-high",
  "primary",
  "error",
  "on-tertiary-fixed",
  "surface-container-low",
  "on-primary-fixed",
  "error-container",
  "on-secondary-fixed",
  "secondary-container",
  "on-surface-variant",
  "on-primary-container",
  "primary-fixed-dim",
  "on-tertiary-fixed-variant",
  "inverse-surface",
  "secondary-fixed-dim",
  "on-tertiary-container",
  "secondary",
  "on-background",
  "signal-red",
  "success-green",
  "outline",
  "background",
  "on-tertiary",
  "slate-muted",
  "surface",
  "on-primary",
  "primary-container",
  "tertiary",
  "on-error",
  "inverse-on-surface",
  "deep-onyx",
  "surface-container-lowest",
  "surface-container-highest",
  "surface-tint",
  "tertiary-fixed",
  "tertiary-fixed-dim",
  "surface-bright",
] as const;

const colors = Object.fromEntries(COLOR_NAMES.map((n) => [n, token(n)]));

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    extend: {
      colors,
      borderRadius: {
        sm: "0.125rem",
        DEFAULT: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
        full: "9999px",
      },
      spacing: {
        "stack-lg": "32px",
        "margin-mobile": "16px",
        gutter: "24px",
        "stack-md": "16px",
        "margin-page": "40px",
        unit: "4px",
        "stack-sm": "8px",
      },
      maxWidth: {
        "container-max": "1440px",
      },
      fontFamily: {
        // Inter only — one typeface across the entire app (no monospace).
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        "body-sm": ["var(--font-sans)"],
        "body-md": ["var(--font-sans)"],
        "body-lg": ["var(--font-sans)"],
        "headline-md": ["var(--font-sans)"],
        "headline-lg": ["var(--font-sans)"],
        "headline-xl": ["var(--font-sans)"],
        "headline-lg-mobile": ["var(--font-sans)"],
        "label-sm": ["var(--font-sans)"],
        "label-md": ["var(--font-sans)"],
      },
      fontSize: {
        // ── Enterprise type scale (Linear / Workday / M365 density) ──────────
        // Body 14, helper 12, table 13 — fixed sizes, no fluid headings.
        "body-sm": ["0.875rem", { lineHeight: "1.45", letterSpacing: "0", fontWeight: "400" }], // 14 — body
        "body-md": ["1rem", { lineHeight: "1.5", letterSpacing: "0", fontWeight: "400" }], // 16 — subheading
        "body-lg": ["1.125rem", { lineHeight: "1.45", letterSpacing: "-0.006em", fontWeight: "600" }], // 18 — card title (H3)
        // Headings — capped, dense, no clamp. H1 32 · H2 24 · H3/metric 20.
        "headline-md": [
          "1.25rem",
          { lineHeight: "1.35", letterSpacing: "-0.01em", fontWeight: "600" },
        ], // 20 — sub-section / KPI value
        "headline-lg": [
          "1.5rem",
          { lineHeight: "1.3", letterSpacing: "-0.014em", fontWeight: "600" },
        ], // 24 — section title (H2)
        "headline-xl": [
          "2rem",
          { lineHeight: "1.2", letterSpacing: "-0.02em", fontWeight: "700" },
        ], // 32 — page title (H1)
        "headline-lg-mobile": [
          "1.5rem",
          { lineHeight: "1.25", letterSpacing: "-0.014em", fontWeight: "600" },
        ], // 24
        // Mono labels — JetBrains Mono is loaded at 500 only; keep weight at 500.
        "label-sm": [
          "0.6875rem",
          { lineHeight: "1.4", letterSpacing: "0.04em", fontWeight: "500" },
        ], // 11
        "label-md": [
          "0.75rem",
          { lineHeight: "1.4", letterSpacing: "0.03em", fontWeight: "500" },
        ], // 12 — labels
      },
      boxShadow: {
        // ── Elevation model (slate-tinted, Untitled-UI style). Use sparingly. ──
        // Level 1 = resting cards · Level 2 = hover/menus · Level 3 = overlays.
        xs: "0 1px 2px rgba(16,24,40,0.04)", // Level 1
        sm: "0 1px 2px rgba(16,24,40,0.04)", // Level 1
        DEFAULT: "0 1px 2px rgba(16,24,40,0.04)",
        md: "0 4px 12px rgba(16,24,40,0.08)", // Level 2
        lg: "0 8px 24px rgba(16,24,40,0.12)", // Level 3
        xl: "0 8px 24px rgba(16,24,40,0.12)", // Level 3
        "elevation-1": "0 1px 2px rgba(16,24,40,0.04)",
        "elevation-2": "0 4px 12px rgba(16,24,40,0.08)",
        "elevation-3": "0 8px 24px rgba(16,24,40,0.12)",
        "elevation-4": "0 8px 24px rgba(16,24,40,0.12)",
        glow: "0 0 0 1px rgb(var(--primary) / 0.35), 0 8px 28px rgb(var(--primary) / 0.28)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.22, 1, 0.36, 1)",
        spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.96)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        "glow-pulse": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out both",
        "slide-up": "slide-up 0.4s cubic-bezier(0.22, 1, 0.36, 1) both",
        "scale-in": "scale-in 0.25s cubic-bezier(0.22, 1, 0.36, 1) both",
        float: "float 6s ease-in-out infinite",
        "glow-pulse": "glow-pulse 3s ease-in-out infinite",
      },
    },
  },
  plugins: [forms, containerQueries, animate],
};

export default config;
