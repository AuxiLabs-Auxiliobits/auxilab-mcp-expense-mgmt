import type { Metadata } from "next";

export const metadata: Metadata = { title: "Expense Sheets" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
