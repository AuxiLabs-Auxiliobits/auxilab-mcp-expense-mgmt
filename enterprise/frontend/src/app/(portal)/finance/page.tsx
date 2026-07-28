import type { Metadata } from "next";
import { FinanceConsole } from "@/features/finance/console";

export const metadata: Metadata = { title: "Finance Dashboard" };

export default function FinancePage() {
  return <FinanceConsole />;
}
