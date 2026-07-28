"use client";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Reveal } from "@/components/shared/reveal";
import { AgencyManagement } from "./agency-management";
import { UserManagement } from "./user-management";

export function AdminSettings() {
  return (
    <PageContainer>
      <PageHeader
        title="Administration"
        description="Onboard and manage users and agencies across the platform."
        tone="primary"
        size="xl"
      />

      <Reveal delay={80} className="mt-6 space-y-6">
        <UserManagement />
        <AgencyManagement />
      </Reveal>
    </PageContainer>
  );
}
