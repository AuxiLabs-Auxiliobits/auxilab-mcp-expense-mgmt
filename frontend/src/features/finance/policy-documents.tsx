"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useCurrentUser, useDeletePolicy, usePolicyDocuments, usePolicyIngestLog, usePublishPolicy } from "@/data/hooks";
import { PolicyViewer } from "@/components/shared/policy-viewer";
import { PolicyUploadDialog } from "./policy-upload-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AgencyPolicyDocument, PolicyIngestEvent } from "@/data/types";

const STATUS_CLASS: Record<string, string> = {
  active: "bg-success-green/10 text-success-green border border-success-green/20",
  draft: "bg-yellow-500/10 text-yellow-600 border border-yellow-500/20",
  archived: "bg-surface-container-highest text-on-surface-variant border border-outline-variant",
};

// The 3 audit actions that map to visible pipeline steps
const PIPELINE = [
  { action: "POLICY_UPLOADED", label: "Document uploaded & stored", icon: "upload_file" },
  { action: "POLICY_PUBLISHED", label: "Published — queued for RAG ingestion", icon: "publish" },
  { action: "POLICY_INDEXED", label: "Indexed into Azure AI Search", icon: "travel_explore" },
] as const;

function PipelineLog({
  agencyId,
  policyId,
  isIndexing,
  docStatus,
}: {
  agencyId: string;
  policyId: string;
  isIndexing: boolean;
  docStatus: string;
}) {
  const { data: events, isLoading } = usePolicyIngestLog(agencyId, policyId);

  const doneSet = new Set((events ?? []).map((e: PolicyIngestEvent) => e.action));
  const failedEvent = (events ?? []).find((e: PolicyIngestEvent) => e.action === "POLICY_INDEX_FAILED");
  const indexedEvent = (events ?? []).find((e: PolicyIngestEvent) => e.action === "POLICY_INDEXED");

  const showSkeleton = isLoading && !isIndexing && docStatus !== "draft";

  return (
    <div className="mt-3 rounded-md border border-outline-variant/60 bg-surface-container-lowest p-3">
      <div className="mb-2.5 flex items-center gap-1.5">
        <Icon name="account_tree" className="text-[15px] text-on-surface-variant" />
        <p className="font-mono text-label-sm font-semibold uppercase tracking-wide text-on-surface-variant">
          RAG Ingestion Pipeline
        </p>
      </div>

      {showSkeleton ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-6 rounded" />
          ))}
        </div>
      ) : (
        <ol className="space-y-2.5">
          {PIPELINE.map((step, idx) => {
            const isDone = doneSet.has(step.action);
            const isFailed = step.action === "POLICY_INDEXED" && !!failedEvent && !isDone;
            // Animate the step that's currently happening during the publish API call
            const isSpinning =
              isIndexing &&
              !isDone &&
              PIPELINE.slice(0, idx).every((s) => doneSet.has(s.action));

            const chunks =
              step.action === "POLICY_INDEXED" && indexedEvent?.after?.chunks != null
                ? Number(indexedEvent.after.chunks)
                : null;

            return (
              <li key={step.action} className="flex items-start gap-2.5">
                <div className="flex flex-col items-center pt-0.5">
                  {isDone ? (
                    <Icon name="check_circle" className="text-[18px] text-success-green" />
                  ) : isFailed ? (
                    <Icon name="cancel" className="text-[18px] text-error" />
                  ) : isSpinning ? (
                    <Icon
                      name="progress_activity"
                      className="animate-spin text-[18px] text-secondary"
                    />
                  ) : (
                    <Icon
                      name="radio_button_unchecked"
                      className="text-[18px] text-outline-variant"
                    />
                  )}
                  {idx < PIPELINE.length - 1 && (
                    <div
                      className={cn(
                        "mt-1 w-px flex-1",
                        isDone ? "bg-success-green/40" : "bg-outline-variant/50",
                      )}
                      style={{ minHeight: 10 }}
                    />
                  )}
                </div>

                <div className="min-w-0 flex-1 pb-1">
                  <p
                    className={cn(
                      "text-body-sm",
                      isDone
                        ? "font-medium text-on-surface"
                        : isFailed
                          ? "font-medium text-error"
                          : isSpinning
                            ? "text-on-surface"
                            : "text-on-surface-variant",
                    )}
                  >
                    {step.label}
                    {chunks != null && (
                      <span className="ml-2 font-mono text-label-sm text-success-green">
                        {chunks} chunks
                      </span>
                    )}
                  </p>
                  {isFailed && failedEvent?.after?.detail != null && (
                    <p className="mt-0.5 font-mono text-label-sm text-error">
                      {String(failedEvent.after.detail).slice(0, 160)}
                    </p>
                  )}
                  {isDone && (
                    <p className="font-mono text-label-sm text-on-surface-variant">
                      {formatRelative(
                        (events ?? []).find((e: PolicyIngestEvent) => e.action === step.action)
                          ?.timestamp ?? "",
                      )}
                    </p>
                  )}
                </div>
              </li>
            );
          })}

          {isIndexing && (
            <li className="flex items-center gap-2.5 pt-1">
              <Icon name="progress_activity" className="animate-spin text-[18px] text-secondary" />
              <p className="text-body-sm text-secondary">
                Running ingestion pipeline… extracting → chunking → embedding → indexing
              </p>
            </li>
          )}
        </ol>
      )}

      {failedEvent && !isIndexing && (
        <div className="mt-2 flex items-center gap-1.5 rounded border border-error/20 bg-error-container px-2 py-1">
          <Icon name="error" className="shrink-0 text-[14px] text-error" />
          <p className="text-label-sm text-error">Indexing failed — upload a new version and try again.</p>
        </div>
      )}
    </div>
  );
}

function PolicyRow({
  doc,
  onPublish,
  publishingId,
  onDelete,
  deletingId,
}: {
  doc: AgencyPolicyDocument;
  onPublish: (id: string) => void;
  publishingId: string | null;
  onDelete: (id: string) => void;
  deletingId: string | null;
}) {
  const isThisPublishing = publishingId === doc.id;
  const isThisDeleting = deletingId === doc.id;
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <>
      {/* Delete confirmation dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete policy version?</DialogTitle>
          </DialogHeader>
          <p className="text-body-sm text-on-surface-variant">
            <span className="font-semibold text-on-surface">{doc.name} {doc.version}</span> will be
            permanently deleted
            {doc.status === "active" ? " and all its chunks will be removed from Azure AI Search." : "."}
            {" "}This cannot be undone.
          </p>
          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              loading={isThisDeleting}
              onClick={() => {
                setConfirmOpen(false);
                onDelete(doc.id);
              }}
            >
              <Icon name="delete" className="text-[16px]" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="rounded-lg border border-outline-variant bg-surface-container-low p-3">
      {/* Header row */}
      <div className="flex items-center gap-3">
        <Icon name="description" className="shrink-0 text-[20px] text-secondary" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-body-md font-semibold text-on-surface">{doc.name}</p>
          <p className="font-mono text-label-sm text-on-surface-variant">
            {doc.version}
            {doc.indexedAt ? ` · Indexed ${formatRelative(doc.indexedAt)}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <PolicyViewer
            doc={doc}
            trigger={
              <button
                className="rounded p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container hover:text-primary"
                aria-label={`Preview ${doc.name}`}
                title="Preview document"
              >
                <Icon name="visibility" className="text-[18px]" />
              </button>
            }
          />
          {doc.status === "draft" && (
            <Button
              size="sm"
              loading={isThisPublishing}
              disabled={!!publishingId && !isThisPublishing || isThisDeleting}
              onClick={() => onPublish(doc.id)}
            >
              <Icon name="publish" className="text-[16px]" />
              Publish & Index
            </Button>
          )}
          <span
            className={cn(
              "rounded px-2 py-0.5 text-label-md font-medium capitalize",
              STATUS_CLASS[doc.status] ?? STATUS_CLASS.archived,
            )}
          >
            {doc.status === "active" ? "indexed" : doc.status}
          </span>
          <button
            className="rounded p-1.5 text-on-surface-variant transition-colors hover:bg-error/10 hover:text-error disabled:opacity-40"
            aria-label={`Delete ${doc.name}`}
            title="Delete policy version"
            disabled={isThisDeleting || !!publishingId}
            onClick={() => setConfirmOpen(true)}
          >
            {isThisDeleting
              ? <Icon name="progress_activity" className="animate-spin text-[18px]" />
              : <Icon name="delete" className="text-[18px]" />}
          </button>
        </div>
      </div>

      {/* Pipeline log — always visible, auto-animates during publish */}
      <PipelineLog
        agencyId={doc.agencyId}
        policyId={doc.id}
        isIndexing={isThisPublishing}
        docStatus={doc.status}
      />

    </div>
    </>
  );
}

export function PolicyDocuments() {
  const { data: user } = useCurrentUser("finance");
  const { data, isLoading } = usePolicyDocuments();
  const publish = usePublishPolicy();
  const deletePolicy = useDeletePolicy();
  const qc = useQueryClient();
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function onPublish(id: string) {
    setPublishingId(id);
    try {
      const doc = await publish.mutateAsync({ id, publishedBy: user?.id ?? "" });
      toast.success(`${doc.name} ${doc.version} published`, {
        description: "RAG ingestion complete — policy is now live.",
      });
    } catch {
      // Global error toast is already handled by the shared query client.
    } finally {
      setPublishingId(null);
      qc.invalidateQueries({ queryKey: ["policy-ingest-log"] });
    }
  }

  async function onDelete(id: string) {
    const doc = (data ?? []).find((d) => d.id === id);
    setDeletingId(id);
    try {
      await deletePolicy.mutateAsync({ id });
      toast.success(`${doc?.name ?? "Policy"} ${doc?.version ?? ""} deleted`, {
        description: doc?.status === "active"
          ? "Policy and its Azure AI Search chunks have been removed."
          : "Policy draft deleted.",
      });
    } catch {
      // Global error toast is already handled by the shared query client.
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <Card className="flex flex-col rounded-xl p-6">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-headline-md font-bold text-on-surface">Policy Documents</h3>
        <PolicyUploadDialog
          trigger={
            <Button size="sm" variant="outline">
              <Icon name="upload_file" className="text-[16px]" /> Upload new
            </Button>
          }
        />
      </div>
      <p className="mb-4 text-body-sm text-on-surface-variant">
        Upload a policy doc, then click{" "}
        <span className="font-medium text-on-surface">Publish &amp; Index</span> to run the RAG
        pipeline. The pipeline log shows each step in real time.
      </p>

      <div className="flex flex-1 flex-col gap-3">
        {isLoading ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-lg" />)
        ) : (data ?? []).length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-outline-variant py-10 text-center">
            <Icon name="policy" className="text-[40px] text-outline-variant" />
            <div>
              <p className="text-body-md font-medium text-on-surface">No policy documents yet</p>
              <p className="mt-0.5 text-body-sm text-on-surface-variant">
                Upload a .pdf or .docx policy file to get started.
              </p>
            </div>
          </div>
        ) : (
          (data ?? []).map((doc) => (
            <PolicyRow
              key={doc.id}
              doc={doc}
              onPublish={onPublish}
              publishingId={publishingId}
              onDelete={onDelete}
              deletingId={deletingId}
            />
          ))
        )}
      </div>
    </Card>
  );
}
