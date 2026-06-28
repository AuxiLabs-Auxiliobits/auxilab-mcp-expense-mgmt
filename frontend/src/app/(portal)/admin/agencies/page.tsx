import type { Metadata } from "next";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { AgencyManagement } from "@/features/admin/agency-management";

export const metadata: Metadata = { title: "Agency Management" };

export default function AdminAgenciesPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Agency Management"
        description="Create and manage agencies, set status and configure org structure."
      />
      <div className="mt-4">
        <AgencyManagement />
      </div>
    </PageContainer>
  );
}
