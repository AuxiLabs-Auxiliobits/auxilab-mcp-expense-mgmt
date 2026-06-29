import type { Metadata } from "next";

export const metadata: Metadata = { title: "Policy Documents" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
