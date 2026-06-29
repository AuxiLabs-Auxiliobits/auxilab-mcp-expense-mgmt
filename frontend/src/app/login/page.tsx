import type { Metadata } from "next";
import { LoginExperience } from "@/features/auth/login-experience";

// Reason-aware title: a session-expiry redirect (?reason=expired) reads "Session Expired".
export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>;
}): Promise<Metadata> {
  const { reason } = await searchParams;
  return { title: reason === "expired" ? "Session Expired" : "Sign In" };
}

export default function LoginPage() {
  return <LoginExperience />;
}
