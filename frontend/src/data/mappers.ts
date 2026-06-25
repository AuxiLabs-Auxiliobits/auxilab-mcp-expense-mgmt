/**
 * Backend (FastAPI, snake_case) → frontend type mappers. Tolerant of optional /
 * differently-named fields so the UI degrades gracefully if a field is absent.
 */
import type {
  Agency,
  AgencyPolicyDocument,
  AgencyStatus,
  AppNotification,
  Attachment,
  AuditLogEntry,
  DecisionEntry,
  ExpenseSheet,
  LineItem,
  Role,
  SheetStatus,
  SpendByCategory,
  User,
} from "./types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Raw = Record<string, any>;

function num(v: unknown, fallback = 0): number {
  const n = typeof v === "string" ? parseFloat(v) : (v as number);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * Coerce a backend timestamp to an absolute (UTC) instant. The API stores UTC, but SQLite
 * round-trips drop the tz, so values arrive tz-naive ("2026-06-22T10:30:00"); the browser
 * would then read them as *local* time (e.g. ~5.5h off in IST → "updated 6 hours ago" for a
 * just-created sheet). Append "Z" when no tz designator is present.
 */
function asUtc(v: unknown): string | undefined {
  if (v == null || v === "") return undefined;
  const s = String(v);
  return /([zZ]|[+-]\d{2}:?\d{2})$/.test(s) ? s : `${s}Z`;
}

export function mapLineItem(r: Raw, sheetId = ""): LineItem {
  const amount = num(r.amount);
  return {
    id: String(r.id ?? ""),
    sheetId: String(r.sheet_id ?? sheetId),
    merchant: r.merchant ?? "",
    description: r.description ?? r.merchant ?? "",
    category: r.category ?? "Other",
    categoryOther: r.category_other ?? r.categoryOther ?? undefined,
    amount,
    currency: r.currency ?? "USD",
    expenseDate: r.expense_date ?? r.expenseDate ?? "",
    receiptDatetime: r.receipt_datetime ?? r.receiptDatetime ?? undefined,
    receiptTotal: r.receipt_total != null ? num(r.receipt_total) : undefined,
    tax: r.tax != null ? num(r.tax) : undefined,
    managerStatus: r.manager_status ?? r.managerStatus ?? "PENDING_MANAGER",
    managerReason: r.manager_reason ?? r.managerReason ?? undefined,
    policyStatus: r.policy_status ?? r.policyStatus ?? undefined,
    policyClauseRef: r.policy_clause_ref ?? r.policyClauseRef ?? undefined,
    needsHumanReview: Boolean(r.needs_human_review ?? r.needsHumanReview ?? false),
    reviewReason: r.review_reason ?? r.reviewReason ?? undefined,
    aiFlag: r.ai_flag ?? r.aiFlag ?? undefined,
    attachments: Array.isArray(r.attachments)
      ? r.attachments.map(
          (a: Raw): import("./types").Attachment => ({
            id: String(a.id ?? ""),
            lineItemId: String(a.line_item_id ?? r.id ?? ""),
            fileName: a.filename ?? a.file_name ?? a.fileName ?? "receipt",
            fileType: a.file_type ?? a.fileType ?? "application/octet-stream",
            sizeBytes: num(a.size ?? a.sizeBytes ?? 0),
            scanStatus: (a.scan_status ?? "clean") as import("./types").ScanStatus,
            ocrStatus: (a.ocr_status ?? "done") as import("./types").OcrStatus,
            downloadUrl: a.download_url ?? a.downloadUrl ?? undefined,
          }),
        )
      : r.has_receipt
        ? [
            {
              id: `${r.id}-receipt`,
              lineItemId: String(r.id ?? ""),
              fileName: "receipt",
              fileType: "application/octet-stream",
              sizeBytes: 0,
              scanStatus: "clean" as import("./types").ScanStatus,
              ocrStatus: "done" as import("./types").OcrStatus,
            },
          ]
        : [],
  };
}

export function mapSheet(r: Raw): ExpenseSheet {
  const lineItems = Array.isArray(r.line_items)
    ? r.line_items.map((li: Raw) => mapLineItem(li, String(r.id ?? "")))
    : [];
  const total =
    r.total != null ? num(r.total) : lineItems.reduce((s, li) => s + li.amount, 0);
  const cited = r.cited_clauses ?? r.citedClause;
  return {
    id: String(r.id ?? ""),
    title: r.title ?? r.period ?? "Expense Sheet",
    employeeId: String(r.employee_id ?? r.employeeId ?? ""),
    employeeName: r.employee_name ?? r.employeeName ?? "—",
    agencyId: String(r.agency_id ?? r.agencyId ?? ""),
    agencyName: r.agency_name ?? r.agencyName ?? "",
    version: num(r.version, 1),
    status: (r.status ?? "DRAFT") as SheetStatus,
    period: r.period ?? "",
    total,
    currency: lineItems[0]?.currency ?? r.currency ?? "USD",
    submittedAt: asUtc(r.submitted_at ?? r.submittedAt),
    updatedAt: asUtc(r.updated_at ?? r.updatedAt) ?? new Date().toISOString(),
    financeDecision: r.finance_decision ?? r.financeDecision ?? undefined,
    financeDecidedBy: r.finance_decided_by ?? undefined,
    policyVersionUsed: r.policy_version_used ?? r.policy_version ?? undefined,
    routeReason: r.route_reason ?? undefined,
    routeReasonDetail: r.route_reason_detail ?? r.uncertainty_reason ?? undefined,
    llmConfidence: r.confidence != null ? num(r.confidence) : undefined,
    citedClause:
      Array.isArray(cited) && cited.length
        ? { policyName: cited[0].source ?? "Policy", text: cited[0].text ?? String(cited[0]) }
        : undefined,
    lineItems,
  };
}

function mapAgencyStatus(s: unknown): AgencyStatus {
  const v = String(s ?? "active").toLowerCase();
  if (v.includes("soft") || v.includes("delete")) return "soft_deleted";
  if (v.includes("suspend")) return "suspended";
  return "active";
}

export function mapAgency(r: Raw): Agency {
  return {
    id: String(r.id ?? ""),
    name: r.name ?? "",
    status: mapAgencyStatus(r.status),
    tier: r.tier ?? "Pro",
    userCount: num(r.user_count ?? r.users, 0),
    createdBy: r.created_by ?? "",
    createdAt: r.created_at ?? new Date().toISOString(),
  };
}

const SEVERITY_BY_ACTION = (action: string): AuditLogEntry["severity"] => {
  const a = action.toUpperCase();
  if (a.includes("REJECT") || a.includes("ESCALATION") || a.includes("DELETE")) return "error";
  if (a.includes("APPROVE") || a.includes("CREATE") || a.includes("PUBLISH")) return "success";
  if (a.includes("ROUTE") || a.includes("RETURN") || a.includes("INFO")) return "warning";
  return "info";
};

export function mapAudit(r: Raw): AuditLogEntry {
  const action = r.action ?? r.event ?? "EVENT";
  return {
    id: String(r.id ?? `${r.timestamp ?? ""}-${action}`),
    actorId: String(r.actor_id ?? r.actorId ?? ""),
    actorName: r.actor_name ?? r.actor ?? "System",
    actorRole: (String(r.actor_role ?? r.actorRole ?? r.role ?? "system").toLowerCase() as AuditLogEntry["actorRole"]),
    action,
    entity: r.entity ?? r.target ?? "",
    summary: r.summary ?? r.message ?? r.detail ?? action,
    reference: r.reference ?? r.ref ?? r.policy_version ?? undefined,
    hash: r.hash ?? undefined,
    timestamp: r.timestamp ?? r.created_at ?? new Date().toISOString(),
    severity: r.severity ?? SEVERITY_BY_ACTION(action),
  };
}

export function mapUser(r: Raw): User {
  return {
    id: String(r.id ?? r.subject_id ?? ""),
    name: r.name ?? r.email ?? "—",
    email: r.email ?? "",
    role: String(r.role ?? "employee").toLowerCase() as Role,
    agencyId: String(r.agency_id ?? r.agencyId ?? ""),
    agencyName: (r.agency_name ?? r.agencyName) as string | undefined,
  };
}

export function mapPolicy(r: Raw): AgencyPolicyDocument {
  const status = String(r.status ?? "draft").toLowerCase();
  return {
    id: String(r.id ?? ""),
    agencyId: String(r.agency_id ?? r.agencyId ?? ""),
    name: r.name ?? "",
    version: String(r.version ?? ""),
    effectiveDate: r.effective_date ?? r.effectiveDate ?? "",
    indexedAt: r.indexed_at ?? r.indexedAt ?? "",
    status: (status === "active" || status === "archived"
      ? status
      : "draft") as AgencyPolicyDocument["status"],
    createdBy: r.created_by ?? r.createdBy ?? "",
    publishedBy: r.published_by ?? r.publishedBy ?? undefined,
  };
}

export function mapNotification(r: Raw): AppNotification {
  return {
    id: String(r.id ?? ""),
    kind: String(r.kind ?? "info").toLowerCase() as AppNotification["kind"],
    icon: r.icon ?? "notifications",
    title: r.title ?? "",
    body: r.body ?? "",
    href: r.href ?? undefined,
    timestamp: r.timestamp ?? r.created_at ?? new Date().toISOString(),
    read: Boolean(r.read ?? r.is_read ?? false),
  };
}

export function mapSpend(r: Raw): SpendByCategory {
  return {
    category: (r.category ?? "Other") as SpendByCategory["category"],
    amount: num(r.amount),
  };
}

export function mapAttachment(r: Raw): Attachment {
  return {
    id: String(r.id ?? ""),
    lineItemId: String(r.line_item_id ?? r.lineItemId ?? ""),
    fileName: r.filename ?? r.fileName ?? r.file_name ?? "receipt",
    fileType: r.file_type ?? r.fileType ?? "application/octet-stream",
    sizeBytes: num(r.size ?? r.sizeBytes, 0),
    scanStatus: (String(r.scan_status ?? r.scanStatus ?? "pending").toLowerCase() as Attachment["scanStatus"]),
    ocrStatus: (String(r.ocr_status ?? r.ocrStatus ?? "pending").toLowerCase() as Attachment["ocrStatus"]),
    uploadedAt: asUtc(r.uploaded_at ?? r.uploadedAt),
  };
}

export function mapDecision(r: Raw): DecisionEntry {
  return {
    id: String(r.id ?? ""),
    actorId: String(r.actor_id ?? r.actorId ?? ""),
    actorRole: String(r.actor_role ?? r.actorRole ?? "system").toLowerCase(),
    action: r.action ?? "EVENT",
    reason: r.reason ?? undefined,
    llmModelVersion: r.llm_model_version ?? undefined,
    policyVersion: r.policy_version ?? undefined,
    citedClauses: Array.isArray(r.cited_clauses) ? r.cited_clauses.map(String) : [],
    timestamp: asUtc(r.timestamp ?? r.created_at) ?? new Date().toISOString(),
  };
}
