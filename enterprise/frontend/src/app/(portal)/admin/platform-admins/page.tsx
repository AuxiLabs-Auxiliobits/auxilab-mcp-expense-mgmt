import type { Metadata } from "next";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { UserManagement } from "@/features/admin/user-management";

export const metadata: Metadata = { title: "Platform Admins" };

export default function AdminPlatformAdminsPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Platform Admins"
        description="Manage platform administrators who have org-wide access."
      />
      <div className="mt-4">
        <UserManagement view="admins" />
      </div>
    </PageContainer>
  );
}
