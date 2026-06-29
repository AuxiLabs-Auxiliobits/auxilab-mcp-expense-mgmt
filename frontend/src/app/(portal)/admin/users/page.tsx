import type { Metadata } from "next";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { UserManagement } from "@/features/admin/user-management";

export const metadata: Metadata = { title: "User Management" };

export default function AdminUsersPage() {
  return (
    <PageContainer>
      <PageHeader
        title="User Management"
        description="Manage employees, managers, and finance reviewers within each agency."
      />
      <div className="mt-4">
        <UserManagement view="agency" />
      </div>
    </PageContainer>
  );
}
