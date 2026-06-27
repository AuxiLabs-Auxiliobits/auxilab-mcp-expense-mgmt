import type { Metadata } from "next";

// Static fallback; the page upgrades this to the sheet's name via <PageTitle/> when loaded.
export const metadata: Metadata = { title: "Expense Details" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
