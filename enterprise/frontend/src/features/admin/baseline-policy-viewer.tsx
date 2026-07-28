"use client";

import { toast } from "sonner";
import { useBaselinePolicy } from "@/data/hooks";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";

export function BaselinePolicyViewer() {
  const { data, isLoading } = useBaselinePolicy();
  const json = data ? JSON.stringify(data, null, 2) : "";

  async function copy() {
    await navigator.clipboard.writeText(json);
    toast.success("Baseline policy copied");
  }

  return (
    <Card className="flex h-96 flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-outline-variant bg-surface-container-lowest p-4">
        <h3 className="flex items-center gap-2 text-body-lg font-bold text-primary">
          <Icon name="code" className="text-primary" /> Baseline Policy (Intake Tier)
        </h3>
        <div className="flex gap-2">
          <button
            onClick={copy}
            className="text-on-surface-variant transition-colors hover:text-primary"
            aria-label="Copy"
          >
            <Icon name="content_copy" className="text-[18px]" />
          </button>
          <button
            className="text-on-surface-variant transition-colors hover:text-primary"
            aria-label="Version history"
          >
            <Icon name="history" className="text-[18px]" />
          </button>
        </div>
      </div>
      <div className="scrollbar-thin flex-1 overflow-y-auto bg-inverse-surface p-4">
        {isLoading ? (
          <Skeleton className="h-full w-full bg-white/10" />
        ) : (
          <pre className="font-mono text-label-md leading-relaxed text-surface-dim">
            <code>{json}</code>
          </pre>
        )}
      </div>
    </Card>
  );
}
