"use client";

import { useEffect, useState } from "react";
import { apiBlob } from "@/data/http";
import { Icon } from "@/components/ui/icon";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

function isImage(fileType: string, fileName: string): boolean {
  return fileType.startsWith("image/") || /\.(png|jpe?g|heic|gif|webp|bmp)$/i.test(fileName);
}
function isPdf(fileType: string, fileName: string): boolean {
  return fileType.includes("pdf") || /\.pdf$/i.test(fileName);
}

/** Large inline render: fetches the bytes (auth) and shows the image / embeds the PDF. */
function FullPreview({
  file,
  downloadUrl,
  fileName,
  fileType,
  className,
}: {
  file?: File;
  downloadUrl?: string;
  fileName: string;
  fileType: string;
  className?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const image = isImage(fileType, fileName);
  const pdf = isPdf(fileType, fileName);

  useEffect(() => {
    let active = true;
    let created: string | null = null;
    setUrl(null);
    setFailed(false);
    if (file) {
      created = URL.createObjectURL(file);
      if (active) setUrl(created);
    } else if (downloadUrl) {
      apiBlob(downloadUrl)
        .then((b) => {
          if (!active) return;
          created = URL.createObjectURL(b.blob);
          setUrl(created);
        })
        .catch(() => active && setFailed(true));
    }
    return () => {
      active = false;
      if (created) URL.revokeObjectURL(created);
    };
  }, [file, downloadUrl]);

  const box = cn("flex h-full w-full items-center justify-center text-on-surface-variant", className);
  if (!file && !downloadUrl)
    return (
      <div className={box}>
        <div className="text-center">
          <Icon name="image" className="text-[40px]" />
          <p className="mt-2 text-body-sm">No preview available</p>
        </div>
      </div>
    );
  if (failed)
    return (
      <div className={box}>
        <div className="text-center">
          <Icon name="broken_image" className="text-[40px]" />
          <p className="mt-2 text-body-sm">Couldn&apos;t load preview</p>
        </div>
      </div>
    );
  if (!url)
    return (
      <div className={box}>
        <Icon name="progress_activity" className="animate-spin text-[28px]" />
      </div>
    );
  if (image) return <img src={url} alt={fileName} className={cn("max-h-full max-w-full object-contain", className)} />;
  if (pdf) return <iframe src={url} title={fileName} className={cn("h-full w-full", className)} />;
  return (
    <a href={url} download={fileName} className="inline-flex items-center gap-1.5 text-body-sm text-primary hover:underline">
      <Icon name="download" className="text-[18px]" /> Download {fileName}
    </a>
  );
}

/**
 * Receipt thumbnail + in-app preview. Works for a not-yet-uploaded `file` (local object URL)
 * or a stored attachment via `downloadUrl` (fetched with the bearer token).
 *
 * - `variant="thumb"` (default): small thumbnail / "View" chip; clicking opens a **modal**
 *   with the full preview (image or embedded PDF) — no new browser tab.
 * - `variant="full"`: renders the large preview inline (e.g. inside a drawer).
 */
export function ReceiptPreview({
  file,
  downloadUrl,
  fileName,
  fileType,
  className,
  variant = "thumb",
}: {
  file?: File;
  downloadUrl?: string;
  fileName: string;
  fileType: string;
  className?: string;
  variant?: "thumb" | "full";
}) {
  const [open, setOpen] = useState(false);
  const [thumb, setThumb] = useState<string | null>(null);
  const image = isImage(fileType, fileName);

  // Thumbnail bytes for images only (cheap visual); other types show a "View" chip.
  useEffect(() => {
    if (variant !== "thumb" || !image) return;
    let active = true;
    let created: string | null = null;
    if (file) {
      created = URL.createObjectURL(file);
      if (active) setThumb(created);
    } else if (downloadUrl) {
      apiBlob(downloadUrl)
        .then((b) => {
          if (!active) return;
          created = URL.createObjectURL(b.blob);
          setThumb(created);
        })
        .catch(() => {});
    }
    return () => {
      active = false;
      if (created) URL.revokeObjectURL(created);
    };
  }, [variant, image, file, downloadUrl]);

  if (variant === "full") {
    return <FullPreview file={file} downloadUrl={downloadUrl} fileName={fileName} fileType={fileType} className={className} />;
  }

  return (
    <>
      {image && thumb ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          title={`Preview ${fileName}`}
          className={cn("block overflow-hidden rounded border border-outline-variant transition-opacity hover:opacity-80", className)}
        >
          <img src={thumb} alt={fileName} className="h-12 w-12 object-cover" />
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          title={`Preview ${fileName}`}
          className={cn("inline-flex items-center gap-1 rounded border border-outline-variant px-2 py-1 text-label-md text-on-surface-variant transition-colors hover:border-secondary hover:text-primary", className)}
        >
          <Icon name={image ? "image" : "visibility"} className="text-[16px]" /> View
        </button>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle className="truncate">{fileName}</DialogTitle>
          </DialogHeader>
          <div className="flex h-[70vh] items-center justify-center overflow-hidden rounded-lg border border-outline-variant bg-surface-container-low">
            <FullPreview file={file} downloadUrl={downloadUrl} fileName={fileName} fileType={fileType} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
