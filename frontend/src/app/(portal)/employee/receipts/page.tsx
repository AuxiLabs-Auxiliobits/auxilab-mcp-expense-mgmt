"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useCurrentUser, useEmployeeSheets } from "@/data/hooks";
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
  const fileRef = useRef<HTMLInputElement>(null);
  const idRef = useRef(0);
  const [uploaded, setUploaded] = useState<ReceiptRow[]>([]);
  const [selected, setSelected] = useState<ReceiptRow | null>(null);

  const attached: ReceiptRow[] = (sheets ?? []).flatMap((s) =>
    s.lineItems.flatMap((li) =>
      li.attachments.map((a) => ({
        id: a.id,
        fileName: a.fileName,
        merchant: li.merchant,
        sheetId: s.id,
        scanStatus: a.scanStatus,
      })),
    ),
  );

  const receipts = [...uploaded, ...attached];

  function onFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    const rows: ReceiptRow[] = files.map((f) => ({
      id: `upload-${idRef.current++}`,
      fileName: f.name,
      merchant: "Manual upload",
      sheetId: "Unassigned",
      scanStatus: "clean",
    }));
    setUploaded((prev) => [...rows, ...prev]);
    toast.success(`${files.length} receipt${files.length === 1 ? "" : "s"} uploaded`, {
      description: "Scanned clean — attach to a line item when you add it to a sheet.",
    });
    e.target.value = "";
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
                <div className="flex aspect-[4/3] items-center justify-center rounded-lg border border-outline-variant bg-surface-container-low">
                  <div className="text-center text-on-surface-variant">
                    <Icon name="image" className="text-[40px]" />
                    <p className="mt-2 text-body-sm">Document preview unavailable in demo</p>
                  </div>
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
                {selected.sheetId !== "Unassigned" && (
                  <Button variant="outline" asChild>
                    <Link href={`/employee/sheets/${selected.sheetId}`}>
                      <Icon name="open_in_new" /> Open sheet
                    </Link>
                  </Button>
                )}
                <Button onClick={() => toast.success("Download started")}>
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
