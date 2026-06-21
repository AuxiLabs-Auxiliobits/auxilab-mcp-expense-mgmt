import type {
  AgencyStatus,
  FinanceDecision,
  LineItemStatus,
  RouteReason,
  SheetStatus,
} from "@/data/types";

export interface StatusMeta {
  label: string;
  /** Tailwind classes for a pill badge (bg + text + border). */
  badgeClass: string;
  /** Material Symbols icon name. */
  icon: string;
}

const SUCCESS = "bg-success-green/10 text-success-green border border-success-green/20";
const ERROR = "bg-error-container text-on-error-container border border-error/20";
const WARNING = "bg-yellow-500/10 text-yellow-600 border border-yellow-500/20";
const INFO = "bg-tertiary-fixed text-on-tertiary-fixed-variant border border-tertiary/20";
const NEUTRAL =
  "bg-surface-container-highest text-on-surface-variant border border-outline-variant";
const DRAFT = "bg-secondary-fixed text-on-secondary-fixed-variant border border-outline-variant";

export const SHEET_STATUS_META: Record<SheetStatus, StatusMeta> = {
  DRAFT: { label: "Draft", badgeClass: DRAFT, icon: "draft" },
  SUBMITTED: { label: "Submitted", badgeClass: INFO, icon: "schedule" },
  IN_MANAGER_REVIEW: {
    label: "In Manager Review",
    badgeClass: INFO,
    icon: "supervisor_account",
  },
  RETURNED_TO_EMPLOYEE: {
    label: "Returned",
    badgeClass: WARNING,
    icon: "undo",
  },
  IN_FINANCE_REVIEW: {
    label: "In Finance Review",
    badgeClass: INFO,
    icon: "smart_toy",
  },
  FINANCE_APPROVED: { label: "Approved", badgeClass: SUCCESS, icon: "check_circle" },
  FINANCE_REJECTED: { label: "Rejected", badgeClass: ERROR, icon: "cancel" },
  FINANCE_MANUAL_REVIEW: {
    label: "Manual Review",
    badgeClass: INFO,
    icon: "hub",
  },
  APPROVED: { label: "Approved", badgeClass: SUCCESS, icon: "check_circle" },
  REJECTED: { label: "Rejected", badgeClass: ERROR, icon: "cancel" },
  PAID: { label: "Paid", badgeClass: SUCCESS, icon: "paid" },
  WITHDRAWN: { label: "Withdrawn", badgeClass: NEUTRAL, icon: "cancel_presentation" },
};

export const LINE_ITEM_STATUS_META: Record<LineItemStatus, StatusMeta> = {
  PENDING_MANAGER: {
    label: "Pending Manager",
    badgeClass: NEUTRAL,
    icon: "radio_button_unchecked",
  },
  MANAGER_APPROVED: { label: "Approved", badgeClass: SUCCESS, icon: "check_circle" },
  MANAGER_REJECTED: { label: "Rejected", badgeClass: ERROR, icon: "cancel" },
  INFO_REQUESTED: { label: "Info Requested", badgeClass: WARNING, icon: "help" },
  POLICY_PASS: { label: "Policy Pass", badgeClass: SUCCESS, icon: "verified" },
  POLICY_FAIL: { label: "Policy Fail", badgeClass: ERROR, icon: "gpp_bad" },
  POLICY_UNCERTAIN: { label: "Uncertain", badgeClass: INFO, icon: "help_center" },
};

export const FINANCE_DECISION_META: Record<FinanceDecision, StatusMeta> = {
  APPROVED: { label: "Approved", badgeClass: SUCCESS, icon: "check_circle" },
  REJECTED_WITH_COMMENTS: {
    label: "Rejected with Comments",
    badgeClass: ERROR,
    icon: "cancel",
  },
  ROUTED_TO_HUMAN: { label: "Routed to Human", badgeClass: INFO, icon: "hub" },
};

export const ROUTE_REASON_META: Record<RouteReason, StatusMeta> = {
  LOW_CONFIDENCE: { label: "Low Confidence", badgeClass: INFO, icon: "info" },
  AMBIGUOUS_CLAUSE: { label: "Ambiguous Clause", badgeClass: ERROR, icon: "warning" },
  MISSING_POLICY: { label: "Missing Policy", badgeClass: WARNING, icon: "help" },
  NUMERIC_DISAGREEMENT: {
    label: "Numeric Disagreement",
    badgeClass: ERROR,
    icon: "calculate",
  },
};

export const AGENCY_STATUS_META: Record<AgencyStatus, StatusMeta> = {
  active: { label: "Active", badgeClass: SUCCESS, icon: "check_circle" },
  suspended: { label: "Suspended", badgeClass: ERROR, icon: "block" },
  soft_deleted: { label: "Deleted", badgeClass: NEUTRAL, icon: "delete" },
};

/** Category → Material Symbols icon, used in line-item grids. */
export const CATEGORY_ICON: Record<string, string> = {
  "Meals & Entertainment": "restaurant",
  "Travel - Air": "flight",
  "Travel - Hotel": "hotel",
  "Travel - Ground": "local_taxi",
  "Office Supplies": "inventory_2",
  "Software / Subscriptions": "cloud",
  "Client Entertainment": "groups",
  Other: "category",
};
