import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthCardShell } from "@/features/auth/auth-card-shell";
import { ResetPasswordCard } from "@/features/auth/reset-password-card";

export const metadata: Metadata = { title: "Reset Password" };

export default function ResetPasswordPage() {
  return (
    <AuthCardShell>
      <Suspense fallback={null}>
        <ResetPasswordCard />
      </Suspense>
    </AuthCardShell>
  );
}
