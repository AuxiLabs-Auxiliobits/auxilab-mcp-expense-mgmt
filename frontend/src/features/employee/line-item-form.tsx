"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAddLineItem, useUpdateLineItem, queryKeys } from "@/data/hooks";
import { uploadReceipt, scanReceipt } from "@/data/api";
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
  policyAdvisory,
  type PolicyPreviewResult,
  type PolicyAdvisory,
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
  item,
  siblings,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sheetId: string;
  item?: LineItem;
  siblings: LineItem[];
}) {
  const addLineItem = useAddLineItem();
  const updateLineItem = useUpdateLineItem();
  const qc = useQueryClient();
  // Each entry carries optional `file` bytes — present for newly picked/dropped files,
  // absent for attachments already on the server (edit mode).
  const [files, setFiles] = useState<(AttachmentInput & { file?: File })[]>([]);
  const [dragging, setDragging] = useState(false);
  const [policy, setPolicy] = useState<PolicyPreviewResult | null>(null);
  const [advisory, setAdvisory] = useState<PolicyAdvisory>({});
  const fileRef = useRef<HTMLInputElement>(null);

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
      amount: undefined as unknown as number,
      currency: "USD",
      expenseDate: "",
      receiptDatetime: "",
      tax: undefined,
    },
  });

  // Reset whenever the dialog opens (for add) or the edited item changes.
  useEffect(() => {
    if (!open) return;
    if (item) {
      reset({
        merchant: item.merchant,
        description: item.description,
        category: item.category,
        categoryOther: item.categoryOther ?? "",
        amount: item.amount,
        currency: "USD",
        expenseDate: item.expenseDate,
        receiptDatetime: item.receiptDatetime?.slice(0, 16) ?? "",
        tax: item.tax,
      });
      setFiles(
        item.attachments.map((a) => ({
          fileName: a.fileName,
          fileType: a.fileType,
          sizeBytes: a.sizeBytes,
        })),
      );
    } else {
      reset();
      setFiles([]);
    }
  }, [open, item, reset]);

  const v = watch();

  // Live, authoritative policy check from the backend (engine `check_policy`) — debounced as
  // the user types. Offline it falls back to the client validator (see api.policyPreview).
  useEffect(() => {
    const amount = Number(v.amount);
    if (!amount || amount <= 0) {
      setPolicy(null);
      return;
    }
    const handle = setTimeout(() => {
      policyPreview({
        category: (v.category as ExpenseCategory) ?? undefined,
        amount,
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
  }, [v.category, v.amount, v.merchant, v.description, v.expenseDate, v.receiptDatetime, files.length]);

  // RAG advisory: the relevant agency policy clause (advisory only; empty offline).
  useEffect(() => {
    const handle = setTimeout(() => {
      policyAdvisory({
        category: (v.category as ExpenseCategory) ?? undefined,
        merchant: v.merchant ?? "",
        description: v.description ?? "",
      })
        .then(setAdvisory)
        .catch(() => {});
    }, 500);
    return () => clearTimeout(handle);
  }, [v.category, v.merchant, v.description]);

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
    if (fileRef.current) fileRef.current.value = "";
  }

  function onDrop(e: React.DragEvent) {
    // Without this, the browser navigates to the dropped file (opens a new tab).
    e.preventDefault();
    setDragging(false);
    acceptFiles(Array.from(e.dataTransfer.files ?? []));
  }

  const onSubmit = handleSubmit(async (values) => {
    const input = {
      merchant: values.merchant,
      description: values.description,
      category: values.category,
      categoryOther: values.category === "Other" ? values.categoryOther?.trim() : undefined,
      amount: Number(values.amount),
      currency: "USD" as Currency,
      expenseDate: values.expenseDate,
      receiptDatetime: values.receiptDatetime || undefined,
      tax: values.tax != null ? Number(values.tax) : undefined,
      attachments: files,
    };
    try {
      const result = item
        ? await updateLineItem.mutateAsync({ sheetId, lineItemId: item.id, input })
        : await addLineItem.mutateAsync({ sheetId, input });

      // Upload the actual receipt bytes for any newly added files. On add, the new
      // line item is the one in the returned sheet that wasn't an existing sibling.
      const newFiles = files.filter((f) => f.file);
      if (newFiles.length) {
        let targetId = item?.id;
        if (!targetId) {
          const known = new Set(siblings.map((s) => s.id));
          targetId = result.lineItems.find((li) => !known.has(li.id))?.id;
        }
        if (targetId) {
          for (const f of newFiles) {
            await uploadReceipt({ sheetId, lineItemId: targetId, file: f.file! });
          }
          qc.invalidateQueries({ queryKey: queryKeys.sheet(sheetId) });

          // Live invoice scan + reconciliation (advisory — never blocks).
          try {
            const scan = await scanReceipt({ sheetId, lineItemId: targetId });
            if (scan && scan.total != null && scan.matchesEntered === false) {
              toast.warning(
                `Receipt total ${scan.total} doesn't match the entered ${input.amount}`,
                {
                  description:
                    scan.reconciles === false
                      ? "The receipt's line items + tax don't sum to its total."
                      : "Review the amount against the receipt.",
                },
              );
            }
          } catch {
            /* scan is best-effort; never block the save */
          }
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

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="li-amount">Amount</Label>
              <Input
                id="li-amount"
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                placeholder="0.00"
                onKeyDown={blockNegativeKeys}
                {...register("amount")}
              />
              {errors.amount && <p className="text-label-md text-error">{errors.amount.message}</p>}
            </div>
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
                placeholder="Optional"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-tax">Tax / VAT</Label>
              <Input
                id="li-tax"
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                placeholder="optional"
                onKeyDown={blockNegativeKeys}
                {...register("tax")}
              />
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
                        <Icon name="description" className="text-[18px] text-secondary" />
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

          {/* RAG advisory — cited agency policy clause (advisory only, never blocks) */}
          {advisory.clause && (
            <div className="space-y-1 rounded border border-secondary/30 bg-secondary-container/20 p-3">
              <p className="flex items-center gap-1.5 font-mono text-label-md uppercase tracking-wide text-on-surface-variant">
                <Icon name="smart_toy" className="text-[14px] text-secondary" />
                AI note · {advisory.clause.source}
              </p>
              <p className="text-body-sm text-on-surface">{advisory.clause.text}</p>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!!blockingError || addLineItem.isPending || updateLineItem.isPending}>
              {item ? "Save changes" : "Add line item"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
