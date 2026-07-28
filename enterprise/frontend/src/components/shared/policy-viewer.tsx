"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Markdown } from "@/components/shared/markdown";
import { Icon } from "@/components/ui/icon";
import { getPolicyContent } from "@/data/policy-content";
import { formatDate } from "@/lib/format";
import type { AgencyPolicyDocument } from "@/data/types";

export function PolicyViewer({
  doc,
  trigger,
}: {
  doc: AgencyPolicyDocument;
  trigger: React.ReactNode;
}) {
  const content = getPolicyContent(doc.id);

  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon name="description" className="text-secondary" />
            {doc.name}
          </DialogTitle>
          <DialogDescription className="font-mono">
            {doc.version} · Effective {formatDate(doc.effectiveDate)} ·{" "}
            <span className="capitalize">{doc.status}</span>
          </DialogDescription>
        </DialogHeader>

        {content ? (
          <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4">
            <Markdown content={content} />
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 py-10 text-center text-on-surface-variant">
            <Icon name="description" className="text-[28px]" />
            <p className="text-body-sm">
              Document preview isn&apos;t available for this version.
            </p>
          </div>
        )}

        <p className="flex items-center gap-1 font-mono text-label-sm text-on-surface-variant">
          <Icon name="lock" className="text-[14px]" />
          Read-only preview · RAG-indexed source
        </p>
      </DialogContent>
    </Dialog>
  );
}
