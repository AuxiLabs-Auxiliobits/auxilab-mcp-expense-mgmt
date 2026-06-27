"use client";

import { toast } from "sonner";
import { useCurrentUser, usePolicyDocuments, usePublishPolicy } from "@/data/hooks";
import { PolicyViewer } from "@/components/shared/policy-viewer";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUS_CLASS: Record<string, string> = {
  active: "bg-success-green/10 text-success-green border border-success-green/20",
  draft: "bg-yellow-500/10 text-yellow-600 border border-yellow-500/20",
  archived: "bg-surface-container-highest text-on-surface-variant border border-outline-variant",
};

export function PolicyDocuments() {
  const { data: user } = useCurrentUser("finance");
  const { data, isLoading } = usePolicyDocuments();
  const publish = usePublishPolicy();

  async function onPublish(id: string) {
    try {
      // The publisher is the checker; the backend re-derives the actor from the token, and
      // the maker-checker SoD (publisher ≠ uploader) is enforced server-side.
      const doc = await publish.mutateAsync({ id, publishedBy: user?.id ?? "" });
      toast.success(`${doc.name} ${doc.version} published`, { description: "Re-indexed for RAG." });
    } catch {
      /* error toast handled globally (QueryClient mutationCache) */
    }
  }

  return (
    <Card className="flex flex-col rounded-xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-headline-md font-bold text-on-surface">Agency Policy Documents</h3>
      </div>
      <p className="mb-4 text-body-sm text-on-surface-variant">
        RAG-indexed documents governing AI decisions per agency.
      </p>

      <div className="flex flex-1 flex-col gap-3">
        {isLoading
          ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded" />)
          : (data ?? []).map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between gap-2 rounded border border-outline-variant bg-surface-container-low p-3"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <Icon name="description" className="text-secondary" />
                  <div className="min-w-0">
                    <p className="truncate text-body-md font-semibold text-on-surface">{doc.name}</p>
                    <p className="font-mono text-label-sm text-on-surface-variant">
                      {doc.version} • Indexed {formatRelative(doc.indexedAt)}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <PolicyViewer
                    doc={doc}
                    trigger={
                      <button
                        className="rounded p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-lowest hover:text-primary"
                        aria-label={`View ${doc.name}`}
                      >
                        <Icon name="visibility" className="text-[18px]" />
                      </button>
                    }
                  />
                  {doc.status === "draft" && (
                    <Button
                      size="sm"
                      loading={publish.isPending && publish.variables?.id === doc.id}
                      disabled={publish.isPending}
                      onClick={() => onPublish(doc.id)}
                    >
                      Publish
                    </Button>
                  )}
                  <span
                    className={cn(
                      "rounded px-2 py-0.5 text-label-md font-medium capitalize",
                      STATUS_CLASS[doc.status] ?? STATUS_CLASS.archived,
                    )}
                  >
                    {doc.status}
                  </span>
                </div>
              </div>
            ))}
      </div>
    </Card>
  );
}
