"use client";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { PolicyDocuments } from "./policy-documents";

export function PolicyPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Policy Documents"
        description="Upload, publish, and manage agency policy documents. Indexed documents are used by the AI Approver for RAG-based compliance checks."
        size="xl"
      />

      <div className="mt-6">
        <PolicyDocuments />
      </div>

      <div className="mt-8">
        {/* <h2 className="mb-1 text-headline-md font-semibold text-on-surface">Policy Activity</h2> */}
        {/* <p className="mb-1 text-body-sm text-on-surface-variant">
          Audit trail of all policy-related actions — uploads, publishes, and index events.
        </p> */}
        {/* <ActivityTable /> */}
      </div>
    </PageContainer>
  );
}
