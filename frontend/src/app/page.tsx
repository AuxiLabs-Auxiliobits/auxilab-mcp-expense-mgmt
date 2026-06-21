import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { PORTAL_BASE } from "@/lib/rbac";

export default async function Home() {
  const session = await auth();
  if (session?.user?.role) {
    redirect(PORTAL_BASE[session.user.role]);
  }
  redirect("/login");
}
