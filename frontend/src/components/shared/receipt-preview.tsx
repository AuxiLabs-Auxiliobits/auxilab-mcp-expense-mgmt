"use client";

import { useEffect, useState } from "react";
import { apiBlob } from "@/data/http";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

function isImage(fileType: string, fileName: string): boolean {
  return fileType.startsWith("image/") || /\.(png|jpe?g|heic|gif|webp|bmp)$/i.test(fileName);
}

/**
 * Receipt thumbnail / viewer. Works for a not-yet-uploaded `file` (local object URL) or a
 * stored attachment via `downloadUrl` (fetched with the bearer token — a plain <a> can't
 * send auth). Images render a thumbnail; anything else shows a "View" button. Click opens
 * the full file in a new tab.
 */
export function ReceiptPreview({
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
  const [thumb, setThumb] = useState<string | null>(null);
  const image = isImage(fileType, fileName);

  useEffect(() => {
    let active = true;
    let created: string | null = null;
    if (file) {
      created = URL.createObjectURL(file);
      if (active) setThumb(created);
    } else if (downloadUrl && image) {
      apiBlob(downloadUrl)
        .then((b) => {
          if (!active) return;
          created = URL.createObjectURL(b);
          setThumb(created);
        })
        .catch(() => {});
    }
    return () => {
      active = false;
      if (created) URL.revokeObjectURL(created);
    };
  }, [file, downloadUrl, image]);

  async function openFull() {
    try {
      let url = file ? URL.createObjectURL(file) : null;
      if (!url && downloadUrl) url = URL.createObjectURL(await apiBlob(downloadUrl));
      if (url) window.open(url, "_blank", "noopener");
    } catch {
      /* best-effort */
    }
  }

  if (image && thumb) {
    return (
      <button
        type="button"
        onClick={openFull}
        title={`Open ${fileName}`}
        className={cn(
          "block overflow-hidden rounded border border-outline-variant transition-opacity hover:opacity-80",
          className,
        )}
      >
        <img src={thumb} alt={fileName} className="h-12 w-12 object-cover" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={openFull}
      title={`Open ${fileName}`}
      className={cn(
        "inline-flex items-center gap-1 rounded border border-outline-variant px-2 py-1 text-label-md text-on-surface-variant transition-colors hover:border-secondary hover:text-primary",
        className,
      )}
    >
      <Icon name={image ? "image" : "visibility"} className="text-[16px]" /> View
    </button>
  );
}
