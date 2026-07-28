import type { Metadata } from "next";
import { AuthCardShell } from "@/features/auth/auth-card-shell";
import { ForgotPasswordCard } from "@/features/auth/forgot-password-card";

export const metadata: Metadata = { title: "Forgot Password" };

export default function ForgotPasswordPage() {
  return (
    <AuthCardShell>
      <ForgotPasswordCard />
    </AuthCardShell>
  );
}
