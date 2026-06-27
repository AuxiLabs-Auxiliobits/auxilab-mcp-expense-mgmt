import type { Metadata } from "next";
import { AdminSettings } from "@/features/admin/settings";

export const metadata: Metadata = { title: "Admin Dashboard" };

export default function AdminPage() {
  return <AdminSettings />;
}
