/**
 * Auxilab brand mark — a bold geometric "A" monogram.
 *
 * Two solid legs + a crossbar give the structured, governed feel of a capital A;
 * the detached node above the apex signals the AI / automation layer. The form is
 * filled (not thin strokes) so it stays confident and legible at favicon size, in
 * the spirit of Linear / Vercel / Atlassian app icons. No banks, buildings, or
 * finance clichés.
 *
 * Two exports:
 *  - <LogoMark/>  the A glyph alone, in `currentColor` — for watermarks, monochrome
 *                 contexts, or anywhere the container supplies its own color.
 *  - <LogoTile/>  the self-contained brand icon: a brand-blue squircle with the A
 *                 knocked out in white. This is the primary lockup and matches the
 *                 favicon exactly. Works as-is in light and dark mode.
 */

const BRAND_BLUE = "#2563EB";

/** Shared geometry, authored in a 24×24 grid. */
function AGlyph({ fill }: { fill: string }) {
  return (
    <g fill={fill}>
      {/* left leg */}
      <path d="M2.8 21 H6.6 L12 7.5 H10.4 Z" />
      {/* right leg */}
      <path d="M21.2 21 H17.4 L12 7.5 H13.6 Z" />
      {/* crossbar — governance */}
      <path d="M8 13.8 H16 V16.2 H8 Z" />
      {/* detached node — automation / intelligence */}
      <circle cx="12" cy="3.7" r="2" />
    </g>
  );
}

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      role="img"
      aria-label="Auxilab"
      focusable="false"
    >
      <AGlyph fill="currentColor" />
    </svg>
  );
}

export function LogoTile({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      role="img"
      aria-label="Auxilab"
      focusable="false"
    >
      <rect width="32" height="32" rx="8" fill={BRAND_BLUE} />
      <g transform="translate(4 4.2)">
        <AGlyph fill="#ffffff" />
      </g>
    </svg>
  );
}
