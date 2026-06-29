"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Markdown } from "@/components/shared/markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { Icon } from "@/components/ui/icon";
import { usePolicyDocumentContent } from "@/data/hooks";
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
  const [open, setOpen] = useState(false);
  // Fetch the real extracted text of the indexed doc (only when the dialog opens).
  const { data: liveContent, isLoading } = usePolicyDocumentContent(doc.id, open);
  // Binary files (DOCX/PDF without Doc Intelligence) are decoded as raw bytes → the
  // content starts with "PK" (ZIP magic). Detect and suppress rather than show garbage.
  const isBinary = typeof liveContent === "string" && liveContent.startsWith("PK");
  // Prefer the real RAG-indexed source; fall back to the bundled sample for seeded demos.
  const content = (liveContent && !isBinary && liveContent.trim()) || getPolicyContent(doc.id);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon name="description" className="text-secondary" />
            {doc.name}
          </DialogTitle>
          <DialogDescription className="font-mono">
            {doc.version}{doc.effectiveDate ? ` · Effective ${formatDate(doc.effectiveDate)}` : ""} ·{" "}
            <span className="capitalize">{doc.status}</span>
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-2 rounded-lg border border-outline-variant bg-surface-container-low p-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-4" />
            ))}
          </div>
        ) : isBinary ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-yellow-500/30 bg-yellow-500/8 p-6 text-center">
            <Icon name="warning" className="text-[32px] text-yellow-600" />
            <div>
              <p className="font-medium text-on-surface">Preview unavailable for binary files</p>
              <p className="mt-1 text-body-sm text-on-surface-variant">
                This is a <strong>.docx</strong> or <strong>.pdf</strong> file. Text extraction
                requires Azure Document Intelligence to be configured. For instant previews,
                upload your policy as a <strong>.md</strong> or <strong>.txt</strong> file instead.
              </p>
              <p className="mt-2 font-mono text-label-sm text-on-surface-variant">
                The file is stored and will index correctly once Doc Intelligence is wired up.
              </p>
            </div>
          </div>
        ) : content ? (
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
