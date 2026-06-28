import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "highlight.js/styles/github-dark.css";
import { Providers } from "@/components/providers";

// Inter variable — the single typeface for the entire app (100–900 from one file).
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  // Every page resolves to "<Page> — Auxilab EM" via the template; pages without their own
  // title fall back to the brand default.
  title: {
    default: "Auxilab EM",
    template: "%s — Auxilab EM",
  },
  description:
    "Enterprise expense compliance platform — multi-role portal with an LLM Finance Approver, agency-scoped policy RAG, and full audit trail.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={inter.variable}
      // next-themes writes the theme class/style onto <html> on the client before hydration
      // (to avoid a flash of the wrong theme), so the server markup can't match. This is the
      // documented, intended use of suppressHydrationWarning — scoped to the <html> tag only.
      suppressHydrationWarning
    >
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans text-on-surface antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
