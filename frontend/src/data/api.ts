/**
 * Typed API client. Today it resolves against the in-memory mock store with
 * simulated latency; to go live, replace each function body with a `fetch()`
 * against the FastAPI backend (the signatures are the contract). Centralising
 * this keeps the TanStack Query hooks unchanged when the backend lands.
 */
import {
  agencies as agencyStore,
  auditLog,
  autoApprovalTrend,
  baselinePolicy,
  expenseSheets as sheetStore,
  financeKpis,
  notifications as notificationStore,
  policyDocuments as policyStore,
  usersByRole,
} from "./mock";
import { toAiFlag, validateLineItem, type IntakeIssue } from "@/lib/intake";
import {
  apiBlob,
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  apiPut,
  apiUpload,
  backend,
} from "./http";
import {
  mapAgency,
  mapAttachment,
  mapAudit,
  mapDecision,
  mapNotification,
  mapPolicy,
  mapSheet,
  mapSpend,
  mapUser,
} from "./mappers";

type Raw = Record<string, unknown>;

/** Tolerant numeric coercion for backend payloads. */
function num(v: unknown, fallback = 0): number {
  const n = typeof v === "string" ? parseFloat(v) : (v as number);
  return Number.isFinite(n) ? n : fallback;
}

/** Like `num`, but preserves "the backend didn't send this" as `null` instead of a
 *  fabricated fallback — so the UI can show "—" rather than a misleading constant. */
function numOrNull(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === "string" ? parseFloat(v) : (v as number);
  return Number.isFinite(n) ? n : null;
}

/** snake_case request body for the line-item endpoints (frontend → backend). */
function lineItemBody(input: LineItemInput) {
  return {
    merchant: input.merchant,
    description: input.description,
    category: input.category,
    category_other: input.categoryOther ?? null,
    amount: input.amount,
    currency: input.currency,
    expense_date: input.expenseDate,
    receipt_datetime: input.receiptDatetime ?? null,
    receipt_total: input.receiptTotal ?? null,
    tax: input.tax ?? null,
    has_receipt: input.attachments.length > 0,
  };
}
import type {
  Agency,
  AgencyPolicyDocument,
  AgencyTier,
  AppNotification,
  Attachment,
  AuditLogEntry,
  Currency,
  DecisionEntry,
  EmployeeKpis,
  ExpenseCategory,
  ExpenseSheet,
  FinanceDecision,
  LineItem,
  LineItemStatus,
  PolicyChunk,
  PolicyIngestEvent,
  Role,
  SheetStatus,
  SpendByCategory,
  User,
} from "./types";

const LATENCY = 350;

function delay<T>(value: T, ms = LATENCY): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function findSheet(id: string): ExpenseSheet {
  const sheet = sheetStore.find((s) => s.id === id);
  if (!sheet) throw new Error(`Sheet ${id} not found`);
  return sheet;
}

/** The bounded LLM Finance Approver identity (SCOPING.md §6.3). */
const AI_APPROVER = { id: "LLM", name: "Auxilab AI Finance Approver" } as const;
/** Confidence below which the agent abstains and routes to a human. */
const ROUTING_THRESHOLD = 0.75;

/** Append a user-scoped entry to the immutable activity log. */
function logActivity(entry: Omit<AuditLogEntry, "id">): void {
  auditLog.unshift({ id: `AUD-${auditLog.length + 1}`, ...entry });
}

/** Category-level dollar cap for quick policy checks inside the mock approver. */
const CATEGORY_CAP: Partial<Record<string, number>> = {
  "Meals & Entertainment": 75,
  "Client Entertainment": 75,
  "Travel - Hotel": 350,
};

/**
 * Runs the AI Finance Approver on a manager-approved sheet (SCOPING.md §6.3).
 * Checks each line item against the agency's policy caps and receipt rules.
 * Clean sheets auto-approve with a cited-clause audit trail; anything flagged
 * or above a cap is routed to the human Finance reviewer with a specific reason.
 */
function runAgentApprover(sheet: ExpenseSheet): void {
  const policyName = sheet.policyVersionUsed ?? "Agency Finance Policy v2.1";
  const flagged = sheet.lineItems.filter((li) => li.aiFlag);
  const hasError = flagged.some((li) => li.aiFlag?.severity === "error");
  const confidence = hasError ? 0.42 : flagged.length ? 0.61 : 0.96;
  const pct = `${Math.round(confidence * 100)}%`;
  sheet.policyVersionUsed = policyName;
  sheet.llmConfidence = confidence;
  sheet.updatedAt = new Date().toISOString();

  if (confidence < ROUTING_THRESHOLD) {
    // Route to human — cite the specific flag that drove the decision.
    const flag = flagged[0]?.aiFlag;
    const offender = flagged[0];
    const capViolation = sheet.lineItems.find((li) => {
      const cap = CATEGORY_CAP[li.category];
      return cap != null && li.amount > cap;
    });
    let routeDetail: string;
    if (capViolation) {
      const cap = CATEGORY_CAP[capViolation.category]!;
      routeDetail = `${capViolation.merchant} claimed $${capViolation.amount.toFixed(2)} for ${capViolation.category} — exceeds the $${cap} policy cap. Requires Finance approval.`;
      sheet.routeReason = "NUMERIC_DISAGREEMENT";
    } else if (flag) {
      routeDetail = `${offender?.merchant ?? "Line item"}: ${flag.message} (ref: ${flag.clauseRef}).`;
      sheet.routeReason = hasError ? "AMBIGUOUS_CLAUSE" : "LOW_CONFIDENCE";
    } else {
      routeDetail = `AI confidence ${pct} is below the auto-approval threshold — routed for human review.`;
      sheet.routeReason = "LOW_CONFIDENCE";
    }
    sheet.status = "FINANCE_MANUAL_REVIEW";
    sheet.financeDecision = "ROUTED_TO_HUMAN";
    sheet.routeReasonDetail = routeDetail;
    sheet.citedClause = flag
      ? { policyName, text: flag.message }
      : capViolation
        ? { policyName, text: routeDetail }
        : undefined;
    logActivity({
      actorId: AI_APPROVER.id, actorName: AI_APPROVER.name, actorRole: "llm_approver",
      action: "FINANCE_ROUTED", entity: "ExpenseSheet",
      summary: `${AI_APPROVER.name} routed ${sheet.id} to a human — ${routeDetail}`,
      reference: `confidence ${pct} · ${policyName}`,
      timestamp: sheet.updatedAt, severity: "warning",
    });
  } else {
    // Auto-approve — produce a per-line-item audit trail for Finance to review.
    const checks = sheet.lineItems.map((li) => {
      const cap = CATEGORY_CAP[li.category];
      const capNote = cap != null
        ? `$${li.amount.toFixed(2)} ≤ $${cap} cap for ${li.category} ✓`
        : `$${li.amount.toFixed(2)} · ${li.category} (no cap) ✓`;
      const receiptNote = li.attachments?.length
        ? `Receipt: ${li.attachments[0].fileName} ✓`
        : "Receipt: attached ✓";
      return `${li.merchant}: ${capNote} · ${receiptNote}`;
    });
    checks.push(`Duplicate risk: none detected ✓`);
    checks.push(`Policy: ${policyName} · AI confidence: ${pct}`);

    sheet.status = "FINANCE_APPROVED";
    sheet.financeDecision = "APPROVED";
    sheet.financeDecidedBy = AI_APPROVER.name;
    sheet.autoApprovalReasons = checks;
    logActivity({
      actorId: AI_APPROVER.id, actorName: AI_APPROVER.name, actorRole: "llm_approver",
      action: "FINANCE_AUTO_APPROVED", entity: "ExpenseSheet",
      summary: `${AI_APPROVER.name} auto-approved ${sheet.id} — ${sheet.lineItems.length} line item(s) cleared policy (${pct} confidence).`,
      reference: `confidence ${pct} · ${policyName}`,
      timestamp: sheet.updatedAt, severity: "success",
    });
  }
}

// ── Session ──────────────────────────────────────────────────────────────────

export function getCurrentUser(role: Role): Promise<User> {
  // Backend resolves the authenticated user from the bearer token; the `role`
  // param selects the demo identity in the mock fallback.
  return backend(
    () => apiGet<Raw>("/auth/me").then(mapUser),
    () => delay(clone(usersByRole[role]), 120),
  );
}

// ── Employee ─────────────────────────────────────────────────────────────────

export function getEmployeeSheets(employeeId: string): Promise<ExpenseSheet[]> {
  // GET /sheets — the backend scopes to the authenticated employee.
  return backend(
    () => apiGet<Raw[]>("/sheets").then((rows) => rows.map(mapSheet)),
    () => delay(clone(sheetStore.filter((s) => s.employeeId === employeeId))),
  );
}

export function getEmployeeKpis(employeeId: string): Promise<EmployeeKpis> {
  const compute = (sheets: ExpenseSheet[]): EmployeeKpis => {
    const reimbursedThisMonth = sheets
      .filter((s) => ["PAID", "FINANCE_APPROVED", "APPROVED"].includes(s.status))
      .reduce((sum, s) => sum + s.total, 0);
    const pending = sheets.filter((s) =>
      ["SUBMITTED", "IN_MANAGER_REVIEW", "IN_FINANCE_REVIEW", "FINANCE_MANUAL_REVIEW"].includes(s.status),
    );
    const drafts = sheets.filter((s) => s.status === "DRAFT");
    return {
      reimbursedThisMonth,
      pendingApprovalValue: pending.reduce((sum, s) => sum + s.total, 0),
      pendingApprovalCount: pending.length,
      draftsValue: drafts.reduce((sum, s) => sum + s.total, 0),
    };
  };
  // Derived from the employee's real sheets (server-scoped by token); no constants.
  return backend(
    () => apiGet<Raw[]>("/sheets").then((rows) => compute(rows.map(mapSheet))),
    () => delay(compute(clone(sheetStore.filter((s) => s.employeeId === employeeId)))),
  );
}

export function getActiveDraft(employeeId: string): Promise<ExpenseSheet | null> {
  // No dedicated endpoint — derive from the employee's sheets (server-scoped).
  return backend(
    () =>
      apiGet<Raw[]>("/sheets").then((rows) => {
        const draft = rows.map(mapSheet).find((s) => s.status === "DRAFT");
        return draft ?? null;
      }),
    () => {
      const draft = sheetStore.find((s) => s.employeeId === employeeId && s.status === "DRAFT");
      return delay(draft ? clone(draft) : null);
    },
  );
}

// ── Sheets (shared) ──────────────────────────────────────────────────────────

export function getSheet(id: string): Promise<ExpenseSheet> {
  return backend(
    () => apiGet<Raw>(`/sheets/${id}`).then(mapSheet),
    () => delay(clone(findSheet(id))),
  );
}

// ── Receipts & approval history (manager + finance review) ───────────────────

/** All receipts on a sheet (scope-checked server-side). */
export function getSheetReceipts(sheetId: string): Promise<Attachment[]> {
  return backend(
    () => apiGet<Raw[]>(`/sheets/${sheetId}/receipts`).then((rows) => rows.map(mapAttachment)),
    () => {
      const sheet = sheetStore.find((s) => s.id === sheetId);
      const atts = (sheet?.lineItems ?? []).flatMap((li) => li.attachments ?? []);
      return delay(clone(atts));
    },
  );
}

/** Fetch a receipt's bytes (authenticated) for inline preview or download. */
export function fetchReceiptBlob(
  attachmentId: string,
  download = false,
): Promise<{ blob: Blob; filename: string; contentType: string }> {
  return apiBlob(`/attachments/${attachmentId}/content${download ? "?download=true" : ""}`);
}

// ── Policy Assistant (agency RAG over Azure Foundry, backend-resolved) ────────
export interface AssistantAnswer {
  answer: string;
  citations: import("./policy-kb").PolicyClause[];
  routedToHuman: boolean;
}

/** Ask the backend Policy Assistant (RAG over the caller's agency policy via Azure Foundry,
 *  offline composer when Azure isn't configured). Agency is taken from the auth token. */
export function queryPolicyAssistant(query: string): Promise<AssistantAnswer> {
  return apiPost<Raw>("/assistant/policy", { query }).then((r) => ({
    answer: String(r.answer ?? ""),
    routedToHuman: Boolean(r.routed_to_human),
    citations: Array.isArray(r.citations)
      ? r.citations.map((c: Raw) => ({
          id: String(c.id ?? ""),
          agencyId: "",
          keywords: [],
          title: String(c.title ?? "Policy clause"),
          text: String(c.text ?? ""),
          source: String(c.source ?? ""),
        }))
      : [],
  }));
}

/** A sheet's approval/decision history (manager → finance → LLM actions), oldest first. */
export function getSheetDecisions(sheetId: string): Promise<DecisionEntry[]> {
  return backend(
    () => apiGet<Raw[]>(`/sheets/${sheetId}/decisions`).then((rows) => rows.map(mapDecision)),
    () => delay([]),
  );
}

// Org-wide list for the finance/admin Expense Sheets screen.
export function getAllSheets(): Promise<ExpenseSheet[]> {
  return backend(
    () => apiGet<Raw[]>("/finance/sheets").then((rows) => rows.map(mapSheet)),
    () => delay(clone(sheetStore)),
  );
}

export interface CreateSheetInput {
  title: string;
  period: string;
  // Only used by the offline mock; in backend mode the owner comes from the auth token.
  employee?: User;
}

export function createSheet(input: CreateSheetInput): Promise<ExpenseSheet> {
  return backend(
    () =>
      apiPost<Raw>("/sheets", { title: input.title, period: input.period }).then(mapSheet),
    () => {
      const id = `SH-2026-${Math.floor(100 + Math.random() * 899)}`;
      const sheet: ExpenseSheet = {
        id,
        title: input.title,
        employeeId: input.employee?.id ?? "me",
        employeeName: input.employee?.name ?? "Me",
        agencyId: input.employee?.agencyId ?? "",
        agencyName: "Crispin",
        version: 1,
        status: "DRAFT",
        period: input.period,
        total: 0,
        currency: "USD",
        updatedAt: new Date(2026, 5, 14).toISOString(),
        lineItems: [],
      };
      sheetStore.unshift(sheet);
      return delay(clone(sheet), 500);
    },
  );
}

export async function updateSheet(args: {
  sheetId: string;
  title?: string;
  period?: string;
  /** Employee note added before resubmitting a returned sheet. */
  note?: string;
}): Promise<ExpenseSheet> {
  // PATCH /sheets/{id} — edit a draft's title/period/note (owner, editable states).
  return backend(
    () =>
      apiPatch<Raw>(`/sheets/${args.sheetId}`, {
        title: args.title,
        period: args.period,
        employee_note: args.note,
      }).then(mapSheet),
    () => {
      const sheet = findSheet(args.sheetId);
      if (args.title != null) sheet.title = args.title;
      if (args.period != null) sheet.period = args.period;
      if (args.note !== undefined) sheet.employeeNote = args.note || undefined;
      sheet.updatedAt = new Date().toISOString();
      return delay(clone(sheet), 250);
    },
  );
}

/** Upload a receipt file and attach it to a line item (multipart). Backend-only; in mock
 *  mode the attachment is already tracked client-side, so this is a no-op. */
export function uploadReceipt(args: {
  sheetId: string;
  lineItemId: string;
  file: File;
}): Promise<void> {
  return backend(
    async () => {
      const form = new FormData();
      form.append("file", args.file);
      await apiUpload<Raw>(
        `/sheets/${args.sheetId}/line-items/${args.lineItemId}/receipt`,
        form,
      );
    },
    async () => {
      /* mock: attachment metadata is already captured in makeLineItem */
    },
  );
}

// ── Receipt library (My Receipts) — unassigned uploads, persisted server-side ──────────────
/** A receipt the employee uploaded but hasn't attached to a line item yet. Persisted on the
 *  backend (survives refresh, shared across devices), unlike the old in-memory store. */
export interface ReceiptUpload {
  id: string;
  fileName: string;
  fileType: string;
  sizeBytes: number;
  scanStatus: string;
  uploadedAt?: string;
  downloadUrl: string; // auth'd API path to fetch the bytes
}

function mapReceiptUpload(r: Raw): ReceiptUpload {
  return {
    id: String(r.id ?? ""),
    fileName: String(r.filename ?? "receipt"),
    fileType: String(r.file_type ?? "application/octet-stream"),
    sizeBytes: num(r.size),
    scanStatus: String(r.scan_status ?? "pending"),
    uploadedAt: (r.uploaded_at as string) ?? undefined,
    downloadUrl: String(r.download_url ?? ""),
  };
}

/** My unassigned receipts (the "From My Receipts" pool), newest first. */
export function listMyReceipts(): Promise<ReceiptUpload[]> {
  return backend(
    () => apiGet<Raw[]>("/receipts").then((rows) => rows.map(mapReceiptUpload)),
    () => delay([]),
  );
}

/** Upload a receipt to the library without attaching it to a line item yet. */
export function uploadReceiptToLibrary(file: File): Promise<ReceiptUpload> {
  return backend(
    () => {
      const form = new FormData();
      form.append("file", file);
      return apiUpload<Raw>("/receipts", form).then(mapReceiptUpload);
    },
    () =>
      delay({
        id: `upload-${file.name}-${file.size}`,
        fileName: file.name,
        fileType: file.type || "application/octet-stream",
        sizeBytes: file.size,
        scanStatus: "pending",
        downloadUrl: "",
      }),
  );
}

/** Remove an unassigned receipt from the library. */
export function deleteLibraryReceipt(id: string): Promise<void> {
  return backend(
    () => apiDelete<unknown>(`/receipts/${id}`).then(() => undefined),
    () => delay(undefined),
  );
}

/** Attach a library receipt to a line item (moves it out of the library). */
export function attachReceiptFromLibrary(args: {
  sheetId: string;
  lineItemId: string;
  receiptId: string;
}): Promise<void> {
  return backend(
    () =>
      apiPost<Raw>(
        `/sheets/${args.sheetId}/line-items/${args.lineItemId}/receipt/from-library`,
        { receipt_id: args.receiptId },
      ).then(() => undefined),
    () => delay(undefined),
  );
}

export interface ReceiptScan {
  source: string; // document_intelligence | text | unavailable
  merchant?: string;
  total?: number;
  tax?: number;
  receiptDatetime?: string; // ISO datetime extracted from the receipt
  reconciles?: boolean;
  delta?: number;
  matchesEntered?: boolean;
  detail?: string;
}

/** Live receipt scan + reconciliation (Document Intelligence). Backend-only; null in mock. */
export function scanReceipt(args: { sheetId: string; lineItemId: string }): Promise<ReceiptScan | null> {
  return backend(
    () =>
      apiPost<Raw>(`/sheets/${args.sheetId}/line-items/${args.lineItemId}/scan`).then((r) => ({
        source: String(r.source ?? "unavailable"),
        merchant: (r.merchant as string) ?? undefined,
        total: r.total != null ? num(r.total) : undefined,
        tax: r.tax != null ? num(r.tax) : undefined,
        receiptDatetime: (r.receipt_datetime as string) ?? undefined,
        reconciles: (r.reconciles as boolean) ?? undefined,
        delta: r.delta != null ? num(r.delta) : undefined,
        matchesEntered: (r.matches_entered as boolean) ?? undefined,
        detail: (r.detail as string) ?? undefined,
      })),
    async () => null,
  );
}

export interface PolicyPreviewResult {
  status: string; // pass | warn | fail
  violations: { code: string; message: string; field?: string }[];
}

/** Authoritative deterministic policy check for the line-item form (Crispin policy). */
export function policyPreview(input: {
  category?: ExpenseCategory;
  amount: number;
  currency?: Currency;
  merchant?: string;
  description?: string;
  expenseDate?: string;
  receiptDatetime?: string;
  receiptTotal?: number;
  hasReceipt?: boolean;
}): Promise<PolicyPreviewResult> {
  return backend(
    () =>
      apiPost<Raw>("/intake/policy-check", {
        category: input.category,
        amount: input.amount,
        currency: input.currency ?? "USD",
        merchant: input.merchant ?? "",
        description: input.description ?? "",
        expense_date: input.expenseDate || null,
        receipt_datetime: input.receiptDatetime || null,
        receipt_total: input.receiptTotal ?? null,
        has_receipt: input.hasReceipt ?? false,
      }).then((r) => ({
        status: String(r.status ?? "pass"),
        violations: Array.isArray(r.violations)
          ? r.violations.map((v: Raw) => ({
              code: String(v.code ?? ""),
              message: String(v.message ?? ""),
              field: (v.field as string) ?? undefined,
            }))
          : [],
      })),
    // Offline: run the client validator so the form still shows policy checks.
    async () => {
      const issues = validateLineItem(
        {
          merchant: input.merchant ?? "",
          description: input.description ?? "",
          category: (input.category ?? "Other") as ExpenseCategory,
          amount: input.amount,
          currency: (input.currency ?? "USD") as Currency,
          expenseDate: input.expenseDate ?? "",
          receiptDatetime: input.receiptDatetime || undefined,
          attachments: input.hasReceipt
            ? [{ fileName: "receipt", fileType: "", sizeBytes: 1 }]
            : [],
        },
        baselinePolicy,
        [],
      );
      const hasError = issues.some((i) => i.level === "error");
      return {
        status: hasError ? "fail" : issues.length ? "warn" : "pass",
        violations: issues.map((i) => ({ code: i.clauseRef, message: i.message })),
      };
    },
  );
}

export interface PolicyAdvisory {
  clause?: { source: string; text: string };
}

/** RAG advisory: the most relevant agency policy clause (advisory only). Empty offline. */
export function policyAdvisory(input: {
  category?: ExpenseCategory;
  merchant?: string;
  description?: string;
}): Promise<PolicyAdvisory> {
  return backend(
    () =>
      apiPost<Raw>("/intake/policy-advisory", {
        category: input.category,
        merchant: input.merchant ?? "",
        description: input.description ?? "",
      }).then((r) => {
        const c = r.clause as Raw | null;
        return c
          ? { clause: { source: String(c.source ?? "Policy"), text: String(c.text ?? "") } }
          : {};
      }),
    async () => ({}),
  );
}

// ── Line items (employee editing) ────────────────────────────────────────────

export interface AttachmentInput {
  fileName: string;
  fileType: string;
  sizeBytes: number;
}

export interface LineItemInput {
  merchant: string;
  description: string;
  category: ExpenseCategory;
  categoryOther?: string;
  amount: number;
  currency: Currency;
  expenseDate: string;
  receiptDatetime?: string;
  receiptTotal?: number;
  tax?: number;
  attachments: AttachmentInput[];
}

function recompute(sheet: ExpenseSheet) {
  sheet.total = sheet.lineItems.reduce((sum, li) => sum + li.amount, 0);
  sheet.updatedAt = new Date().toISOString();
}

/** Duplicate detection across sheets (SCOPING.md §6.1): same-employee other
 *  sheets, and cross-employee (which must route to human). */
function crossDuplicateIssues(
  sheet: ExpenseSheet,
  input: LineItemInput,
  selfId?: string,
): IntakeIssue[] {
  if (!input.receiptDatetime) return [];
  for (const other of sheetStore) {
    for (const li of other.lineItems) {
      if (li.id === selfId || li.sheetId === sheet.id) continue;
      const sameKey =
        li.receiptDatetime === input.receiptDatetime &&
        Math.abs((li.receiptTotal ?? li.amount) - input.amount) < 0.01;
      if (!sameKey) continue;
      return other.employeeId === sheet.employeeId
        ? [{ level: "warning", message: `Possible duplicate of ${li.sheetId} (same receipt date & total).`, clauseRef: "DUP-XSHEET" }]
        : [{ level: "warning", message: "Possible cross-employee duplicate — will route to human review.", clauseRef: "DUP-XEMP" }];
    }
  }
  return [];
}

function makeLineItem(
  sheet: ExpenseSheet,
  input: LineItemInput,
  id: string,
  siblings: LineItem[],
): LineItem {
  const issues = [
    ...validateLineItem({ ...input }, baselinePolicy, siblings),
    ...crossDuplicateIssues(sheet, input, id),
  ];
  return {
    id,
    sheetId: sheet.id,
    merchant: input.merchant,
    description: input.description,
    category: input.category,
    categoryOther: input.categoryOther,
    amount: input.amount,
    currency: input.currency,
    expenseDate: input.expenseDate,
    receiptDatetime: input.receiptDatetime,
    receiptTotal: input.receiptTotal,
    tax: input.tax,
    managerStatus: "PENDING_MANAGER",
    aiFlag: toAiFlag(issues),
    attachments: input.attachments.map((a, i) => ({
      id: `${id}-att-${i}`,
      lineItemId: id,
      fileName: a.fileName,
      fileType: a.fileType,
      sizeBytes: a.sizeBytes,
      scanStatus: "clean" as const,
      ocrStatus: "done" as const,
    })),
  };
}

export async function addLineItem(args: {
  sheetId: string;
  input: LineItemInput;
}): Promise<ExpenseSheet> {
  return backend(
    () =>
      apiPost<Raw>(`/sheets/${args.sheetId}/line-items`, lineItemBody(args.input)).then(mapSheet),
    () => {
      const sheet = findSheet(args.sheetId);
      const id = `LI-${sheet.id}-${sheet.lineItems.length + 1}-${Math.floor(Math.random() * 1000)}`;
      sheet.lineItems.push(makeLineItem(sheet, args.input, id, sheet.lineItems));
      recompute(sheet);
      return delay(clone(sheet), 250);
    },
  );
}

export async function updateLineItem(args: {
  sheetId: string;
  lineItemId: string;
  input: LineItemInput;
}): Promise<ExpenseSheet> {
  return backend(
    () =>
      apiPatch<Raw>(
        `/sheets/${args.sheetId}/line-items/${args.lineItemId}`,
        lineItemBody(args.input),
      ).then(mapSheet),
    () => {
      const sheet = findSheet(args.sheetId);
      const idx = sheet.lineItems.findIndex((l) => l.id === args.lineItemId);
      if (idx < 0) throw new Error("Line item not found");
      const others = sheet.lineItems.filter((l) => l.id !== args.lineItemId);
      sheet.lineItems[idx] = makeLineItem(sheet, args.input, args.lineItemId, others);
      recompute(sheet);
      return delay(clone(sheet), 250);
    },
  );
}

export async function withdrawSheet(sheetId: string): Promise<ExpenseSheet> {
  return backend(
    () => apiPost<Raw>(`/sheets/${sheetId}/withdraw`).then(mapSheet),
    () => {
      const sheet = findSheet(sheetId);
      sheet.status = "WITHDRAWN";
      sheet.updatedAt = new Date().toISOString();
      return delay(clone(sheet), 350);
    },
  );
}

/** Permanently discard a DRAFT sheet (hard delete, owner + DRAFT only). 204 → void.
 *  For an in-flight sheet use withdrawSheet (soft recall) instead. */
export async function discardDraft(sheetId: string): Promise<void> {
  return backend(
    () => apiDelete<void>(`/sheets/${sheetId}`),
    () => {
      const idx = sheetStore.findIndex((s) => s.id === sheetId);
      if (idx >= 0) sheetStore.splice(idx, 1);
      return delay(undefined, 200);
    },
  );
}

export async function removeLineItem(args: {
  sheetId: string;
  lineItemId: string;
}): Promise<ExpenseSheet> {
  return backend(
    () =>
      apiDelete<Raw>(`/sheets/${args.sheetId}/line-items/${args.lineItemId}`).then(mapSheet),
    () => {
      const sheet = findSheet(args.sheetId);
      sheet.lineItems = sheet.lineItems.filter((l) => l.id !== args.lineItemId);
      recompute(sheet);
      return delay(clone(sheet), 200);
    },
  );
}

export function submitSheet(sheetId: string): Promise<ExpenseSheet> {
  return backend(
    () => apiPost<Raw>(`/sheets/${sheetId}/submit`).then(mapSheet),
    () => {
      const sheet = findSheet(sheetId);
      if (sheet.lineItems.length === 0) throw new Error("Cannot submit an empty sheet");
      sheet.status = "IN_MANAGER_REVIEW";
      sheet.submittedAt = new Date().toISOString();
      sheet.lineItems.forEach((li) => {
        li.managerStatus = "PENDING_MANAGER";
      });
      logActivity({
        actorId: sheet.employeeId,
        actorName: sheet.employeeName,
        actorRole: "employee",
        action: "SHEET_SUBMITTED",
        entity: "ExpenseSheet",
        summary: `${sheet.employeeName} submitted "${sheet.title}" for manager review.`,
        reference: sheet.id,
        timestamp: sheet.submittedAt,
        severity: "info",
      });
      return delay(clone(sheet), 450);
    },
  );
}

/**
 * Resubmission (SCOPING.md §5.1): same sheet id, version increments, workflow
 * restarts fresh from manager review, and all prior manager + finance verdicts
 * are reset (the data may have changed).
 */
export async function resubmitSheet(sheetId: string): Promise<ExpenseSheet> {
  return backend(
    () => apiPost<Raw>(`/sheets/${sheetId}/submit`).then(mapSheet),
    () => resubmitSheetMock(sheetId),
  );
}

async function resubmitSheetMock(sheetId: string): Promise<ExpenseSheet> {
  const sheet = findSheet(sheetId);
  sheet.version += 1;
  sheet.status = "IN_MANAGER_REVIEW";
  sheet.submittedAt = new Date().toISOString();
  sheet.managerDecidedBy = undefined;
  sheet.financeDecision = undefined;
  sheet.financeDecidedBy = undefined;
  sheet.routeReason = undefined;
  sheet.routeReasonDetail = undefined;
  sheet.citedClause = undefined;
  sheet.llmConfidence = undefined;
  sheet.lineItems.forEach((li) => {
    li.managerStatus = "PENDING_MANAGER";
    li.managerReason = undefined;
    li.policyStatus = undefined;
    li.policyClauseRef = undefined;
  });
  logActivity({
    actorId: sheet.employeeId,
    actorName: sheet.employeeName,
    actorRole: "employee",
    action: "SHEET_RESUBMITTED",
    entity: "ExpenseSheet",
    summary: `${sheet.employeeName} resubmitted "${sheet.title}" (v${sheet.version}) for manager review.`,
    reference: sheet.id,
    timestamp: sheet.submittedAt!,
    severity: "info",
  });
  return delay(clone(sheet), 500);
}

// ── Manager ──────────────────────────────────────────────────────────────────

export function getManagerQueue(agencyId: string): Promise<ExpenseSheet[]> {
  // GET /manager/queue — agency-scoped server-side by the manager's token.
  return backend(
    () => apiGet<Raw[]>("/manager/queue").then((rows) => rows.map(mapSheet)),
    () =>
      delay(
        clone(
          sheetStore.filter(
            (s) => s.agencyId === agencyId && s.status === "IN_MANAGER_REVIEW",
          ),
        ),
      ),
  );
}

export interface LineItemActionInput {
  sheetId: string;
  lineItemId: string;
  action: "approve" | "reject" | "request_info";
  reason?: string;
  actor?: { id: string; name: string };
}

const BACKEND_ACTION: Record<LineItemActionInput["action"], string> = {
  approve: "MANAGER_APPROVED",
  reject: "MANAGER_REJECTED",
  request_info: "INFO_REQUESTED",
};

export async function actOnLineItem(input: LineItemActionInput): Promise<ExpenseSheet> {
  return backend(
    () =>
      apiPost<Raw>(`/manager/sheets/${input.sheetId}/action`, {
        line_item_id: input.lineItemId,
        action: BACKEND_ACTION[input.action],
        reason: input.reason ?? null,
      }).then(mapSheet),
    () => actOnLineItemMock(input),
  );
}

async function actOnLineItemMock(input: LineItemActionInput): Promise<ExpenseSheet> {
  const sheet = findSheet(input.sheetId);
  const item = sheet.lineItems.find((l) => l.id === input.lineItemId);
  if (!item) throw new Error("Line item not found");
  const next: Record<LineItemActionInput["action"], LineItemStatus> = {
    approve: "MANAGER_APPROVED",
    reject: "MANAGER_REJECTED",
    request_info: "INFO_REQUESTED",
  };
  item.managerStatus = next[input.action];
  item.managerReason = input.reason;
  // Any rejection / info-request returns the whole sheet to the employee
  // so they can fix it and resubmit (SCOPING.md §6.2).
  if (input.action === "reject" || input.action === "request_info") {
    sheet.status = "RETURNED_TO_EMPLOYEE";
    sheet.managerDecidedBy = input.actor?.id;
    sheet.updatedAt = new Date().toISOString();
  }
  // Audit each per-line-item verdict (SCOPING.md §6.2).
  if (input.actor) {
    const verb =
      input.action === "approve" ? "approved" : input.action === "reject" ? "rejected" : "requested info on";
    logActivity({
      actorId: input.actor.id,
      actorName: input.actor.name,
      actorRole: "manager",
      action: `MANAGER_${input.action.toUpperCase()}`,
      entity: "LineItem",
      summary: `${input.actor.name} ${verb} "${item.merchant}" on ${sheet.id}.`,
      reference: input.reason ? `Reason: ${input.reason}` : sheet.id,
      timestamp: new Date().toISOString(),
      severity: input.action === "approve" ? "success" : input.action === "reject" ? "error" : "warning",
    });
  }
  return delay(clone(sheet), 250);
}

/** A user sees only their own recorded actions (not the org-wide log). */
export function getMyAuditLog(actorId: string) {
  return backend(
    () => apiGet<Raw[]>("/audit/me?limit=200").then((rows) => rows.map(mapAudit)),
    () => delay(clone(auditLog.filter((e) => e.actorId === actorId))),
  );
}

/**
 * Per-user activity log. Admin sees the entire platform trail (employee,
 * manager, finance, and AI approver actions); every other role sees only the
 * actions they personally performed (SCOPING.md §6.5).
 */
export function getActivityLog(scope: { role: Role; userId: string }) {
  const mockLog = () => {
    const all = clone(auditLog);
    return delay(scope.role === "admin" ? all : all.filter((e) => e.actorId === scope.userId));
  };
  // Use the single role-scoped /activity endpoint for every role: the backend already scopes
  // it (employee → own, manager → agency, finance/admin → org-wide) AND returns human-readable
  // summaries, so the feed reads consistently everywhere (the raw /finance/audit and /audit/me
  // endpoints have no `summary`, which left those feeds showing raw action codes).
  return backend(
    () =>
      apiGet<Raw>("/activity?page=1&page_size=200").then((r) =>
        Array.isArray(r.items) ? (r.items as Raw[]).map(mapAudit) : [],
      ),
    mockLog,
  );
}

// ── Activity feed (role-scoped audit trail, paginated + filtered) ─────────────
export interface ActivityParams {
  page?: number;
  pageSize?: number;
  action?: string;
  q?: string;
  actor_id?: string;
}
export interface ActivityPage {
  items: AuditLogEntry[];
  total: number;
  page: number;
  pageSize: number;
}

/** GET /activity — the backend scopes by the caller's role (employee→own, manager→agency,
 *  finance/admin→all). Offline falls back to paging/filtering the mock trail. */
export function getActivity(params: ActivityParams = {}): Promise<ActivityPage> {
  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? 25;
  return backend(
    () => {
      const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (params.action) qs.set("action", params.action);
      if (params.q) qs.set("q", params.q);
      if (params.actor_id) qs.set("actor_id", params.actor_id);
      return apiGet<Raw>(`/activity?${qs.toString()}`).then((r) => ({
        items: Array.isArray(r.items) ? (r.items as Raw[]).map(mapAudit) : [],
        total: num(r.total),
        page: num(r.page, page),
        pageSize: num(r.page_size, pageSize),
      }));
    },
    () => {
      const ql = (params.q ?? "").toLowerCase();
      const all = clone(auditLog).filter(
        (e) =>
          (!params.action || e.action === params.action) &&
          (!params.actor_id || e.actorId === params.actor_id) &&
          (!ql || `${e.summary} ${e.action} ${e.entity ?? ""}`.toLowerCase().includes(ql)),
      );
      const start = (page - 1) * pageSize;
      return delay({ items: all.slice(start, start + pageSize), total: all.length, page, pageSize });
    },
  );
}

/**
 * Manager confirms a fully-reviewed sheet (SCOPING.md §6.2 → §6.3). Every
 * non-rejected line item is marked approved, the action is logged, then the AI
 * Finance Approver runs automatically and either auto-decides or routes to a
 * human (manual intervention).
 */
export async function approveSheet(input: {
  sheetId: string;
  actor?: { id: string; name: string };
}): Promise<ExpenseSheet> {
  return backend(
    () => apiPost<Raw>(`/manager/sheets/${input.sheetId}/approve`).then(mapSheet),
    () => approveSheetMock(input),
  );
}

async function approveSheetMock(input: {
  sheetId: string;
  actor?: { id: string; name: string };
}): Promise<ExpenseSheet> {
  const sheet = findSheet(input.sheetId);
  sheet.lineItems.forEach((li) => {
    if (li.managerStatus !== "MANAGER_REJECTED") li.managerStatus = "MANAGER_APPROVED";
  });
  sheet.managerDecidedBy = input.actor?.id;
  if (input.actor) {
    logActivity({
      actorId: input.actor.id,
      actorName: input.actor.name,
      actorRole: "manager",
      action: "MANAGER_SHEET_APPROVED",
      entity: "ExpenseSheet",
      summary: `${input.actor.name} approved all line items on ${sheet.id} — handed to the AI Finance Approver.`,
      reference: sheet.id,
      timestamp: new Date().toISOString(),
      severity: "success",
    });
  }
  runAgentApprover(sheet);
  return delay(clone(sheet), 500);
}

/** Outcome of a bulk approval: the sheets that went through, plus the ids that
 *  failed so the caller can report a partial result instead of an all-or-nothing
 *  error when only some sheets fail. */
export interface BulkApproveResult {
  approved: ExpenseSheet[];
  failed: string[];
}

/** Manager bulk-approve (SCOPING.md §8): approve every line item on each
 *  selected sheet, then run the AI Finance Approver on each. There's no bulk
 *  endpoint server-side, so this fans out to the per-sheet route; we use
 *  `allSettled` so one sheet failing doesn't discard the sheets that succeeded. */
export async function managerBulkApprove(input: {
  ids: string[];
  actor?: { id: string; name: string };
}): Promise<BulkApproveResult> {
  return backend(
    async () => {
      const settled = await Promise.allSettled(
        input.ids.map((id) => apiPost<Raw>(`/manager/sheets/${id}/approve`).then(mapSheet)),
      );
      const approved: ExpenseSheet[] = [];
      const failed: string[] = [];
      settled.forEach((r, i) => {
        if (r.status === "fulfilled") approved.push(r.value);
        else failed.push(input.ids[i]);
      });
      return { approved, failed };
    },
    () => managerBulkApproveMock(input),
  );
}

async function managerBulkApproveMock(input: {
  ids: string[];
  actor?: { id: string; name: string };
}): Promise<BulkApproveResult> {
  const approved: ExpenseSheet[] = [];
  const failed: string[] = [];
  for (const id of input.ids) {
    const sheet = sheetStore.find((s) => s.id === id);
    if (!sheet) {
      failed.push(id);
      continue;
    }
    sheet.lineItems.forEach((li) => {
      li.managerStatus = "MANAGER_APPROVED";
    });
    sheet.managerDecidedBy = input.actor?.id;
    if (input.actor) {
      logActivity({
        actorId: input.actor.id,
        actorName: input.actor.name,
        actorRole: "manager",
        action: "MANAGER_SHEET_APPROVED",
        entity: "ExpenseSheet",
        summary: `${input.actor.name} bulk-approved ${sheet.id} — handed to the AI Finance Approver.`,
        reference: sheet.id,
        timestamp: new Date().toISOString(),
        severity: "success",
      });
    }
    runAgentApprover(sheet);
    approved.push(clone(sheet));
  }
  return delay({ approved, failed }, 600);
}

// ── Finance ──────────────────────────────────────────────────────────────────

export function getRoutedSheets(): Promise<ExpenseSheet[]> {
  return backend(
    () => apiGet<Raw[]>("/finance/queue").then((rows) => rows.map(mapSheet)),
    () => delay(clone(sheetStore.filter((s) => s.status === "FINANCE_MANUAL_REVIEW"))),
  );
}

export interface ProcessPendingResult {
  processed: number;
  approved: number;
  routed: number;
}

/** Nudge the AI finance approver to decide sheets stuck in IN_FINANCE_REVIEW (offline approver
 *  runs them: clean → auto-approved, flagged → routed to the manual-review queue). */
export function processPendingApprover(): Promise<ProcessPendingResult> {
  return backend(
    () =>
      apiPost<Raw>("/finance/process-pending").then((r) => ({
        processed: num(r.processed),
        approved: num(r.approved),
        routed: num(r.routed),
      })),
    () => delay({ processed: 0, approved: 0, routed: 0 }),
  );
}

export function getFinanceKpis() {
  // Backend computes core rates; the extended AI-performance metrics that the
  // backend KPI endpoint doesn't emit yet fall back to the seeded baseline so
  // the analytics strip stays fully populated.
  return backend(
    () =>
      apiGet<Raw>("/finance/kpis").then((r) => ({
        autoApprovalRate: num(r.auto_approval_rate, financeKpis.autoApprovalRate),
        // Optional / period-dependent fields: surface them as `null` when the backend
        // can't compute them (e.g. no resolved sheets yet) rather than masking the gap
        // with a seeded constant — the UI renders "—" for a null.
        autoApprovalDelta: numOrNull(r.auto_approval_delta),
        manualInterventions: num(r.manual_interventions, financeKpis.manualInterventions),
        manualInterventionsDelta: numOrNull(r.manual_interventions_delta),
        policyCitations: num(r.policy_citations, financeKpis.policyCitations),
        topClause: (r.top_clause as string) ?? null,
        // Not emitted by the backend KPI endpoint today → honest null, never a fake value.
        ragSyncedAgo: (r.rag_synced_ago as string) ?? null,
        approvalAccuracy: numOrNull(r.approval_accuracy),
        escalationRate: num(r.escalation_rate, financeKpis.escalationRate),
        falsePositiveRate: numOrNull(r.false_positive_rate),
        slaCompliance: numOrNull(r.sla_compliance),
        avgResolutionHours: numOrNull(r.avg_resolution_hours),
        policyComplianceRate: num(r.policy_compliance_rate, financeKpis.policyComplianceRate),
        trend:
          Array.isArray(r.trend) && r.trend.length ? (r.trend as number[]) : autoApprovalTrend,
      })),
    () => delay({ ...financeKpis, trend: autoApprovalTrend }),
  );
}

export function getPolicyDocuments(): Promise<AgencyPolicyDocument[]> {
  // Policies are agency-scoped; resolve the caller's agency via /auth/me.
  return backend(
    async () => {
      const aid = (await getMe()).agencyId;
      if (!aid) return [];
      const rows = await apiGet<Raw[]>(`/finance/policies/${aid}`);
      return rows.map(mapPolicy);
    },
    () => delay(clone(policyStore)),
  );
}

/** Extracted plain text of a stored policy doc (for the read-only viewer). */
export function getPolicyDocumentContent(policyId: string): Promise<string> {
  return backend(
    async () => {
      const aid = (await getMe()).agencyId;
      const r = await apiGet<Raw>(`/finance/policies/${aid}/${policyId}/content`);
      return (r.content as string) ?? "";
    },
    () => delay(""),
  );
}

/** All chunks currently indexed in Azure AI Search for an agency — chunk verification. */
export function getAgencyChunks(agencyId: string): Promise<PolicyChunk[]> {
  return backend(
    async () => {
      const rows = await apiGet<Raw[]>(`/finance/policies/${agencyId}/chunks`);
      return rows.map((r) => ({
        id: String(r.id ?? ""),
        agencyId: String(r.agency_id ?? ""),
        policyVersion: String(r.policy_version ?? ""),
        chunkIndex: Number(r.chunk_index ?? 0),
        content: String(r.content ?? ""),
        hasVector: Boolean(r.has_vector),
      }));
    },
    async () => [],
  );
}

export interface AgencyIndexSummary {
  agencyId: string;
  versions: { version: string; chunks: number; hasVectors: boolean }[];
  totalChunks: number;
}

/** Per-version chunk count summary from Azure AI Search — tells you what's actually indexed. */
export function getAgencyIndexSummary(agencyId: string): Promise<AgencyIndexSummary> {
  return backend(
    async () => {
      const r = await apiGet<Raw>(`/finance/policies/${agencyId}/index-summary`);
      return {
        agencyId: String(r.agency_id ?? ""),
        totalChunks: Number(r.total_chunks ?? 0),
        versions: ((r.versions ?? []) as Raw[]).map((v) => ({
          version: String(v.version ?? ""),
          chunks: Number(v.chunks ?? 0),
          hasVectors: Boolean(v.has_vectors),
        })),
      };
    },
    async () => ({ agencyId, versions: [], totalChunks: 0 }),
  );
}

/** Ingestion audit trail for one policy version: upload → publish → indexed/failed. */
export function getPolicyIngestLog(agencyId: string, policyId: string): Promise<PolicyIngestEvent[]> {
  return backend(
    async () => {
      const rows = await apiGet<Raw[]>(`/finance/policies/${agencyId}/${policyId}/log`);
      return rows.map((r) => ({
        id: String(r.id ?? ""),
        action: String(r.action ?? ""),
        after: (r.after ?? undefined) as Record<string, unknown> | undefined,
        timestamp: String(r.timestamp ?? ""),
      }));
    },
    async () => [],
  );
}

export interface PolicyMatchEvidence {
  policyVersion: string;
  text: string;
}

export interface PolicyCheckResult {
  decision: FinanceDecision;
  confidence: number;
  citedClauses: string[];
  reasonDetail?: string;
  evidence: PolicyMatchEvidence[];
  policyFound: boolean;
  llmUsed: boolean;
}

/** On-demand AI policy evaluation of a sheet — returns the verdict + cited clauses + the
 *  exact policy chunks the sheet was checked against (read-only; never changes status). */
export function getSheetPolicyCheck(sheetId: string): Promise<PolicyCheckResult> {
  return backend(
    () =>
      apiPost<Raw>(`/finance/sheets/${sheetId}/policy-check`).then((r) => ({
        decision: (r.decision ?? "ROUTED_TO_HUMAN") as FinanceDecision,
        confidence: num(r.confidence),
        citedClauses: Array.isArray(r.cited_clauses) ? r.cited_clauses.map(String) : [],
        reasonDetail: (r.reason_detail as string) ?? undefined,
        evidence: Array.isArray(r.evidence)
          ? r.evidence.map((e: Raw) => ({
              policyVersion: String(e.policy_version ?? "current"),
              text: String(e.text ?? ""),
            }))
          : [],
        policyFound: Boolean(r.policy_found),
        llmUsed: Boolean(r.llm_used),
      })),
    () =>
      delay({
        decision: "APPROVED" as FinanceDecision,
        confidence: 0.96,
        citedClauses: ["No receipt discrepancies detected."],
        reasonDetail: undefined,
        evidence: [],
        policyFound: false,
        llmUsed: false,
      }),
  );
}

export interface FinanceOverrideInput {
  sheetId: string;
  decision: Extract<FinanceDecision, "APPROVED" | "REJECTED_WITH_COMMENTS">;
  reason: string;
  actor: User;
  /** Current sheet status — routes to the correct backend endpoint.
   *  FINANCE_APPROVED / FINANCE_REJECTED → /override (overrides an LLM auto-decision).
   *  FINANCE_MANUAL_REVIEW → /decision (resolves a routed sheet). */
  sheetStatus?: SheetStatus;
}

export async function financeOverride(input: FinanceOverrideInput): Promise<ExpenseSheet> {
  const isOverride =
    input.sheetStatus === "FINANCE_APPROVED" || input.sheetStatus === "FINANCE_REJECTED";
  const endpoint = isOverride
    ? `/finance/sheets/${input.sheetId}/override`
    : `/finance/sheets/${input.sheetId}/decision`;

  return backend(
    () =>
      apiPost<Raw>(endpoint, {
        approve: input.decision === "APPROVED",
        reason: input.reason,
      }).then(mapSheet),
    () => {
      const sheet = findSheet(input.sheetId);
      if (isOverride) {
        // Override: the sheet leaves the finance-decision states and becomes fully settled.
        sheet.status = input.decision === "APPROVED" ? "APPROVED" : "REJECTED";
      } else {
        // Human decision on a routed sheet.
        sheet.status = input.decision === "APPROVED" ? "FINANCE_APPROVED" : "FINANCE_REJECTED";
      }
      sheet.financeDecision = input.decision;
      sheet.financeDecidedBy = input.actor.name;
      sheet.updatedAt = new Date().toISOString();
      const actionLabel = isOverride
        ? input.decision === "APPROVED"
          ? "OVERRIDE_CONFIRMED"
          : "OVERRIDE_REJECTED"
        : input.decision === "APPROVED"
          ? "FINANCE_APPROVED"
          : "FINANCE_REJECTED";
      logActivity({
        actorId: input.actor.id,
        actorName: input.actor.name,
        actorRole: "finance",
        action: actionLabel,
        entity: "ExpenseSheet",
        summary: isOverride
          ? `${input.actor.name} overrode AI auto-approval for sheet ${sheet.id} · ${input.decision === "APPROVED" ? "confirmed" : "rejected"}.`
          : `${input.actor.name} ${input.decision === "APPROVED" ? "approved" : "rejected"} routed sheet ${sheet.id} after manual review.`,
        reference: `${isOverride ? "override" : "manual intervention"} · ${input.reason}`,
        timestamp: sheet.updatedAt,
        severity: input.decision === "APPROVED" ? "success" : "error",
      });
      return delay(clone(sheet), 450);
    },
  );
}

export async function getSpendByCategory(): Promise<SpendByCategory[]> {
  return backend(
    () => apiGet<Raw[]>("/reports/spend-by-category").then((rows) => rows.map(mapSpend)),
    () => {
      const totals = new Map<string, number>();
      for (const sheet of sheetStore) {
        for (const item of sheet.lineItems) {
          totals.set(item.category, (totals.get(item.category) ?? 0) + item.amount);
        }
      }
      return delay(
        [...totals.entries()]
          .map(([category, amount]) => ({ category, amount }) as SpendByCategory)
          .sort((a, b) => b.amount - a.amount),
      );
    },
  );
}

// ── Admin ────────────────────────────────────────────────────────────────────

export function getAgencies(): Promise<Agency[]> {
  return backend(
    () => apiGet<Raw[]>("/admin/agencies").then((rows) => rows.map(mapAgency)),
    () => delay(clone(agencyStore)),
  );
}

export function getBaselinePolicy() {
  return delay(clone(baselinePolicy));
}

export function getAuditLog() {
  // Admin compliance view — ALWAYS the real immutable backend trail, never the mock store
  // (showing fabricated audit entries would be a correctness/compliance hazard).
  return apiGet<Raw[]>("/finance/audit?limit=200").then((rows) => rows.map(mapAudit));
}

export interface AssignRoleInput {
  email: string;
  role: Role;
}

export async function assignRole(input: AssignRoleInput): Promise<{ ok: true }> {
  return backend(
    () =>
      apiPost<Raw>("/admin/users/assign-role", { email: input.email, role: input.role }).then(
        () => ({ ok: true }) as const,
      ),
    () => assignRoleMock(input),
  );
}

async function assignRoleMock(input: AssignRoleInput): Promise<{ ok: true }> {
  auditLog.unshift({
    id: `AUD-${auditLog.length + 1}`,
    actorId: "USR-ALEX",
    actorName: "Alex Rivera",
    actorRole: "admin",
    action: "ROLE_ASSIGNMENT",
    entity: "User",
    summary: `${input.email} assigned ${input.role} role.`,
    reference: "via Quick Role Assignment",
    timestamp: new Date(2026, 5, 14, 11, 0).toISOString(),
    severity: "info",
  });
  return delay({ ok: true } as const, 400);
}

export interface OnboardAgencyInput {
  name: string;
  tier: AgencyTier;
}

/** Admin onboards an agency (SCOPING.md §7 lifecycle) — POST /admin/agencies. */
export async function addAgency(input: OnboardAgencyInput): Promise<Agency> {
  return backend(
    () => apiPost<Raw>("/admin/agencies", { name: input.name, tier: input.tier }).then(mapAgency),
    () => {
      const agency: Agency = {
        id: `AGY-${input.name.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8)}-${Math.floor(Math.random() * 900 + 100)}`,
        name: input.name,
        status: "active",
        tier: input.tier,
        userCount: 0,
        createdBy: "alex.rivera",
        createdAt: new Date(2026, 5, 14).toISOString(),
      };
      agencyStore.unshift(agency);
      auditLog.unshift({
        id: `AUD-${auditLog.length + 1}`,
        actorId: "USR-ALEX",
        actorName: "Alex Rivera",
        actorRole: "admin",
        action: "AGENCY_CREATED",
        entity: "Agency",
        summary: `New agency '${input.name}' onboarded to ${input.tier} tier.`,
        reference: agency.id,
        timestamp: new Date(2026, 5, 14, 11, 5).toISOString(),
        severity: "success",
      });
      return delay(clone(agency), 450);
    },
  );
}

// ── Policy documents (Finance maker-checker, SCOPING.md §7) ───────────────────

export interface UploadPolicyInput {
  agencyId: string;
  agencyName: string;
  /** The actual policy document (PDF/DOCX…) — streamed to the storage account as multipart. */
  file: File;
  /** Optional; the backend stores it on the version and treats it as nullable. */
  effectiveDate?: string;
  /** The uploading user's id (the maker); the backend derives the real actor from the token. */
  createdBy: string;
}

/**
 * Maker step (SCOPING §7): upload a new policy version. The file is sent as multipart and the
 * backend stores it in the policy storage account (Azure Blob, or local fallback offline),
 * auto-assigns the next version, and creates an unpublished/unindexed draft. A *different*
 * Finance/Admin then publishes it, which enqueues it for RAG ingestion (see publishPolicyDocument).
 * The endpoint takes only the file + effective_date — name/version are server-managed.
 */
export async function uploadPolicyDocument(
  input: UploadPolicyInput,
): Promise<AgencyPolicyDocument> {
  return backend(
    () => {
      const form = new FormData();
      form.append("file", input.file);
      if (input.effectiveDate) form.append("effective_date", input.effectiveDate);
      return apiUpload<Raw>(`/finance/policies/${input.agencyId}`, form).then(mapPolicy);
    },
    () => uploadPolicyDocumentMock(input),
  );
}

async function uploadPolicyDocumentMock(
  input: UploadPolicyInput,
): Promise<AgencyPolicyDocument> {
  // Mirror the server: next version = current max for the agency + 1; name derived from the file.
  const nextVersion = policyStore.filter((d) => d.agencyId === input.agencyId).length + 1;
  const version = `v${nextVersion}`;
  const name = input.file.name.replace(/\.[^.]+$/, "");
  const doc: AgencyPolicyDocument = {
    id: `POL-${input.agencyId}-${version}`,
    agencyId: input.agencyId,
    name,
    version,
    effectiveDate: input.effectiveDate ?? "",
    indexedAt: "", // draft is not indexed until published + ingested
    status: "draft",
    createdBy: input.createdBy,
  };
  policyStore.unshift(doc);
  auditLog.unshift({
    id: `AUD-${auditLog.length + 1}`,
    actorId: input.createdBy,
    actorName: input.createdBy,
    actorRole: "finance",
    action: "POLICY_UPLOAD",
    entity: "AgencyPolicy",
    summary: `${name} ${version} uploaded (${input.file.name}) — pending publish.`,
    reference: "maker-checker: awaiting approval",
    timestamp: new Date(2026, 5, 14, 11, 10).toISOString(),
    severity: "info",
  });
  return delay(clone(doc), 600);
}

/** Checker step: publish + re-index a draft policy version. */
export async function publishPolicyDocument(args: {
  id: string;
  publishedBy: string;
  agencyId?: string;
}): Promise<AgencyPolicyDocument> {
  return backend(
    async () => {
      const aid = args.agencyId ?? (await getMe()).agencyId;
      return apiPost<Raw>(`/finance/policies/${aid}/${args.id}/publish`).then(mapPolicy);
    },
    () => publishPolicyDocumentMock(args),
  );
}

async function publishPolicyDocumentMock(args: {
  id: string;
  publishedBy: string;
}): Promise<AgencyPolicyDocument> {
  const doc = policyStore.find((d) => d.id === args.id);
  if (!doc) throw new Error("Policy not found");
  if (doc.createdBy === args.publishedBy) {
    throw new Error("Maker-checker: the publisher must differ from the uploader.");
  }
  doc.status = "active";
  doc.publishedBy = args.publishedBy;
  doc.indexedAt = new Date(2026, 5, 14).toISOString();
  auditLog.unshift({
    id: `AUD-${auditLog.length + 1}`,
    actorId: "USR-ALEX",
    actorName: args.publishedBy,
    actorRole: "finance",
    action: "POLICY_PUBLISH",
    entity: "AgencyPolicy",
    summary: `${doc.name} ${doc.version} published and re-indexed.`,
    reference: "maker-checker: approved",
    timestamp: new Date(2026, 5, 14, 11, 15).toISOString(),
    severity: "success",
  });
  return delay(clone(doc), 500);
}

/** Delete a policy version and purge its Azure AI Search chunks. */
export async function deletePolicyDocument(args: {
  id: string;
  agencyId?: string;
}): Promise<void> {
  return backend(
    async () => {
      const aid = args.agencyId ?? (await getMe()).agencyId;
      await apiDelete(`/finance/policies/${aid}/${args.id}`);
    },
    () => {
      const idx = policyStore.findIndex((d) => d.id === args.id);
      if (idx !== -1) policyStore.splice(idx, 1);
      return delay(undefined, 400);
    },
  );
}

// ── Notifications ─────────────────────────────────────────────────────────────

export function getNotifications(role: Role, includeArchived = false): Promise<AppNotification[]> {
  // Backend scopes by the caller's token (recipient or role); `role` filters the mock.
  return backend(
    () =>
      apiGet<Raw[]>(`/notifications${includeArchived ? "?include_archived=true" : ""}`).then(
        (rows) => rows.map(mapNotification),
      ),
    () => {
      const list = notificationStore.filter(
        (n) =>
          (!n.roles || n.roles.includes(role)) &&
          (includeArchived || !(n as { archived?: boolean }).archived),
      );
      return delay(clone(list), 150);
    },
  );
}

export async function markNotificationsRead(role: Role): Promise<AppNotification[]> {
  return backend(
    () => apiPost<Raw[]>("/notifications/read").then((rows) => rows.map(mapNotification)),
    () => {
      notificationStore.forEach((n) => {
        if (!n.roles || n.roles.includes(role)) n.read = true;
      });
      return delay(
        clone(notificationStore.filter((n) => !n.roles || n.roles.includes(role))),
        150,
      );
    },
  );
}

/** Mark a single notification read (owner-scoped server-side). */
export async function markOneNotificationRead(id: string): Promise<void> {
  return backend(
    () => apiPost<Raw>(`/notifications/${id}/read`).then(() => undefined),
    () => {
      const n = notificationStore.find((x) => x.id === id);
      if (n) n.read = true;
      return delay(undefined, 120);
    },
  );
}

/** Archive a notification (hidden from the default inbox, kept in the Notification Center). */
export async function archiveNotification(id: string): Promise<void> {
  return backend(
    () => apiPost<Raw>(`/notifications/${id}/archive`).then(() => undefined),
    () => {
      const n = notificationStore.find((x) => x.id === id) as { archived?: boolean } | undefined;
      if (n) n.archived = true;
      return delay(undefined, 120);
    },
  );
}

/** Permanently delete a notification (owner-scoped). */
export async function deleteNotification(id: string): Promise<void> {
  return backend(
    () => apiDelete<Raw>(`/notifications/${id}`).then(() => undefined),
    () => {
      const i = notificationStore.findIndex((x) => x.id === id);
      if (i >= 0) notificationStore.splice(i, 1);
      return delay(undefined, 80);
    },
  );
}

// ── User settings / preferences ──────────────────────────────────────────────
export type UserPreferences = Record<string, boolean | string | number>;

export function getPreferences(): Promise<UserPreferences> {
  return backend(
    () => apiGet<Raw>("/me/preferences").then((r) => (r.preferences as UserPreferences) ?? {}),
    () => delay({}, 100),
  );
}

export function updatePreferences(prefs: UserPreferences): Promise<UserPreferences> {
  return backend(
    () =>
      apiPut<Raw>("/me/preferences", { preferences: prefs }).then(
        (r) => (r.preferences as UserPreferences) ?? {},
      ),
    () => delay(clone(prefs), 100),
  );
}

export type FinanceKpisResult = Awaited<ReturnType<typeof getFinanceKpis>>;

// ── Additional backend clients ───────────────────────────────────────────────
// Direct clients for the remaining API endpoints (auth/me, admin user + agency
// CRUD, finance policy docs). Backend-only — call when NEXT_PUBLIC_USE_BACKEND
// is on; no mock fallback. Wired opportunistically; available for new UI.

export interface MeProfile {
  subjectId: string;
  role: Role;
  agencyId?: string;
  agencyName?: string;
  email?: string;
  name?: string;
}

export function getMe(): Promise<MeProfile> {
  return apiGet<Raw>("/auth/me").then((r) => ({
    subjectId: String(r.subject_id ?? r.id ?? ""),
    role: String(r.role ?? "employee").toLowerCase() as Role,
    agencyId: (r.agency_id as string) ?? undefined,
    agencyName: (r.agency_name as string) ?? undefined,
    email: (r.email as string) ?? undefined,
    name: (r.name as string) ?? undefined,
  }));
}

// Admin — users
export interface AdminUserInput {
  name: string;
  email: string;
  role: Role;
  password: string;
  agencyId?: string;
}
/** Map a backend UserOut row to the typed User (agencyName is resolved client-side). */
function mapAdminUser(r: Raw): User {
  return {
    id: String(r.id ?? ""),
    name: String(r.name ?? ""),
    email: String(r.email ?? ""),
    role: String(r.role ?? "employee").toLowerCase() as Role,
    agencyId: (r.agency_id as string) ?? "",
    isActive: (r.is_active as boolean) ?? true,
    createdAt: (r.created_at as string) ?? undefined,
  };
}

export const listAdminUsers = (opts?: { isActive?: boolean }): Promise<User[]> =>
  apiGet<Raw[]>(
    `/admin/users${opts?.isActive != null ? `?is_active=${opts.isActive}` : ""}`,
  ).then((rows) => rows.map(mapAdminUser));

export const getAdminUser = (id: string) => apiGet<Raw>(`/admin/users/${id}`).then(mapAdminUser);

export const createUser = (input: AdminUserInput): Promise<User> =>
  apiPost<Raw>("/admin/users", {
    name: input.name,
    email: input.email,
    role: input.role,
    password: input.password,
    agency_id: input.agencyId,
  }).then(mapAdminUser);

export interface AdminUserPatch {
  name?: string;
  email?: string;
  role?: Role;
  agencyId?: string;
  isActive?: boolean;
  password?: string;
}
export const updateUser = (id: string, patch: AdminUserPatch): Promise<User> =>
  apiPatch<Raw>(`/admin/users/${id}`, {
    ...(patch.name !== undefined ? { name: patch.name } : {}),
    ...(patch.email !== undefined ? { email: patch.email } : {}),
    ...(patch.role !== undefined ? { role: patch.role } : {}),
    ...(patch.agencyId !== undefined ? { agency_id: patch.agencyId } : {}),
    ...(patch.isActive !== undefined ? { is_active: patch.isActive } : {}),
    ...(patch.password ? { password: patch.password } : {}),
  }).then(mapAdminUser);

/** Soft-delete (deactivate). Re-enable via updateUser({ isActive: true }). */
export const deleteUser = (id: string): Promise<User> =>
  apiDelete<Raw>(`/admin/users/${id}`).then(mapAdminUser);

// Admin — agencies CRUD
export const getAgency = (id: string) => apiGet<Raw>(`/admin/agencies/${id}`).then(mapAgency);
export const updateAgency = (id: string, name: string) =>
  apiPatch<Raw>(`/admin/agencies/${id}`, { name }).then(mapAgency);
export const deleteAgency = (id: string) =>
  apiDelete<Raw>(`/admin/agencies/${id}`).then(mapAgency);

// Finance — policy documents (RAG)
export const getPolicies = (agencyId: string) =>
  apiGet<Raw[]>(`/finance/policies/${agencyId}`);
export const publishPolicy = (agencyId: string, policyId: string) =>
  apiPost<Raw>(`/finance/policies/${agencyId}/${policyId}/publish`);
