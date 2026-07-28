import type { Metadata } from "next";

// `template` re-declares the suffix for this subtree so nested employee routes
// (sheets, receipts, …) keep the " — Auxilab EM" convention; `default` titles /employee.
export const metadata: Metadata = {
  title: { default: "Employee Dashboard", template: "%s — Auxilab EM" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
