"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import * as api from "./api";
import type { Role } from "./types";

export const queryKeys = {
  currentUser: (role: Role) => ["current-user", role] as const,
  employeeKpis: (id: string) => ["employee-kpis", id] as const,
  employeeSheets: (id: string) => ["employee-sheets", id] as const,
  activeDraft: (id: string) => ["active-draft", id] as const,
  sheet: (id: string) => ["sheet", id] as const,
  allSheets: ["all-sheets"] as const,
  managerQueue: (agencyId: string) => ["manager-queue", agencyId] as const,
  routedSheets: ["routed-sheets"] as const,
  financeKpis: ["finance-kpis"] as const,
  policyDocuments: ["policy-documents"] as const,
  spendByCategory: ["spend-by-category"] as const,
  agencies: ["agencies"] as const,
  baselinePolicy: ["baseline-policy"] as const,
  auditLog: ["audit-log"] as const,
  myAuditLog: (id: string) => ["my-audit", id] as const,
  activityLog: (role: Role, id: string) => ["activity-log", role, id] as const,
  notifications: (role: Role) => ["notifications", role] as const,
};

// ── Session ──
export const useCurrentUser = (role: Role) =>
  useQuery({ queryKey: queryKeys.currentUser(role), queryFn: () => api.getCurrentUser(role) });

// ── Employee ──
export const useEmployeeKpis = (employeeId: string) =>
  useQuery({ queryKey: queryKeys.employeeKpis(employeeId), queryFn: () => api.getEmployeeKpis(employeeId) });

export const useEmployeeSheets = (employeeId: string) =>
  useQuery({ queryKey: queryKeys.employeeSheets(employeeId), queryFn: () => api.getEmployeeSheets(employeeId) });

export const useActiveDraft = (employeeId: string) =>
  useQuery({ queryKey: queryKeys.activeDraft(employeeId), queryFn: () => api.getActiveDraft(employeeId) });

// ── Sheets ──
export const useSheet = (id: string | undefined) =>
  useQuery({ queryKey: queryKeys.sheet(id ?? ""), queryFn: () => api.getSheet(id as string), enabled: !!id });

export function useCreateSheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createSheet,
    onSuccess: (sheet) => {
      qc.invalidateQueries({ queryKey: queryKeys.employeeSheets(sheet.employeeId) });
      qc.invalidateQueries({ queryKey: queryKeys.activeDraft(sheet.employeeId) });
    },
  });
}

function useSheetMutation<TArgs>(
  fn: (args: TArgs) => Promise<import("./types").ExpenseSheet>,
  // Opt out of the global error toast for call sites that show their own (and that may
  // also do non-mutation work, e.g. receipt uploads, in the same handler).
  suppressErrorToast = false,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    meta: suppressErrorToast ? { suppressErrorToast: true } : undefined,
    onSuccess: (sheet) => {
      qc.setQueryData(queryKeys.sheet(sheet.id), sheet);
      qc.invalidateQueries({ queryKey: queryKeys.employeeSheets(sheet.employeeId) });
      qc.invalidateQueries({ queryKey: queryKeys.activeDraft(sheet.employeeId) });
      qc.invalidateQueries({ queryKey: queryKeys.employeeKpis(sheet.employeeId) });
      qc.invalidateQueries({ queryKey: queryKeys.managerQueue(sheet.agencyId) });
      qc.invalidateQueries({ queryKey: queryKeys.routedSheets });
    },
  });
}

// These call sites toast their own error (and update/add also upload receipts) → opt out.
export const useUpdateSheet = () => useSheetMutation(api.updateSheet, true);
export const useAddLineItem = () => useSheetMutation(api.addLineItem, true);
export const useUpdateLineItem = () => useSheetMutation(api.updateLineItem, true);
// These rely on the global error toast.
export const useRemoveLineItem = () => useSheetMutation(api.removeLineItem);
export const useSubmitSheet = () => useSheetMutation(api.submitSheet);
export const useResubmitSheet = () => useSheetMutation(api.resubmitSheet);
export const useWithdrawSheet = () => useSheetMutation(api.withdrawSheet);

export const useAllSheets = () =>
  useQuery({ queryKey: queryKeys.allSheets, queryFn: api.getAllSheets });

// ── Manager ──
export const useManagerQueue = (agencyId: string) =>
  useQuery({ queryKey: queryKeys.managerQueue(agencyId), queryFn: () => api.getManagerQueue(agencyId) });

export function useLineItemAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.actOnLineItem,
    onSuccess: (sheet) => {
      qc.setQueryData(queryKeys.sheet(sheet.id), sheet);
      qc.invalidateQueries({ queryKey: queryKeys.managerQueue(sheet.agencyId) });
      qc.invalidateQueries({ queryKey: ["my-audit"] });
      qc.invalidateQueries({ queryKey: ["activity-log"] });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
    },
  });
}

export const useMyAuditLog = (actorId: string) =>
  useQuery({
    queryKey: queryKeys.myAuditLog(actorId),
    queryFn: () => api.getMyAuditLog(actorId),
    enabled: !!actorId,
  });

/** Per-user activity log; admin sees the whole platform, others see their own. */
export const useActivityLog = (role: Role, userId: string) =>
  useQuery({
    queryKey: queryKeys.activityLog(role, userId),
    queryFn: () => api.getActivityLog({ role, userId }),
    enabled: !!userId,
  });

export function useApproveSheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.approveSheet,
    onSuccess: (sheet) => {
      qc.invalidateQueries({ queryKey: queryKeys.managerQueue(sheet.agencyId) });
      qc.invalidateQueries({ queryKey: queryKeys.sheet(sheet.id) });
      qc.invalidateQueries({ queryKey: queryKeys.routedSheets });
      qc.invalidateQueries({ queryKey: queryKeys.allSheets });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
      qc.invalidateQueries({ queryKey: ["activity-log"] });
      qc.invalidateQueries({ queryKey: ["my-audit"] });
    },
  });
}

export function useManagerBulkApprove() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.managerBulkApprove,
    onSuccess: (sheets) => {
      sheets.forEach((s) => qc.invalidateQueries({ queryKey: queryKeys.managerQueue(s.agencyId) }));
      qc.invalidateQueries({ queryKey: queryKeys.routedSheets });
      qc.invalidateQueries({ queryKey: queryKeys.allSheets });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
      qc.invalidateQueries({ queryKey: ["activity-log"] });
      qc.invalidateQueries({ queryKey: ["my-audit"] });
    },
  });
}

// ── Finance ──
export const useRoutedSheets = () =>
  useQuery({ queryKey: queryKeys.routedSheets, queryFn: api.getRoutedSheets });

export const useFinanceKpis = () =>
  useQuery({ queryKey: queryKeys.financeKpis, queryFn: api.getFinanceKpis });

export const usePolicyDocuments = () =>
  useQuery({ queryKey: queryKeys.policyDocuments, queryFn: api.getPolicyDocuments });

export const useSpendByCategory = () =>
  useQuery({ queryKey: queryKeys.spendByCategory, queryFn: api.getSpendByCategory });

export function useFinanceOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.financeOverride,
    onSuccess: (sheet) => {
      qc.invalidateQueries({ queryKey: queryKeys.routedSheets });
      qc.invalidateQueries({ queryKey: queryKeys.sheet(sheet.id) });
      qc.invalidateQueries({ queryKey: queryKeys.allSheets });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
      qc.invalidateQueries({ queryKey: ["activity-log"] });
    },
  });
}

// ── Admin ──
// Listing all agencies is admin-only server-side; pass enabled=false for non-admins
// (e.g. Finance) so the UI never fires a guaranteed-403 request.
export const useAgencies = (enabled = true) =>
  useQuery({ queryKey: queryKeys.agencies, queryFn: api.getAgencies, enabled });

export const useBaselinePolicy = () =>
  useQuery({ queryKey: queryKeys.baselinePolicy, queryFn: api.getBaselinePolicy });

export const useAuditLog = () =>
  useQuery({ queryKey: queryKeys.auditLog, queryFn: api.getAuditLog });

export function useAssignRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.assignRole,
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.auditLog }),
  });
}

export function useAddAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.addAgency,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agencies });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
    },
  });
}

export function useUploadPolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.uploadPolicyDocument,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.policyDocuments });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
    },
  });
}

export function usePublishPolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.publishPolicyDocument,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.policyDocuments });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
    },
  });
}

// ── Notifications ──
export const useNotifications = (role: Role) =>
  useQuery({ queryKey: queryKeys.notifications(role), queryFn: () => api.getNotifications(role) });

export function useMarkNotificationsRead(role: Role) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.markNotificationsRead(role),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.notifications(role) }),
  });
}
