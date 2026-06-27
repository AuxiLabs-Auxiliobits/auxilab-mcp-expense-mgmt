import type { Metadata } from "next";
import { PolicyAssistant } from "@/features/assistant/policy-assistant";

export const metadata: Metadata = { title: "Policy Assistant" };

export default function FinanceAssistantPage() {
  return <PolicyAssistant role="finance" />;
}
