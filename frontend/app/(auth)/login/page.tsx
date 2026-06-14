// REFERENCE SCAFFOLD ONLY — see README.md.
// Login page — kicks off the NextAuth → Entra External ID OIDC flow (SCOPING §10/§13).

import { redirect } from "next/navigation";

export default function LoginPage() {
  // STUB: real implementation triggers the Entra provider, e.g.
  //   "use server";
  //   await signIn("microsoft-entra-id", { redirectTo: "/" });
  async function signInWithEntra() {
    "use server";
    // TODO(reference): call signIn("microsoft-entra-id") from lib/auth.ts.
    redirect("/");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-8">
      <div>
        <h1 className="text-xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Authentication is brokered by Microsoft Entra External ID
          (Google / Microsoft / SSO). Tokens carry role + agency claims.
        </p>
      </div>

      <form action={signInWithEntra}>
        <button
          type="submit"
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Continue with Microsoft Entra
        </button>
      </form>

      <p className="text-xs text-muted-foreground">
        Stubbed: this form does not perform a real sign-in in the reference
        scaffold.
      </p>
    </main>
  );
}
