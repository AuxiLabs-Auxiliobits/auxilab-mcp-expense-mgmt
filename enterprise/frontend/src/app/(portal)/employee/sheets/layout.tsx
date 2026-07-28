import type { Metadata } from "next";

// Re-declare the template so /employee/sheets/new and /sheets/[id] keep the suffix.
export const metadata: Metadata = {
  title: { default: "My Expense Sheets", template: "%s — Auxilab EM" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
