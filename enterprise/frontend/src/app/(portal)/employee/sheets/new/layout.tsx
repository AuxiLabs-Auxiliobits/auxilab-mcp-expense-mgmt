import type { Metadata } from "next";

export const metadata: Metadata = { title: "Create Expense Sheet" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
