"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useCurrentUser, useEmployeeSheets } from "@/data/hooks";
import { useReceiptUploads } from "@/data/receipt-uploads";
import { apiBlob } from "@/data/http";
import { fileIssue } from "@/lib/intake";
import { baselinePolicy } from "@/data/mock";
import { ReceiptPreview } from "@/components/shared/receipt-preview";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";

type ReceiptRow = {
  id: string;
  fileName: string;
  merchant: string;
  sheetId: string;
  scanStatus: string;
  fileType: string;
  downloadUrl?: string; // stored attachment (fetched with auth)
  file?: File; // not-yet-attached local upload
  uploadId?: string; // store id for an unassigned upload (deletable)
};

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-outline-variant py-2.5 last:border-0">
      <dt className="font-mono text-label-md uppercase tracking-wider text-on-surface-variant">{label}</dt>
      <dd className="min-w-0 text-right text-body-sm text-on-surface">{children}</dd>
    </div>
  );
}

export default function EmployeeReceiptsPage() {
  const { data: user } = useCurrentUser("employee");
  const { data: sheets } = useEmployeeSheets(user?.id ?? "");
  const { uploads, addUploads, removeUpload } = useReceiptUploads();
  const fileRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<ReceiptRow | null>(null);

  const uploaded: ReceiptRow[] = uploads.map((u) => ({
    id: u.id,
    fileName: u.fileName,
    merchant: "Manual upload",
    sheetId: "Unassigned",
    scanStatus: "clean",
    fileType: u.fileType,
    file: u.file,
    uploadId: u.id,
  }));

  const attached: ReceiptRow[] = (sheets ?? []).flatMap((s) =>
    s.lineItems.flatMap((li) =>
      li.attachments.map((a) => ({
        id: a.id,
        fileName: a.fileName,
        merchant: li.merchant,
        sheetId: s.id,
        scanStatus: a.scanStatus,
        fileType: a.fileType,
        downloadUrl: a.downloadUrl,
      })),
    ),
  );

  const receipts = [...uploaded, ...attached];

  function onFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (!picked.length) return;
    const valid: File[] = [];
    for (const f of picked) {
      const issue = fileIssue(f, baselinePolicy);
      if (issue) {
        toast.error(`${f.name}: ${issue}`);
        continue;
      }
      valid.push(f);
    }
    if (!valid.length) return;
    addUploads(valid);
    toast.success(`${valid.length} receipt${valid.length === 1 ? "" : "s"} added`, {
      description: "Preview/download here; pick it when you add a line item to a sheet.",
    });
  }

  function deleteUpload(r: ReceiptRow) {
    if (!r.uploadId) return;
    removeUpload(r.uploadId);
    setSelected((cur) => (cur?.id === r.id ? null : cur));
    toast("Receipt removed", { description: r.fileName });
  }

  async function downloadReceipt(r: ReceiptRow) {
    try {
      const blob = r.file ?? (r.downloadUrl ? await apiBlob(r.downloadUrl) : null);
      if (!blob) {
        toast.error("Nothing to download for this receipt");
        return;
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = r.fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Download started");
    } catch {
      toast.error("Download failed");
    }
  }

  return (
    <PageContainer>
      <PageHeader title="My Receipts" description="All receipts attached to your line items." tone="primary">
        <input
          ref={fileRef}
          type="file"
          accept="image/*,application/pdf"
          multiple
          hidden
          onChange={onFiles}
        />
        <Button variant="outline" onClick={() => fileRef.current?.click()}>
          <Icon name="upload_file" /> Upload Receipt
        </Button>
      </PageHeader>

      {receipts.length === 0 ? (
        <Card className="mt-6">
          <EmptyState icon="receipt_long" title="No receipts yet" description="Upload receipts when you add line items." />
        </Card>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {receipts.map((r) => (
            <Card
              key={r.id}
              interactive
              role="button"
              tabIndex={0}
              onClick={() => setSelected(r)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelected(r);
                }
              }}
              className="flex items-center gap-3 p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
            >
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-surface-container-high text-on-surface-variant">
                <Icon name="receipt_long" className="text-[20px]" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-body-sm font-medium text-on-surface">{r.fileName}</div>
                <div className="truncate font-mono text-label-sm text-on-surface-variant">
                  {r.merchant} · {r.sheetId}
                </div>
              </div>
              <Badge className="bg-success-green/10 capitalize text-success-green" pill={false}>
                <Icon name="verified" className="text-[12px]" /> {r.scanStatus}
              </Badge>
              {r.uploadId && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteUpload(r);
                  }}
                  aria-label={`Delete ${r.fileName}`}
                  className="rounded p-1.5 text-on-surface-variant transition-colors hover:bg-error-container hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error"
                >
                  <Icon name="delete" className="text-[18px]" />
                </button>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Receipt preview drawer */}
      <Drawer open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DrawerContent>
          {selected && (
            <>
              <DrawerHeader>
                <DrawerTitle className="truncate">{selected.fileName}</DrawerTitle>
                <DrawerDescription>{selected.merchant}</DrawerDescription>
              </DrawerHeader>
              <DrawerBody className="space-y-5">
                <div className="flex aspect-[4/3] items-center justify-center overflow-hidden rounded-lg border border-outline-variant bg-surface-container-low">
                  <ReceiptPreview
                    variant="full"
                    file={selected.file}
                    downloadUrl={selected.downloadUrl}
                    fileName={selected.fileName}
                    fileType={selected.fileType}
                  />
                </div>
                <dl>
                  <MetaRow label="File">
                    <span className="font-mono">{selected.fileName}</span>
                  </MetaRow>
                  <MetaRow label="Merchant">{selected.merchant}</MetaRow>
                  <MetaRow label="Sheet">
                    <span className="font-mono">{selected.sheetId}</span>
                  </MetaRow>
                  <MetaRow label="Virus scan">
                    <Badge className="bg-success-green/10 capitalize text-success-green" pill={false}>
                      <Icon name="verified" className="text-[12px]" /> {selected.scanStatus}
                    </Badge>
                  </MetaRow>
                  <MetaRow label="OCR">
                    <Badge className="bg-success-green/10 text-success-green" pill={false}>
                      <Icon name="check" className="text-[12px]" /> Done
                    </Badge>
                  </MetaRow>
                </dl>
              </DrawerBody>
              <DrawerFooter>
                {selected.uploadId && (
                  <Button
                    variant="outline"
                    onClick={() => deleteUpload(selected)}
                    className="text-error hover:text-error"
                  >
                    <Icon name="delete" /> Delete
                  </Button>
                )}
                {selected.sheetId !== "Unassigned" && (
                  <Button variant="outline" asChild>
                    <Link href={`/employee/sheets/${selected.sheetId}`}>
                      <Icon name="open_in_new" /> Open sheet
                    </Link>
                  </Button>
                )}
                <Button onClick={() => downloadReceipt(selected)}>
                  <Icon name="download" /> Download
                </Button>
              </DrawerFooter>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </PageContainer>
  );
}
