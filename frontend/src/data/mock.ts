/**
 * Mock dataset backing the demo. Mirrors the synthetic dataset in SCOPING.md
 * §20.D (compliant items, policy violations, near-duplicates, missing receipt).
 * Swap `src/data/api.ts` to call the real FastAPI backend to go live.
 */
import type {
  Agency,
  AgencyPolicyDocument,
  AppNotification,
  AuditLogEntry,
  BaselinePolicy,
  ExpenseSheet,
  FinanceKpis,
  LineItem,
  Role,
  User,
} from "./types";

// ── Agencies ─────────────────────────────────────────────────────────────────

export const agencies: Agency[] = [
  { id: "AGY-CRISPIN", name: "Crispin", status: "active", tier: "Enterprise", userCount: 1245, createdBy: "alex.rivera", createdAt: "2025-01-12T09:00:00Z" },
  { id: "AGY-SKDK", name: "SKDK", status: "active", tier: "Pro", userCount: 892, createdBy: "alex.rivera", createdAt: "2025-02-03T09:00:00Z" },
  { id: "AGY-JETFUEL", name: "JetFuel", status: "active", tier: "Pro", userCount: 311, createdBy: "alex.rivera", createdAt: "2025-03-21T09:00:00Z" },
  { id: "AGY-ACME", name: "Acme Corp", status: "active", tier: "Enterprise", userCount: 1245, createdBy: "alex.rivera", createdAt: "2025-04-01T09:00:00Z" },
  { id: "AGY-GLOBEX", name: "Globex Inc", status: "active", tier: "Pro", userCount: 892, createdBy: "alex.rivera", createdAt: "2026-06-14T09:15:00Z" },
  { id: "AGY-INITECH", name: "Initech", status: "suspended", tier: "Basic", userCount: 42, createdBy: "alex.rivera", createdAt: "2025-09-09T09:00:00Z" },
];

// ── Users (one representative per role for the demo) ──────────────────────────

export const usersByRole: Record<Role, User> = {
  employee: {
    id: "USR-JANE",
    name: "Jane Doe",
    email: "employee@demo.local",
    role: "employee",
    agencyId: "AGY-CRISPIN",
    avatarUrl:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuD-dK1yfEIvgQj41fz53badizKcUfgYS8n90fNB7I-N6mOoyM1Pdh2-WRTfe-uI9nuQVe9b8E0jaTp3lC_L1Li_XMkieY-HjRAOJ4m17KrsYCbEfv_qVEprK4La1-InT8XNdlxryqS_ALEEC2_C9s7b-JRMb9_nuaHqk1m2nnNVS9R0EthlZVIuHTCJiPbSkrNumXwSBI6DrR_FcP79z8Ss-iDgZuvC1RRHr963oPVK4st1a132SLA21CmN99iINZRGjO32oBJZ-BI",
  },
  manager: {
    id: "USR-MARK",
    name: "Mark Chen",
    email: "manager@demo.local",
    role: "manager",
    agencyId: "AGY-CRISPIN",
    avatarUrl:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuB3m0_a5ReeZrUNkj7Iso7Kok92k-R9PqJjrIJOVDOkssAu9bt76BRp2WvWqDQ_SKkjYGDJVB8lhDEKQqnRu6DDTl5fQH133cHHY28vWtnH6RSJ1joxfxgkGQRA6y09Yel8LF98fUPvsMc3_pGmdwlRUffI8ap8lNgj7loFBagaPsHc7X0jJ9m2WCZBuRSY2LbuBTF4SKMMnBL-1GYZ6suc_Hf2yIKrtgFf1sIl-kxg5wRbTbroAf6gKlWq3Vi-UYDStPrCW9FasZY",
  },
  finance: {
    id: "USR-SARAH",
    name: "Sarah Okafor",
    email: "finance@demo.local",
    role: "finance",
    agencyId: "AGY-CRISPIN",
    avatarUrl:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuDYZSStMXqo7LCIrxFtW0TQfZKVu6lkHhpbYhbnfVKRc_YRnDXvvQSPgf-gysj3v3OATeheXEQWkxN8RS0anamUrrl9FNlk8eT8ePwWOlG0tB9pkGM4Dww4jDG0pGUi9_TNRs3mhzONHpb6STTbnkblCDMPr0nSPQTdr4008ASwjhwS3Dwh9n1Y3Xc1hLrujVk3qCICfKo0POfEsKcDocJujdDw7QCQZfDr7jNFONbOR7fJM4BOBBuHeEqbaTdCYoGW9Eiv2nlUJzc",
  },
  admin: {
    id: "USR-ALEX",
    name: "Alex Rivera",
    email: "admin@demo.local",
    role: "admin",
    agencyId: "AGY-CRISPIN",
  },
};

// ── Agency policy documents (RAG-indexed) ────────────────────────────────────

export const policyDocuments: AgencyPolicyDocument[] = [
  { id: "POL-CRISPIN", agencyId: "AGY-CRISPIN", name: "Crispin Travel & Expense Policy", version: "v2.1", effectiveDate: "2024-05-01", indexedAt: "2026-06-14T08:00:00Z", status: "active", createdBy: "sarah.okafor", publishedBy: "sarah.okafor" },
  { id: "POL-SKDK", agencyId: "AGY-SKDK", name: "SKDK Travel Policy", version: "v1.4", effectiveDate: "2026-04-10", indexedAt: "2026-06-11T08:00:00Z", status: "active", createdBy: "sarah.okafor", publishedBy: "sarah.okafor" },
  { id: "POL-JETFUEL", agencyId: "AGY-JETFUEL", name: "JetFuel Vendor Guidelines", version: "v3.0", effectiveDate: "2026-03-15", indexedAt: "2026-06-07T08:00:00Z", status: "active", createdBy: "sarah.okafor", publishedBy: "sarah.okafor" },
  { id: "POL-ACME", agencyId: "AGY-ACME", name: "Acme Corp Enterprise Travel Policy", version: "v1.0", effectiveDate: "2026-02-01", indexedAt: "2026-06-10T08:00:00Z", status: "active", createdBy: "sarah.okafor", publishedBy: "alex.rivera" },
  { id: "POL-GLOBEX", agencyId: "AGY-GLOBEX", name: "Globex Inc Expense Policy", version: "v2.0", effectiveDate: "2026-05-01", indexedAt: "2026-06-14T09:30:00Z", status: "draft", createdBy: "sarah.okafor" },
];

// ── Baseline policy (intake tier) ────────────────────────────────────────────

export const baselinePolicy: BaselinePolicy = {
  per_meal_limit: 75,
  per_hotel_night_limit: 250,
  prohibited_categories: ["Other"],
  receipt_required_threshold: 25,
  submission_cutoff: "month_end_of_incurred_month",
  max_file_mb: 25,
  allowed_extensions: [".pdf", ".jpeg", ".jpg", ".heic", ".png", ".docx", ".doc"],
  duplicate_near_match_days: 3,
  cap_boundary: "inclusive",
  llm_confidence_routing_threshold: 0.7,
  currency: "USD",
};

// ── Finance KPIs ─────────────────────────────────────────────────────────────

export const financeKpis: FinanceKpis = {
  autoApprovalRate: 92.4,
  autoApprovalDelta: 1.2,
  manualInterventions: 143,
  manualInterventionsDelta: 12,
  policyCitations: 4200,
  topClause: "Travel > Per Diem",
  ragSyncedAgo: "2h ago",
  approvalAccuracy: 98.7,
  escalationRate: 7.6,
  falsePositiveRate: 3.2,
  slaCompliance: 96.2,
  avgResolutionHours: 5.4,
  policyComplianceRate: 98.1,
};

/** Auto-approval rate trend (last 12 periods) for the finance sparkline/chart. */
export const autoApprovalTrend = [88.1, 89.0, 88.6, 90.2, 91.1, 90.5, 91.8, 92.0, 91.6, 92.9, 92.1, 92.4];

// ── Audit log ────────────────────────────────────────────────────────────────

export const auditLog: AuditLogEntry[] = [
  { id: "AUD-1", actorId: "USR-ALEX", actorName: "Alex Rivera", actorRole: "admin", action: "POLICY_UPDATE", entity: "BaselinePolicy", summary: "Admin (sys_admin_1) updated global baseline policy.", hash: "a7f8b9...2c4", timestamp: "2026-06-14T10:42:00Z", severity: "info" },
  { id: "AUD-2", actorId: "USR-ALEX", actorName: "Alex Rivera", actorRole: "admin", action: "AGENCY_CREATED", entity: "Agency", summary: "New agency 'Globex Inc' onboarded to Pro tier.", reference: "AGY-992-K", timestamp: "2026-06-14T09:15:00Z", severity: "success" },
  { id: "AUD-3", actorId: "USR-ALEX", actorName: "Alex Rivera", actorRole: "admin", action: "ROLE_ESCALATION", entity: "User", summary: "User j.doe@acme.com elevated to Finance role.", reference: "Authorized by: a.rivera", timestamp: "2026-06-13T16:20:00Z", severity: "error" },
  { id: "AUD-4", actorId: "SYSTEM", actorName: "System", actorRole: "system", action: "SYSTEM_MAINT", entity: "Platform", summary: "Automated backup completed successfully.", reference: "Size: 4.2TB", timestamp: "2026-06-13T02:00:00Z", severity: "info" },
  { id: "AUD-5", actorId: "LLM", actorName: "Auxilab AI Finance Approver", actorRole: "llm_approver", action: "FINANCE_ROUTED", entity: "ExpenseSheet", summary: "Sheet #EXP-2026-0842 routed to a human — ambiguous clause (Crispin v2.1).", reference: "confidence 58% · policy v2.1", timestamp: "2026-06-14T07:55:00Z", severity: "warning" },
  { id: "AUD-6", actorId: "USR-SARAH", actorName: "Sarah Okafor", actorRole: "finance", action: "POLICY_PUBLISH", entity: "AgencyPolicy", summary: "Crispin Finance Rules v2.1 published and re-indexed.", reference: "maker-checker: approved", timestamp: "2026-06-14T08:01:00Z", severity: "success" },
  { id: "AUD-7", actorId: "LLM", actorName: "Auxilab AI Finance Approver", actorRole: "llm_approver", action: "FINANCE_AUTO_APPROVED", entity: "ExpenseSheet", summary: "Auto-approved SH-2026-085 (1 line item cleared policy).", reference: "confidence 96% · policy v2.1", timestamp: "2026-06-13T15:10:00Z", severity: "success" },
  { id: "AUD-8", actorId: "USR-MARK", actorName: "Mark Chen", actorRole: "manager", action: "MANAGER_APPROVE", entity: "LineItem", summary: "Mark Chen approved \"Hardware Procurement\" on SH-2026-085.", reference: "SH-2026-085", timestamp: "2026-06-13T14:02:00Z", severity: "success" },
  { id: "AUD-9", actorId: "USR-SARAH", actorName: "Sarah Okafor", actorRole: "finance", action: "FINANCE_OVERRIDE", entity: "ExpenseSheet", summary: "Sarah Okafor approved routed sheet EXP-2026-0815 after manual review.", reference: "manual intervention", timestamp: "2026-06-13T13:30:00Z", severity: "success" },
  { id: "AUD-10", actorId: "USR-JANE", actorName: "Jane Doe", actorRole: "employee", action: "SHEET_SUBMITTED", entity: "ExpenseSheet", summary: "Jane Doe submitted \"Q3 Field Operations\" for manager review.", reference: "SH-2026-8891", timestamp: "2026-06-12T09:20:00Z", severity: "info" },
  { id: "AUD-11", actorId: "USR-JANE", actorName: "Jane Doe", actorRole: "employee", action: "SHEET_SUBMITTED", entity: "ExpenseSheet", summary: "Jane Doe submitted \"Client Dinner NYC\" for manager review.", reference: "SH-2026-088", timestamp: "2026-06-11T17:45:00Z", severity: "info" },
];

// ── Notifications ────────────────────────────────────────────────────────────

export const notifications: AppNotification[] = [
  { id: "N1", kind: "error", icon: "cancel", title: "Sheet rejected", body: "Wi-Fi reimbursement (SH-2026-066) exceeded the $100 cap.", href: "/employee/sheets/SH-2026-066", timestamp: "2026-09-02T11:00:00Z", read: false, roles: ["employee"] },
  { id: "N2", kind: "success", icon: "check_circle", title: "Sheet approved", body: "Hardware Procurement (SH-2026-085) was approved by the AI approver.", href: "/employee/sheets/SH-2026-085", timestamp: "2026-10-01T09:00:00Z", read: false, roles: ["employee"] },
  { id: "N3", kind: "warning", icon: "hourglass_top", title: "Aging review", body: "Conference Travel SF (SH-2026-8885) has been pending 2 days.", href: "/manager", timestamp: "2026-06-12T10:00:00Z", read: false, roles: ["manager"] },
  { id: "N4", kind: "warning", icon: "hub", title: "Routed for review", body: "EXP-2026-0842 routed to human — ambiguous clause.", href: "/finance", timestamp: "2026-06-14T07:55:00Z", read: false, roles: ["finance"] },
  { id: "N5", kind: "info", icon: "domain", title: "Agency onboarded", body: "Globex Inc was onboarded to the Pro tier.", href: "/admin", timestamp: "2026-06-14T09:15:00Z", read: true, roles: ["admin"] },
];

// ── Expense sheets ───────────────────────────────────────────────────────────

function li(partial: Partial<LineItem> & Pick<LineItem, "id" | "sheetId" | "merchant" | "category" | "amount" | "expenseDate">): LineItem {
  return {
    description: partial.description ?? partial.merchant,
    currency: "USD",
    managerStatus: "PENDING_MANAGER",
    attachments: [],
    ...partial,
  } as LineItem;
}

function attach(lineItemId: string, fileName: string, fileType = "application/pdf"): LineItem["attachments"][number] {
  return { id: `ATT-${lineItemId}`, lineItemId, fileName, fileType, sizeBytes: 482_113, scanStatus: "clean", ocrStatus: "done" };
}

export const expenseSheets: ExpenseSheet[] = [
  // — Employee (Jane Doe) sheets —
  {
    id: "SH-2026-089",
    title: "Q3 Engineering Offsite",
    employeeId: "USR-JANE",
    employeeName: "Jane Doe",
    agencyId: "AGY-CRISPIN",
    agencyName: "Crispin",
    version: 1,
    status: "DRAFT",
    period: "Oct 2026",
    total: 655.5,
    currency: "USD",
    updatedAt: "2026-10-14T11:00:00Z",
    lineItems: [
      li({ id: "LI-089-1", sheetId: "SH-2026-089", merchant: "Delta Airlines", description: "Flight to Chicago", category: "Travel - Air", amount: 450, expenseDate: "2026-10-12", receiptDatetime: "2026-10-12T08:14:00Z", receiptTotal: 450, attachments: [attach("LI-089-1", "delta-boarding.pdf")] }),
      li({
        id: "LI-089-2", sheetId: "SH-2026-089", merchant: "Uber Eats", description: "Team dinner", category: "Meals & Entertainment", amount: 85.5, expenseDate: "2026-10-13",
        aiFlag: { message: "Exceeds daily meal allowance", clauseRef: "POL-ML-02", severity: "warning" },
      }),
      li({ id: "LI-089-3", sheetId: "SH-2026-089", merchant: "WeWork", description: "Office space day pass", category: "Office Supplies", amount: 120, expenseDate: "2026-10-14", receiptDatetime: "2026-10-14T18:00:00Z", receiptTotal: 120, attachments: [attach("LI-089-3", "wework-invoice.pdf")] }),
    ],
  },
  {
    id: "SH-2026-088",
    title: "Client Dinner NYC",
    employeeId: "USR-JANE", employeeName: "Jane Doe", agencyId: "AGY-CRISPIN", agencyName: "Crispin",
    version: 1, status: "SUBMITTED", period: "Oct 2026", total: 340, currency: "USD",
    submittedAt: "2026-10-10T20:00:00Z", updatedAt: "2026-10-10T20:00:00Z",
    lineItems: [
      li({ id: "LI-088-1", sheetId: "SH-2026-088", merchant: "Gramercy Tavern", description: "Client dinner", category: "Client Entertainment", amount: 340, expenseDate: "2026-10-09", receiptDatetime: "2026-10-09T21:10:00Z", receiptTotal: 340, attachments: [attach("LI-088-1", "gramercy.pdf")] }),
    ],
  },
  {
    id: "SH-2026-085",
    title: "Hardware Procurement",
    employeeId: "USR-JANE", employeeName: "Jane Doe", agencyId: "AGY-CRISPIN", agencyName: "Crispin",
    version: 1, status: "FINANCE_APPROVED", period: "Sep 2026", total: 1200, currency: "USD",
    submittedAt: "2026-09-28T14:00:00Z", updatedAt: "2026-10-01T09:00:00Z",
    financeDecision: "APPROVED", financeDecidedBy: "LLM Finance Approver", policyVersionUsed: "v2.1",
    lineItems: [
      li({ id: "LI-085-1", sheetId: "SH-2026-085", merchant: "Apple Store", description: "MacBook Pro 14\"", category: "Office Supplies", amount: 1200, expenseDate: "2026-09-27", receiptDatetime: "2026-09-27T13:00:00Z", receiptTotal: 1200, managerStatus: "MANAGER_APPROVED", policyStatus: "POLICY_PASS", attachments: [attach("LI-085-1", "apple-invoice.pdf")] }),
    ],
  },
  {
    id: "SH-2026-070",
    title: "September Commute",
    employeeId: "USR-JANE", employeeName: "Jane Doe", agencyId: "AGY-CRISPIN", agencyName: "Crispin",
    version: 1, status: "PAID", period: "Sep 2026", total: 150, currency: "USD",
    submittedAt: "2026-09-30T17:00:00Z", updatedAt: "2026-10-05T10:00:00Z",
    financeDecision: "APPROVED", financeDecidedBy: "LLM Finance Approver", policyVersionUsed: "v2.1",
    lineItems: [
      li({ id: "LI-070-1", sheetId: "SH-2026-070", merchant: "MTA", description: "Monthly transit pass", category: "Travel - Ground", amount: 150, expenseDate: "2026-09-01", receiptDatetime: "2026-09-01T08:00:00Z", receiptTotal: 150, managerStatus: "MANAGER_APPROVED", policyStatus: "POLICY_PASS", attachments: [attach("LI-070-1", "mta-pass.pdf")] }),
    ],
  },
  {
    id: "SH-2026-066",
    title: "August Wi-Fi Reimbursement",
    employeeId: "USR-JANE", employeeName: "Jane Doe", agencyId: "AGY-CRISPIN", agencyName: "Crispin",
    version: 2, status: "FINANCE_REJECTED", period: "Aug 2026", total: 130.01, currency: "USD",
    submittedAt: "2026-08-30T12:00:00Z", updatedAt: "2026-09-02T11:00:00Z",
    financeDecision: "REJECTED_WITH_COMMENTS", financeDecidedBy: "LLM Finance Approver", policyVersionUsed: "v2.1",
    citedClause: { policyName: "Crispin Finance Rules v2.1", text: "Wi-Fi / internet reimbursement is capped at $100; any amount above is rejected." },
    lineItems: [
      li({ id: "LI-066-1", sheetId: "SH-2026-066", merchant: "Verizon Fios", description: "Home internet", category: "Software / Subscriptions", amount: 130.01, expenseDate: "2026-08-15", receiptDatetime: "2026-08-15T09:00:00Z", receiptTotal: 130.01, managerStatus: "MANAGER_APPROVED", policyStatus: "POLICY_FAIL", policyClauseRef: "WIFI-01", attachments: [attach("LI-066-1", "verizon.pdf")] }),
    ],
  },

  // — Manager review queue (Crispin agency, pending) —
  {
    id: "SH-2026-8891",
    title: "Q3 Field Operations",
    employeeId: "USR-JANE", employeeName: "Jane Doe", agencyId: "AGY-CRISPIN", agencyName: "Crispin",
    version: 1, status: "IN_MANAGER_REVIEW", period: "Oct 2026", total: 1245.5, currency: "USD",
    submittedAt: "2026-06-14T12:00:00Z", updatedAt: "2026-06-14T12:00:00Z",
    lineItems: [
      li({ id: "LI-8891-1", sheetId: "SH-2026-8891", merchant: "United Airlines", description: "Flight to Chicago", category: "Travel - Air", amount: 450, expenseDate: "2026-06-10", managerStatus: "MANAGER_APPROVED", attachments: [attach("LI-8891-1", "united.pdf")] }),
      li({ id: "LI-8891-2", sheetId: "SH-2026-8891", merchant: "Uber", description: "Uber to Hotel", category: "Travel - Ground", amount: 45.5, expenseDate: "2026-06-10", managerStatus: "MANAGER_APPROVED", attachments: [attach("LI-8891-2", "uber.pdf")] }),
      li({ id: "LI-8891-3", sheetId: "SH-2026-8891", merchant: "Hilton", description: "2 nights", category: "Travel - Hotel", amount: 0, expenseDate: "2026-06-10", managerStatus: "MANAGER_APPROVED", attachments: [attach("LI-8891-3", "hilton.pdf")] }),
      li({
        id: "LI-8891-4", sheetId: "SH-2026-8891", merchant: "Peter Luger", description: "Client Dinner - Steakhouse", category: "Client Entertainment", amount: 650, expenseDate: "2026-06-11",
        aiFlag: { message: "Amount exceeds standard meal allowance ($150). Justification required per policy", clauseRef: "MEAL-04", severity: "error" },
        attachments: [attach("LI-8891-4", "peterluger.pdf")],
      }),
      li({ id: "LI-8891-5", sheetId: "SH-2026-8891", merchant: "Home Depot", description: "Equipment Rental", category: "Office Supplies", amount: 100, expenseDate: "2026-06-12", attachments: [attach("LI-8891-5", "homedepot.pdf")] }),
    ],
  },
  {
    id: "SH-2026-8890",
    title: "Client Dinner NYC",
    employeeId: "USR-MS", employeeName: "Mark Smith", agencyId: "AGY-CRISPIN", agencyName: "Crispin",
    version: 1, status: "IN_MANAGER_REVIEW", period: "Oct 2026", total: 450, currency: "USD",
    submittedAt: "2026-06-13T19:00:00Z", updatedAt: "2026-06-13T19:00:00Z",
    lineItems: [
      li({ id: "LI-8890-1", sheetId: "SH-2026-8890", merchant: "Le Bernardin", description: "Client dinner", category: "Client Entertainment", amount: 380, expenseDate: "2026-06-12", attachments: [attach("LI-8890-1", "lebernardin.pdf")] }),
      li({ id: "LI-8890-2", sheetId: "SH-2026-8890", merchant: "Uber", description: "Ride home", category: "Travel - Ground", amount: 70, expenseDate: "2026-06-12", attachments: [attach("LI-8890-2", "uber2.pdf")] }),
    ],
  },
  {
    id: "SH-2026-8885",
    title: "Conference Travel SF",
    employeeId: "USR-SJ", employeeName: "Sarah Jenkins", agencyId: "AGY-CRISPIN", agencyName: "Crispin",
    version: 1, status: "IN_MANAGER_REVIEW", period: "Oct 2026", total: 3120, currency: "USD",
    submittedAt: "2026-06-12T10:00:00Z", updatedAt: "2026-06-12T10:00:00Z",
    lineItems: [
      li({ id: "LI-8885-1", sheetId: "SH-2026-8885", merchant: "American Airlines", description: "SFO round trip", category: "Travel - Air", amount: 720, expenseDate: "2026-06-08", attachments: [attach("LI-8885-1", "aa.pdf")] }),
      li({ id: "LI-8885-2", sheetId: "SH-2026-8885", merchant: "Marriott", description: "3 nights", category: "Travel - Hotel", amount: 1500, expenseDate: "2026-06-08", attachments: [attach("LI-8885-2", "marriott.pdf")] }),
      li({ id: "LI-8885-3", sheetId: "SH-2026-8885", merchant: "Dreamforce", description: "Conference pass", category: "Software / Subscriptions", amount: 900, expenseDate: "2026-06-07", attachments: [attach("LI-8885-3", "df.pdf")] }),
    ],
  },

  // — Finance: routed for manual review —
  {
    id: "EXP-2026-0842",
    title: "Client Entertainment — Group Dinner",
    employeeId: "USR-JANE", employeeName: "Jane Doe", agencyId: "AGY-CRISPIN", agencyName: "Crispin",
    version: 1, status: "FINANCE_MANUAL_REVIEW", period: "Jun 2026", total: 1245, currency: "USD",
    submittedAt: "2026-06-14T07:30:00Z", updatedAt: "2026-06-14T07:55:00Z",
    financeDecision: "ROUTED_TO_HUMAN", routeReason: "AMBIGUOUS_CLAUSE", policyVersionUsed: "v2.1", llmConfidence: 0.68,
    routeReasonDetail: 'The receipt indicates "Client Entertainment - Group Dinner", but the total exceeds the standard per-meal limit ($75). The policy document has an ambiguous clause regarding group dinners requiring pre-approval, which is not attached.',
    citedClause: { policyName: "Crispin v2.1", text: "Individual meals are capped at $75 inclusive of tax and tip. Group client entertainment exceeding $500 total requires documented pre-approval from the agency Managing Director." },
    lineItems: [
      li({ id: "LI-0842-1", sheetId: "EXP-2026-0842", merchant: "Carbone", description: "Group client dinner (8 attendees)", category: "Client Entertainment", amount: 1245, expenseDate: "2026-06-11", receiptDatetime: "2026-06-11T21:30:00Z", receiptTotal: 1245, managerStatus: "MANAGER_APPROVED", policyStatus: "POLICY_UNCERTAIN", attachments: [attach("LI-0842-1", "carbone.pdf")] }),
    ],
  },
  {
    id: "EXP-2026-0839",
    title: "Travel — Ground",
    employeeId: "USR-DK", employeeName: "Diego Kim", agencyId: "AGY-SKDK", agencyName: "SKDK",
    version: 1, status: "FINANCE_MANUAL_REVIEW", period: "Jun 2026", total: 450.75, currency: "USD",
    submittedAt: "2026-06-14T06:00:00Z", updatedAt: "2026-06-14T06:40:00Z",
    financeDecision: "ROUTED_TO_HUMAN", routeReason: "LOW_CONFIDENCE", policyVersionUsed: "v1.4", llmConfidence: 0.62,
    routeReasonDetail: "Retrieval returned low-relevance chunks for ground-transport caps; confidence below the routing threshold (0.70).",
    lineItems: [
      li({ id: "LI-0839-1", sheetId: "EXP-2026-0839", merchant: "Blacklane", description: "Executive car service", category: "Travel - Ground", amount: 450.75, expenseDate: "2026-06-10", managerStatus: "MANAGER_APPROVED", policyStatus: "POLICY_UNCERTAIN", attachments: [attach("LI-0839-1", "blacklane.pdf")] }),
    ],
  },
  {
    id: "EXP-2026-0831",
    title: "Software — Subscription",
    employeeId: "USR-RP", employeeName: "Riya Patel", agencyId: "AGY-JETFUEL", agencyName: "JetFuel",
    version: 1, status: "FINANCE_MANUAL_REVIEW", period: "Jun 2026", total: 89.99, currency: "USD",
    submittedAt: "2026-06-13T15:00:00Z", updatedAt: "2026-06-13T15:30:00Z",
    financeDecision: "ROUTED_TO_HUMAN", routeReason: "MISSING_POLICY", policyVersionUsed: "v3.0", llmConfidence: 0.4,
    routeReasonDetail: "No agency policy clause covers SaaS subscriptions for JetFuel — approver must route to human (never auto-approve on missing policy).",
    lineItems: [
      li({ id: "LI-0831-1", sheetId: "EXP-2026-0831", merchant: "Figma", description: "Annual seat", category: "Software / Subscriptions", amount: 89.99, expenseDate: "2026-06-12", managerStatus: "MANAGER_APPROVED", policyStatus: "POLICY_UNCERTAIN", attachments: [attach("LI-0831-1", "figma.pdf")] }),
    ],
  },
];

/** Convenience: the immutable status total used for the manager queue badge. */
export const MANAGER_QUEUE_AGENCY = "US-EAST-01";
