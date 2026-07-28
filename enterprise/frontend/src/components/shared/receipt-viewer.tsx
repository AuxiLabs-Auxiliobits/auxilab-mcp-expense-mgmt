"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { fetchReceiptBlob } from "@/data/api";
import type { Attachment } from "@/data/types";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/loaders";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatRelative } from "@/lib/format";

function sizeLabel(bytes: number): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function iconFor(type: string): string {
  if (type.startsWith("image/")) return "image";
  if (type.includes("pdf")) return "picture_as_pdf";
  return "description";
}

/**
 * Lists receipt attachments with inline **preview** and **download**, both authenticated
 * (the API requires a bearer token, so we fetch bytes → object URL rather than a raw <img src>).
 * Every action shows a loader and surfaces failures as a toast.
 */
export function ReceiptViewer({
  attachments,
  emptyHint = "No receipts attached.",
}: {
  attachments: Attachment[];
  emptyHint?: string;
}) {
  const [busyId, setBusyId] = useState<string | null>(null); // attachment id currently fetching
  const [preview, setPreview] = useState<{ url: string; type: string; name: string } | null>(null);

  // Revoke the object URL when the preview closes/unmounts to avoid memory leaks.
  useEffect(() => {
    return () => {
      if (preview?.url) URL.revokeObjectURL(preview.url);
    };
  }, [preview?.url]);

  async function onPreview(a: Attachment) {
    setBusyId(a.id);
    try {
      const { blob, filename, contentType } = await fetchReceiptBlob(a.id);
      setPreview({ url: URL.createObjectURL(blob), type: contentType, name: filename });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Couldn't load the receipt");
    } finally {
      setBusyId(null);
    }
  }

  async function onDownload(a: Attachment) {
    setBusyId(a.id + ":dl");
    try {
      const { blob, filename } = await fetchReceiptBlob(a.id, true);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename || a.fileName || "receipt";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Couldn't download the receipt");
    } finally {
      setBusyId(null);
    }
  }

  function closePreview() {
    if (preview?.url) URL.revokeObjectURL(preview.url);
    setPreview(null);
  }

  if (!attachments.length) {
    return <p className="text-body-sm text-on-surface-variant">{emptyHint}</p>;
  }

  return (
    <>
      <ul className="space-y-2">
        {attachments.map((a) => (
          <li
            key={a.id}
            className="flex items-center gap-3 rounded-md border border-outline-variant bg-surface-container-lowest px-3 py-2"
          >
            <Icon name={iconFor(a.fileType)} className="shrink-0 text-[20px] text-secondary" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-body-sm font-medium text-on-surface">{a.fileName}</div>
              <div className="font-mono text-label-sm text-on-surface-variant">
                {[sizeLabel(a.sizeBytes), a.uploadedAt ? `Uploaded ${formatRelative(a.uploadedAt)}` : null]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              loading={busyId === a.id}
              onClick={() => onPreview(a)}
            >
              <Icon name="visibility" /> Preview
            </Button>
            <Button
              variant="ghost"
              size="sm"
              loading={busyId === a.id + ":dl"}
              onClick={() => onDownload(a)}
              aria-label={`Download ${a.fileName}`}
            >
              <Icon name="download" /> Download
            </Button>
          </li>
        ))}
      </ul>

      <Dialog open={!!preview} onOpenChange={(o) => !o && closePreview()}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle className="truncate">{preview?.name}</DialogTitle>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-auto rounded-md border border-outline-variant bg-surface-container-low">
            {preview?.type.startsWith("image/") ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview.url} alt={preview.name} className="mx-auto max-h-[68vh]" />
            ) : preview?.type.includes("pdf") ? (
              <iframe src={preview.url} title={preview.name} className="h-[68vh] w-full" />
            ) : (
              <div className="flex flex-col items-center gap-3 p-10 text-center text-on-surface-variant">
                <Icon name="description" className="text-[40px]" />
                <p className="text-body-sm">
                  This file type can&apos;t be previewed inline. Use Download to open it.
                </p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Tiny inline loading state for the receipts section. */
export function ReceiptsLoading() {
  return (
    <div className="flex items-center gap-2 py-2 text-body-sm text-on-surface-variant">
      <Spinner /> Loading receipts…
    </div>
  );
}
