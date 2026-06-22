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
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  apiUpload,
  backend,
} from "./http";
import {
  mapAgency,
  mapAudit,
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
  AuditLogEntry,
  Currency,
  EmployeeKpis,
  ExpenseCategory,
  ExpenseSheet,
  FinanceDecision,
  LineItem,
  LineItemStatus,
  Role,
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

/**
 * Runs the AI Finance Approver on a manager-approved sheet (SCOPING.md §6.3).
 * Clean sheets are auto-decided; anything carrying a policy flag or low
 * confidence is routed to a human finance approver (FINANCE_MANUAL_REVIEW).
 */
function runAgentApprover(sheet: ExpenseSheet): void {
  const flagged = sheet.lineItems.filter((li) => li.aiFlag);
  const hasError = flagged.some((li) => li.aiFlag?.severity === "error");
  const confidence = hasError ? 0.42 : flagged.length ? 0.61 : 0.96;
  const pct = `${Math.round(confidence * 100)}%`;
  sheet.policyVersionUsed = "Crispin Finance Rules v2.1";
  sheet.llmConfidence = confidence;
  sheet.updatedAt = new Date().toISOString();

  if (confidence < ROUTING_THRESHOLD) {
    const flag = flagged[0]?.aiFlag;
    sheet.status = "FINANCE_MANUAL_REVIEW";
    sheet.financeDecision = "ROUTED_TO_HUMAN";
    sheet.routeReason = hasError ? "AMBIGUOUS_CLAUSE" : "LOW_CONFIDENCE";
    sheet.routeReasonDetail = flag?.message ?? "Confidence below the routing threshold.";
    sheet.citedClause = flag
      ? { policyName: "Crispin Finance Rules v2.1", text: flag.message }
      : undefined;
    logActivity({
      actorId: AI_APPROVER.id,
      actorName: AI_APPROVER.name,
      actorRole: "llm_approver",
      action: "FINANCE_ROUTED",
      entity: "ExpenseSheet",
      summary: `${AI_APPROVER.name} routed ${sheet.id} to a human — ${sheet.routeReasonDetail}`,
      reference: `confidence ${pct} · policy v2.1`,
      timestamp: sheet.updatedAt,
      severity: "warning",
    });
  } else {
    sheet.status = "FINANCE_APPROVED";
    sheet.financeDecision = "APPROVED";
    sheet.financeDecidedBy = AI_APPROVER.name;
    logActivity({
      actorId: AI_APPROVER.id,
      actorName: AI_APPROVER.name,
      actorRole: "llm_approver",
      action: "FINANCE_AUTO_APPROVED",
      entity: "ExpenseSheet",
      summary: `${AI_APPROVER.name} auto-approved ${sheet.id} (${sheet.lineItems.length} line item${sheet.lineItems.length === 1 ? "" : "s"} cleared policy).`,
      reference: `confidence ${pct} · policy v2.1`,
      timestamp: sheet.updatedAt,
      severity: "success",
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
}): Promise<ExpenseSheet> {
  // PATCH /sheets/{id} — edit a draft's title/period (owner, DRAFT only).
  return backend(
    () =>
      apiPatch<Raw>(`/sheets/${args.sheetId}`, {
        title: args.title,
        period: args.period,
      }).then(mapSheet),
    () => {
      const sheet = findSheet(args.sheetId);
      if (args.title != null) sheet.title = args.title;
      if (args.period != null) sheet.period = args.period;
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
    () => apiPost<Raw>(`/sheets/${sheetId}/resubmit`).then(mapSheet),
    () => resubmitSheetMock(sheetId),
  );
}

async function resubmitSheetMock(sheetId: string): Promise<ExpenseSheet> {
  const sheet = findSheet(sheetId);
  sheet.version += 1;
  sheet.status = "IN_MANAGER_REVIEW";
  sheet.submittedAt = new Date().toISOString();
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
  // The backend audit endpoint is finance/admin-gated and already scopes the
  // result by the caller's token (admin = org-wide, finance = own). Employee /
  // manager have no such endpoint, so they keep the mock trail.
  return backend(
    () =>
      scope.role === "finance" || scope.role === "admin"
        ? apiGet<Raw[]>("/finance/audit?limit=200").then((rows) => rows.map(mapAudit))
        : apiGet<Raw[]>("/audit/me?limit=200").then((rows) => rows.map(mapAudit)),
    mockLog,
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

/** Manager bulk-approve (SCOPING.md §8): approve every line item on each
 *  selected sheet, then run the AI Finance Approver on each. */
export async function managerBulkApprove(input: {
  ids: string[];
  actor?: { id: string; name: string };
}): Promise<ExpenseSheet[]> {
  return backend(
    // No bulk endpoint server-side — approve each sheet via the per-sheet route.
    () =>
      Promise.all(
        input.ids.map((id) => apiPost<Raw>(`/manager/sheets/${id}/approve`).then(mapSheet)),
      ),
    () => managerBulkApproveMock(input),
  );
}

async function managerBulkApproveMock(input: {
  ids: string[];
  actor?: { id: string; name: string };
}): Promise<ExpenseSheet[]> {
  const updated: ExpenseSheet[] = [];
  for (const id of input.ids) {
    const sheet = sheetStore.find((s) => s.id === id);
    if (!sheet) continue;
    sheet.lineItems.forEach((li) => {
      li.managerStatus = "MANAGER_APPROVED";
    });
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
    updated.push(clone(sheet));
  }
  return delay(updated, 600);
}

// ── Finance ──────────────────────────────────────────────────────────────────

export function getRoutedSheets(): Promise<ExpenseSheet[]> {
  return backend(
    () => apiGet<Raw[]>("/finance/queue").then((rows) => rows.map(mapSheet)),
    () => delay(clone(sheetStore.filter((s) => s.status === "FINANCE_MANUAL_REVIEW"))),
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
        autoApprovalDelta: num(r.auto_approval_delta, financeKpis.autoApprovalDelta),
        manualInterventions: num(r.manual_interventions, financeKpis.manualInterventions),
        manualInterventionsDelta: num(
          r.manual_interventions_delta,
          financeKpis.manualInterventionsDelta,
        ),
        policyCitations: num(r.policy_citations, financeKpis.policyCitations),
        topClause: (r.top_clause as string) ?? financeKpis.topClause,
        ragSyncedAgo: (r.rag_synced_ago as string) ?? financeKpis.ragSyncedAgo,
        approvalAccuracy: num(r.approval_accuracy, financeKpis.approvalAccuracy),
        escalationRate: num(r.escalation_rate, financeKpis.escalationRate),
        falsePositiveRate: num(r.false_positive_rate, financeKpis.falsePositiveRate),
        slaCompliance: num(r.sla_compliance, financeKpis.slaCompliance),
        avgResolutionHours: num(r.avg_resolution_hours, financeKpis.avgResolutionHours),
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

export interface FinanceOverrideInput {
  sheetId: string;
  decision: Extract<FinanceDecision, "APPROVED" | "REJECTED_WITH_COMMENTS">;
  reason: string;
  actor: User;
}

export async function financeOverride(input: FinanceOverrideInput): Promise<ExpenseSheet> {
  // Human decision on a routed sheet: POST /finance/sheets/{id}/decision.
  return backend(
    () =>
      apiPost<Raw>(`/finance/sheets/${input.sheetId}/decision`, {
        approve: input.decision === "APPROVED",
        reason: input.reason,
      }).then(mapSheet),
    () => {
      const sheet = findSheet(input.sheetId);
      sheet.status = input.decision === "APPROVED" ? "FINANCE_APPROVED" : "FINANCE_REJECTED";
      sheet.financeDecision = input.decision;
      sheet.financeDecidedBy = input.actor.name;
      sheet.updatedAt = new Date().toISOString();
      logActivity({
        actorId: input.actor.id,
        actorName: input.actor.name,
        actorRole: "finance",
        action: input.decision === "APPROVED" ? "FINANCE_APPROVED" : "FINANCE_REJECTED",
        entity: "ExpenseSheet",
        summary: `${input.actor.name} ${input.decision === "APPROVED" ? "approved" : "rejected"} routed sheet ${sheet.id} after manual review.`,
        reference: `manual intervention · ${input.reason}`,
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
  return backend(
    () => apiGet<Raw[]>("/finance/audit?limit=200").then((rows) => rows.map(mapAudit)),
    () => delay(clone(auditLog)),
  );
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
  name: string;
  version: string;
  fileName: string;
  effectiveDate: string;
  createdBy: string;
}

/** Maker step: upload a new policy version → virus scan → extract → draft. */
export async function uploadPolicyDocument(
  input: UploadPolicyInput,
): Promise<AgencyPolicyDocument> {
  return backend(
    () =>
      apiPost<Raw>(`/finance/policies/${input.agencyId}`, {
        name: input.name,
        version: input.version,
        effective_date: input.effectiveDate,
      }).then(mapPolicy),
    () => uploadPolicyDocumentMock(input),
  );
}

async function uploadPolicyDocumentMock(
  input: UploadPolicyInput,
): Promise<AgencyPolicyDocument> {
  const doc: AgencyPolicyDocument = {
    id: `POL-${input.agencyId}-${input.version}`,
    agencyId: input.agencyId,
    name: input.name,
    version: input.version,
    effectiveDate: input.effectiveDate,
    indexedAt: new Date(2026, 5, 14).toISOString(),
    status: "draft",
    createdBy: input.createdBy,
  };
  policyStore.unshift(doc);
  auditLog.unshift({
    id: `AUD-${auditLog.length + 1}`,
    actorId: "USR-SARAH",
    actorName: "Sarah Okafor",
    actorRole: "finance",
    action: "POLICY_UPLOAD",
    entity: "AgencyPolicy",
    summary: `${input.name} ${input.version} uploaded (${input.fileName}) — pending publish.`,
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

// ── Notifications ─────────────────────────────────────────────────────────────

export function getNotifications(role: Role): Promise<AppNotification[]> {
  // Backend scopes by the caller's token (recipient or role); `role` filters the mock.
  return backend(
    () => apiGet<Raw[]>("/notifications").then((rows) => rows.map(mapNotification)),
    () => {
      const list = notificationStore.filter((n) => !n.roles || n.roles.includes(role));
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

export type FinanceKpisResult = Awaited<ReturnType<typeof getFinanceKpis>>;

// ── Additional backend clients ───────────────────────────────────────────────
// Direct clients for the remaining API endpoints (auth/me, admin user + agency
// CRUD, finance policy docs). Backend-only — call when NEXT_PUBLIC_USE_BACKEND
// is on; no mock fallback. Wired opportunistically; available for new UI.

export interface MeProfile {
  subjectId: string;
  role: Role;
  agencyId?: string;
  email?: string;
  name?: string;
}

export function getMe(): Promise<MeProfile> {
  return apiGet<Raw>("/auth/me").then((r) => ({
    subjectId: String(r.subject_id ?? r.id ?? ""),
    role: String(r.role ?? "employee").toLowerCase() as Role,
    agencyId: (r.agency_id as string) ?? undefined,
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
export const getUsers = (isActive?: boolean) =>
  apiGet<Raw[]>(`/admin/users${isActive != null ? `?is_active=${isActive}` : ""}`);
export const getAdminUser = (id: string) => apiGet<Raw>(`/admin/users/${id}`);
export const createUser = (input: AdminUserInput) =>
  apiPost<Raw>("/admin/users", {
    name: input.name,
    email: input.email,
    role: input.role,
    password: input.password,
    agency_id: input.agencyId,
  });
export const updateUser = (id: string, patch: Partial<{ role: Role; name: string }>) =>
  apiPatch<Raw>(`/admin/users/${id}`, patch);
export const deleteUser = (id: string) => apiDelete<Raw>(`/admin/users/${id}`);

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
