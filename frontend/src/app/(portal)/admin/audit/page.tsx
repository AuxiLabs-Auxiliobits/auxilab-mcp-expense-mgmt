"use client";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Icon } from "@/components/ui/icon";
import { ActivityTable } from "@/features/shared/activity-table";
import { useCurrentUser } from "@/data/hooks";

export default function AdminAuditPage() {
  const { data: user, isLoading } = useCurrentUser("admin");

  return (
    <PageContainer>
      <PageHeader
        title="My Activity Log"
        description="Actions you have performed on the platform."
      />

      <div className="mt-4 flex items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
        <Icon name="shield_person" className="text-[18px] text-secondary" />
        Showing your actions only — actions taken under your admin account.
      </div>

      {/* Wait for the user ID so ActivityTable always fetches with the actor_id filter. */}
      {!isLoading && <ActivityTable actorId={user?.id} />}
    </PageContainer>
  );
}
