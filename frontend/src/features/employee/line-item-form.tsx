"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAddLineItem, useUpdateLineItem, useMyReceipts, queryKeys } from "@/data/hooks";
import {
  uploadReceipt,
  scanReceipt,
  attachReceiptFromLibrary,
  type ReceiptUpload,
} from "@/data/api";
import { ReceiptPreview } from "@/components/shared/receipt-preview";
import { baselinePolicy } from "@/data/mock";
import {
  EXPENSE_CATEGORIES,
  type Currency,
  type ExpenseCategory,
  type LineItem,
} from "@/data/types";
import { lineItemSchema, type LineItemValues } from "@/lib/schemas";
import { fileIssue, fileNote } from "@/lib/intake";
import {
  policyPreview,
  type PolicyPreviewResult,
} from "@/data/api";
import type { AttachmentInput } from "@/data/api";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DateTimePicker } from "@/components/ui/date-time-picker";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Block sign/exponent keys so monetary number inputs can't go negative. */
function blockNegativeKeys(e: React.KeyboardEvent<HTMLInputElement>) {
  if (["-", "+", "e", "E"].includes(e.key)) e.preventDefault();
}

export function LineItemDialog({
  open,
  onOpenChange,
  sheetId,
  period,
  item,
  siblings,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sheetId: string;
  /** Sheet's expense period ("YYYY-MM") — constrains the expense date to that month. */
  period?: string;
  item?: LineItem;
  siblings: LineItem[];
}) {
  const addLineItem = useAddLineItem();
  const updateLineItem = useUpdateLineItem();
  const qc = useQueryClient();
  const { data: myReceipts } = useMyReceipts();
  // Each entry carries optional `file` bytes (newly picked/dropped) and/or a `downloadUrl`
  // (already on the server: edit-mode attachments, or a My Receipts pick) so we can show a
  // real size + preview either way. `uploadId` is set when the entry was picked from the My
  // Receipts library, so on save we attach it server-side instead of re-uploading bytes.
  const [files, setFiles] = useState<
    (AttachmentInput & { file?: File; downloadUrl?: string; uploadId?: string })[]
  >([]);
  const [dragging, setDragging] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  // Only offer the camera on touch devices — `capture` is a no-op on desktop.
  const [hasCamera, setHasCamera] = useState(false);
  const [policy, setPolicy] = useState<PolicyPreviewResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<LineItemValues>({
    // Cast: the schema coerces number inputs (z.coerce / preprocess), so its
    // input type differs from the inferred output type — runtime is correct.
    resolver: zodResolver(lineItemSchema) as Resolver<LineItemValues>,
    defaultValues: {
      merchant: "",
      description: "",
      category: "Meals & Entertainment",
      categoryOther: "",
      subtotal: undefined as unknown as number,
      tax: undefined,
      receiptTotal: undefined,
      currency: "USD",
      expenseDate: "",
      receiptDatetime: "",
    },
  });

  // Reset whenever the dialog opens (for add) or the edited item changes.
  useEffect(() => {
    if (!open) return;
    setPickerOpen(false);
    if (item) {
      reset({
        merchant: item.merchant,
        description: item.description,
        category: item.category,
        categoryOther: item.categoryOther ?? "",
        // Stored `amount` is the total (subtotal + tax); derive the subtotal back out for the form.
        subtotal: Math.max(0, item.amount - (item.tax ?? 0)),
        tax: item.tax ?? undefined,
        receiptTotal: item.receiptTotal ?? undefined,
        currency: "USD",
        expenseDate: item.expenseDate,
        receiptDatetime: item.receiptDatetime?.slice(0, 16) ?? "",
      });
      setFiles(
        item.attachments.map((a) => ({
          fileName: a.fileName,
          fileType: a.fileType,
          sizeBytes: a.sizeBytes,
          downloadUrl: a.downloadUrl,
        })),
      );
    } else {
      reset();
      setFiles([]);
    }
  }, [open, item, reset]);

  useEffect(() => {
    setHasCamera(window.matchMedia?.("(pointer: coarse)").matches ?? false);
  }, []);

  const v = watch();
  // Receipt-style total: the claim = subtotal + tax (the amount stored on the line item).
  const lineTotal = (Number(v.subtotal) || 0) + (Number(v.tax) || 0);

  // Restrict the expense date to the sheet's period month (backend enforces this too).
  const dateBounds = period
    ? (() => {
        const [y, m] = period.split("-").map(Number);
        const last = new Date(y, m, 0).getDate();
        return { min: `${period}-01`, max: `${period}-${String(last).padStart(2, "0")}` };
      })()
    : undefined;

  // The receipt date must equal the expense date (time may differ). Keep the receipt
  // datetime's day pinned to the expense date whenever it changes, preserving the time.
  useEffect(() => {
    if (!v.expenseDate) return;
    const time = v.receiptDatetime?.slice(11, 16) || "12:00";
    const synced = `${v.expenseDate}T${time}`;
    if (synced !== v.receiptDatetime) {
      setValue("receiptDatetime", synced, { shouldValidate: true });
    }
    // Intentionally keyed on expenseDate only — editing the time shouldn't re-pin.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v.expenseDate]);

  // Live, authoritative policy check from the backend (engine `check_policy`) — debounced as
  // the user types. Offline it falls back to the client validator (see api.policyPreview).
  useEffect(() => {
    if (!lineTotal || lineTotal <= 0) {
      setPolicy(null);
      return;
    }
    const handle = setTimeout(() => {
      policyPreview({
        category: (v.category as ExpenseCategory) ?? undefined,
        amount: lineTotal,
        currency: "USD",
        merchant: v.merchant ?? "",
        description: v.description ?? "",
        expenseDate: v.expenseDate || undefined,
        receiptDatetime: v.receiptDatetime || undefined,
        hasReceipt: files.length > 0,
      })
        .then(setPolicy)
        .catch(() => {});
    }, 400);
    return () => clearTimeout(handle);
  }, [v.category, lineTotal, v.merchant, v.description, v.expenseDate, v.receiptDatetime, files.length]);

  const policyStatus = policy?.status ?? "pass";
  const liveIssues = (policy?.violations ?? []).map((vi) => ({
    level: policyStatus === "fail" ? ("error" as const) : ("warning" as const),
    message: vi.message,
    clauseRef: vi.code,
  }));

  function acceptFiles(picked: File[]) {
    const accepted: (AttachmentInput & { file?: File })[] = [];
    for (const f of picked) {
      const issue = fileIssue(f, baselinePolicy);
      if (issue) {
        toast.error(`${f.name}: ${issue}`);
        continue;
      }
      accepted.push({
        fileName: f.name,
        fileType: f.type || "application/octet-stream",
        sizeBytes: f.size,
        file: f,
      });
    }
    if (accepted.length) setFiles((prev) => [...prev, ...accepted]);
  }

  function onPickFiles(e: React.ChangeEvent<HTMLInputElement>) {
    acceptFiles(Array.from(e.target.files ?? []));
    e.target.value = "";
  }

  /** Attach a receipt the employee already uploaded on the My Receipts page. The bytes already
   *  live on the server, so we only carry a reference (`uploadId`) + preview URL; the actual
   *  attach happens on save via `attachReceiptFromLibrary`. */
  function addFromUpload(u: ReceiptUpload) {
    if (files.some((f) => f.uploadId === u.id)) return;
    setFiles((prev) => [
      ...prev,
      {
        fileName: u.fileName,
        fileType: u.fileType,
        sizeBytes: u.sizeBytes,
        downloadUrl: u.downloadUrl,
        uploadId: u.id,
      },
    ]);
  }

  // My Receipts entries not already added to this line item.
  const availableUploads = (myReceipts ?? []).filter(
    (u) => !files.some((f) => f.uploadId === u.id),
  );

  function onDrop(e: React.DragEvent) {
    // Without this, the browser navigates to the dropped file (opens a new tab).
    e.preventDefault();
    setDragging(false);
    acceptFiles(Array.from(e.dataTransfer.files ?? []));
  }

  const onSubmit = handleSubmit(async (values) => {
    const tax = values.tax != null ? Number(values.tax) : undefined;
    const input = {
      merchant: values.merchant,
      description: values.description,
      category: values.category,
      categoryOther: values.category === "Other" ? values.categoryOther?.trim() : undefined,
      // Stored claim = subtotal + tax (the receipt total).
      amount: Number(values.subtotal) + (tax ?? 0),
      tax,
      receiptTotal: values.receiptTotal != null ? Number(values.receiptTotal) : undefined,
      currency: "USD" as Currency,
      expenseDate: values.expenseDate,
      receiptDatetime: values.receiptDatetime || undefined,
      attachments: files,
    };
    try {
      const result = item
        ? await updateLineItem.mutateAsync({ sheetId, lineItemId: item.id, input })
        : await addLineItem.mutateAsync({ sheetId, input });

      // Persist receipts. Two kinds: freshly picked/dropped files (upload the bytes) and
      // picks from the My Receipts library (already on the server — attach by reference). On
      // add, the new line item is the one in the returned sheet that wasn't an existing sibling.
      const newFiles = files.filter((f) => f.file && !f.uploadId);
      const libraryPicks = files.filter((f) => f.uploadId);
      if (newFiles.length || libraryPicks.length) {
        let targetId = item?.id;
        if (!targetId) {
          const known = new Set(siblings.map((s) => s.id));
          targetId = result.lineItems.find((li) => !known.has(li.id))?.id;
        }
        if (targetId) {
          for (const f of newFiles) {
            await uploadReceipt({ sheetId, lineItemId: targetId, file: f.file! });
          }
          // A receipt picked from the My Receipts library moves onto this line item server-side.
          for (const f of libraryPicks) {
            await attachReceiptFromLibrary({ sheetId, lineItemId: targetId, receiptId: f.uploadId! });
          }
          qc.invalidateQueries({ queryKey: queryKeys.sheet(sheetId) });
          if (libraryPicks.length) qc.invalidateQueries({ queryKey: queryKeys.myReceipts });

          // Fire the receipt scan (Document Intelligence) but DON'T await it — it can take
          // several seconds, and blocking here keeps the dialog open. Fire-and-forget so the
          // dialog closes immediately; the scan still persists the derived values + Finance
          // review flag server-side (never shown to the employee).
          void scanReceipt({ sheetId, lineItemId: targetId }).catch(() => {
            /* scan is best-effort; never block the save */
          });
        }
      }

      toast.success(item ? "Line item updated" : "Line item added");
      onOpenChange(false);
    } catch (e) {
      toast.error("Couldn't save the line item", {
        description: e instanceof Error ? e.message : "Please try again.",
      });
    }
  });

  const blockingError = liveIssues.find((i) => i.level === "error");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{item ? "Edit line item" : "Add line item"}</DialogTitle>
          <DialogDescription>
            Enter the bill details and attach supporting documents. Checks run as you type.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="li-merchant">Merchant</Label>
              <Input id="li-merchant" placeholder="e.g. Delta Airlines" {...register("merchant")} />
              {errors.merchant && <p className="text-label-md text-error">{errors.merchant.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-category">Expense Type</Label>
              <Select
                value={v.category}
                onValueChange={(val) => setValue("category", val as ExpenseCategory, { shouldValidate: true })}
              >
                <SelectTrigger id="li-category">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  {EXPENSE_CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {v.category === "Other" && (
            <div className="space-y-1.5 rounded-md border border-secondary/30 bg-secondary-container/30 p-3">
              <Label htmlFor="li-category-other">Specify expense type</Label>
              <Input
                id="li-category-other"
                placeholder="e.g. Conference registration, professional membership…"
                {...register("categoryOther")}
              />
              {errors.categoryOther ? (
                <p className="text-label-md text-error">{errors.categoryOther.message}</p>
              ) : (
                <p className="text-label-md text-on-surface-variant">
                  &ldquo;Other&rdquo; needs a specific type before it can be submitted.
                </p>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="li-desc">Description / Business Justification</Label>
            <Input id="li-desc" placeholder="What was this expense for?" {...register("description")} />
            {errors.description && <p className="text-label-md text-error">{errors.description.message}</p>}
          </div>

          {/* Receipt-style amounts: Subtotal + Tax = Total (the claim). */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="li-subtotal">Subtotal</Label>
              <Input
                id="li-subtotal"
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                placeholder="0.00"
                onKeyDown={blockNegativeKeys}
                {...register("subtotal")}
              />
              {errors.subtotal && (
                <p className="text-label-md text-error">{errors.subtotal.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-tax">
                Tax / VAT <span className="text-on-surface-variant">(optional)</span>
              </Label>
              <Input
                id="li-tax"
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                placeholder="0.00"
                onKeyDown={blockNegativeKeys}
                {...register("tax")}
              />
              {errors.tax && <p className="text-label-md text-error">{errors.tax.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-total">Total</Label>
              <Input
                id="li-total"
                value={lineTotal.toFixed(2)}
                readOnly
                disabled
                className="cursor-not-allowed bg-surface-container-low font-mono font-semibold"
              />
              <p className="text-label-md text-on-surface-variant">Subtotal + Tax</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="li-currency">Currency</Label>
              <Input
                id="li-currency"
                value="USD"
                readOnly
                disabled
                className="cursor-not-allowed bg-surface-container-low"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-date">Expense Date</Label>
              <DateTimePicker
                id="li-date"
                mode="date"
                value={v.expenseDate}
                onChange={(val) => setValue("expenseDate", val, { shouldValidate: true })}
                placeholder="Select date"
                min={dateBounds?.min}
                max={dateBounds?.max}
              />
              {errors.expenseDate && <p className="text-label-md text-error">{errors.expenseDate.message}</p>}
            </div>
          </div>

          <p className="flex items-start gap-1.5 text-label-md text-on-surface-variant">
            <Icon name="info" className="mt-px shrink-0 text-[14px] text-secondary" />
            Amounts are recorded in USD. A receipt in another currency is converted to USD
            using the exchange rate on the expense date.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="li-rdt">Receipt Date / Time</Label>
              <DateTimePicker
                id="li-rdt"
                mode="datetime"
                value={v.receiptDatetime}
                onChange={(val) => setValue("receiptDatetime", val, { shouldValidate: true })}
                placeholder={v.expenseDate ? "Pick the time" : "Set the expense date first"}
                // Pinned to the expense date — only the time of day is selectable.
                min={v.expenseDate || dateBounds?.min}
                max={v.expenseDate || dateBounds?.max}
              />
              {errors.receiptDatetime ? (
                <p className="text-label-md text-error">{errors.receiptDatetime.message}</p>
              ) : (
                <p className="text-label-md text-on-surface-variant">
                  Same day as the expense date; set the time from the receipt.
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-receipt-total">
                Receipt Total <span className="text-on-surface-variant">(optional)</span>
              </Label>
              <Input
                id="li-receipt-total"
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                placeholder="0.00"
                onKeyDown={blockNegativeKeys}
                {...register("receiptTotal")}
              />
              {errors.receiptTotal ? (
                <p className="text-label-md text-error">{errors.receiptTotal.message}</p>
              ) : (
                <p className="text-label-md text-on-surface-variant">
                  The grand total printed on the receipt (should match Subtotal + Tax).
                </p>
              )}
            </div>
          </div>

          {/* Attachments */}
          <div className="space-y-2">
            <Label>Supporting Documents</Label>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setDragging(false);
              }}
              onDrop={onDrop}
              className={
                "flex w-full flex-col items-center justify-center gap-1 rounded border border-dashed px-4 py-5 transition-colors hover:border-secondary hover:text-primary " +
                (dragging
                  ? "border-secondary bg-secondary-container/30 text-primary"
                  : "border-outline-variant bg-surface-container-low text-on-surface-variant")
              }
            >
              <Icon name="upload_file" className="text-[22px]" />
              <span className="text-body-sm font-medium">
                {dragging ? "Drop to attach" : "Click or drop receipts here"}
              </span>
              <span className="font-mono text-label-sm">
                {baselinePolicy.allowed_extensions.join("  ")} · max {baselinePolicy.max_file_mb} MB
              </span>
            </button>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={baselinePolicy.allowed_extensions.join(",")}
              className="hidden"
              onChange={onPickFiles}
            />
            {/* On mobile these open the photo library / camera directly; on desktop
                they fall back to the file dialog. */}
            <input
              ref={galleryRef}
              type="file"
              multiple
              accept="image/*"
              className="hidden"
              onChange={onPickFiles}
            />
            <input
              ref={cameraRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={onPickFiles}
            />

            {/* Other ways to attach: device gallery, camera, or a receipt already
                uploaded on the My Receipts page. */}
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => galleryRef.current?.click()}>
                <Icon name="photo_library" /> Gallery
              </Button>
              {hasCamera && (
                <Button type="button" variant="outline" size="sm" onClick={() => cameraRef.current?.click()}>
                  <Icon name="photo_camera" /> Camera
                </Button>
              )}
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={availableUploads.length === 0}
                onClick={() => setPickerOpen((o) => !o)}
                title={
                  availableUploads.length === 0
                    ? "No unassigned receipts in My Receipts"
                    : "Pick a receipt you already uploaded"
                }
              >
                <Icon name="receipt_long" /> From My Receipts ({availableUploads.length})
              </Button>
            </div>

            {pickerOpen && availableUploads.length > 0 && (
              <ul className="space-y-1 rounded border border-outline-variant bg-surface-container-low p-2">
                {availableUploads.map((u) => (
                  <li key={u.id} className="flex items-center gap-2 rounded px-1 py-1">
                    <ReceiptPreview
                      downloadUrl={u.downloadUrl}
                      fileName={u.fileName}
                      fileType={u.fileType}
                    />
                    <span className="flex-1 truncate text-body-sm">{u.fileName}</span>
                    <span className="font-mono text-label-sm text-on-surface-variant">
                      {formatSize(u.sizeBytes)}
                    </span>
                    <Button type="button" variant="ghost" size="sm" onClick={() => addFromUpload(u)}>
                      <Icon name="add" /> Add
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            {files.length > 0 && (
              <ul className="space-y-1">
                {files.map((f, i) => {
                  const note = fileNote(f.fileName);
                  return (
                    <li
                      key={`${f.fileName}-${i}`}
                      className="rounded border border-outline-variant bg-surface-container-lowest px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        <ReceiptPreview
                          file={f.file}
                          downloadUrl={f.downloadUrl}
                          fileName={f.fileName}
                          fileType={f.fileType}
                        />
                        <span className="flex-1 truncate text-body-sm">{f.fileName}</span>
                        <span className="font-mono text-label-sm text-on-surface-variant">
                          {formatSize(f.sizeBytes)}
                        </span>
                        <button
                          type="button"
                          onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                          className="text-on-surface-variant hover:text-error"
                          aria-label="Remove"
                        >
                          <Icon name="close" className="text-[16px]" />
                        </button>
                      </div>
                      {note && (
                        <p className="mt-1 flex items-center gap-1 font-mono text-label-sm text-tertiary">
                          <Icon name="info" className="text-[12px]" /> {note}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {files.length === 0 && (
              <p className="flex items-center gap-1 text-label-md text-error">
                <Icon name="error" className="text-[14px]" />
                A receipt is required to save this line item.
              </p>
            )}
          </div>

          {/* Live intake checks */}
          {liveIssues.length > 0 && (
            <div className="space-y-1.5 rounded border border-outline-variant bg-surface-container-low p-3">
              <p className="font-mono text-label-md uppercase tracking-wide text-on-surface-variant">
                Intake checks
              </p>
              {liveIssues.map((iss, i) => (
                <div
                  key={i}
                  className={
                    "flex items-start gap-1.5 text-body-sm " +
                    (iss.level === "error" ? "text-error" : "text-yellow-600")
                  }
                >
                  <Icon
                    name={iss.level === "error" ? "error" : "warning"}
                    className="mt-0.5 text-[16px]"
                  />
                  <span className="text-on-surface">
                    {iss.message}{" "}
                    <span className="font-mono text-label-sm text-on-surface-variant">[{iss.clauseRef}]</span>
                  </span>
                </div>
              ))}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              loading={addLineItem.isPending || updateLineItem.isPending}
              disabled={!!blockingError || files.length === 0}
            >
              {item ? "Save changes" : "Add line item"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
