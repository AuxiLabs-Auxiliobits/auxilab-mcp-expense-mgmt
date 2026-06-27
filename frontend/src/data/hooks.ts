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
  adminUsers: ["admin-users"] as const,
  baselinePolicy: ["baseline-policy"] as const,
  auditLog: ["audit-log"] as const,
  myAuditLog: (id: string) => ["my-audit", id] as const,
  activityLog: (role: Role, id: string) => ["activity-log", role, id] as const,
  notifications: (role: Role) => ["notifications", role] as const,
  myReceipts: ["my-receipts"] as const,
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

// ── Receipts & approval history (manager/finance review) ──
export const useSheetReceipts = (sheetId: string | undefined) =>
  useQuery({
    queryKey: ["sheet-receipts", sheetId ?? ""],
    queryFn: () => api.getSheetReceipts(sheetId as string),
    enabled: !!sheetId,
  });

export const useSheetDecisions = (sheetId: string | undefined) =>
  useQuery({
    queryKey: ["sheet-decisions", sheetId ?? ""],
    queryFn: () => api.getSheetDecisions(sheetId as string),
    enabled: !!sheetId,
  });

// ── Receipt library (My Receipts) — persisted unassigned uploads ──
export const useMyReceipts = () =>
  useQuery({ queryKey: queryKeys.myReceipts, queryFn: api.listMyReceipts });

export function useUploadReceiptToLibrary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.uploadReceiptToLibrary(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.myReceipts }),
  });
}

export function useDeleteLibraryReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteLibraryReceipt(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.myReceipts }),
  });
}

export function useAttachReceiptFromLibrary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.attachReceiptFromLibrary,
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.myReceipts }),
  });
}

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

/** Discard a DRAFT sheet (hard delete). Takes the sheet's id + owner so we can drop it
 *  from the caches it appears in; the DELETE itself returns no body. */
export function useDiscardDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { sheetId: string; employeeId: string }) => api.discardDraft(args.sheetId),
    onSuccess: (_void, { sheetId, employeeId }) => {
      qc.removeQueries({ queryKey: queryKeys.sheet(sheetId) });
      qc.invalidateQueries({ queryKey: queryKeys.employeeSheets(employeeId) });
      qc.invalidateQueries({ queryKey: queryKeys.activeDraft(employeeId) });
      qc.invalidateQueries({ queryKey: queryKeys.employeeKpis(employeeId) });
    },
  });
}

export const useAllSheets = (enabled = true) =>
  useQuery({ queryKey: queryKeys.allSheets, queryFn: api.getAllSheets, enabled });

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
      // Backs the manager's "Reviewed" history + the finance/admin Expense Sheets screen.
      qc.invalidateQueries({ queryKey: queryKeys.allSheets });
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

/** Role-scoped, paginated + filtered activity feed (backend scopes by token). */
export const useActivity = (params: api.ActivityParams) =>
  useQuery({
    queryKey: ["activity", params] as const,
    queryFn: () => api.getActivity(params),
    placeholderData: (prev) => prev, // keep the table stable while paging/filtering
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
    onSuccess: ({ approved }) => {
      approved.forEach((s) => qc.invalidateQueries({ queryKey: queryKeys.managerQueue(s.agencyId) }));
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
  useQuery({
    queryKey: queryKeys.auditLog,
    queryFn: api.getAuditLog,
    refetchInterval: 30_000, // live: re-poll the immutable trail every 30s
    staleTime: 0, // always considered stale so admin mutations refetch immediately
  });

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

// ── Admin: agency CRUD (rename / soft-delete) ──
export function useUpdateAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.updateAgency(id, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agencies });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
    },
  });
}

export function useDeleteAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteAgency(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agencies });
      qc.invalidateQueries({ queryKey: queryKeys.auditLog });
    },
  });
}

// ── Admin: user CRUD (onboard employee / manager / finance) ──
export const useAdminUsers = () =>
  useQuery({ queryKey: queryKeys.adminUsers, queryFn: () => api.listAdminUsers() });

function _invalidateUsers(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: queryKeys.adminUsers });
  qc.invalidateQueries({ queryKey: queryKeys.agencies }); // user counts change
  qc.invalidateQueries({ queryKey: queryKeys.auditLog });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: api.AdminUserInput) => api.createUser(input),
    onSuccess: () => _invalidateUsers(qc),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: api.AdminUserPatch }) =>
      api.updateUser(id, patch),
    onSuccess: () => _invalidateUsers(qc),
  });
}

export function useDeactivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => _invalidateUsers(qc),
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
// Near-real-time delivery via polling (Phase 4 baseline). React Query refetches every 20s
// and on window focus, so new workflow notifications appear without a manual refresh.
export const useNotifications = (role: Role) =>
  useQuery({
    queryKey: queryKeys.notifications(role),
    queryFn: () => api.getNotifications(role),
    refetchInterval: 20_000,
    refetchOnWindowFocus: true,
  });

/** Full inbox incl. archived — used by the Notification Center (keyed under the role's
 * notifications prefix so the per-item mutations' prefix-invalidation refreshes it too). */
export const useAllNotifications = (role: Role) =>
  useQuery({
    queryKey: [...queryKeys.notifications(role), "all"],
    queryFn: () => api.getNotifications(role, true),
    refetchInterval: 20_000,
    refetchOnWindowFocus: true,
  });

export function useMarkNotificationsRead(role: Role) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.markNotificationsRead(role),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.notifications(role) }),
  });
}

// Per-item notification mutations. Invalidating the role-prefixed key refreshes BOTH the
// bell (`notifications(role)`) and the center (`[...notifications(role), "all"]`).
export function useMarkOneNotificationRead(role: Role) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.markNotificationRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.notifications(role) }),
  });
}

export function useArchiveNotification(role: Role) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.archiveNotification(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.notifications(role) }),
  });
}

export function useDeleteNotification(role: Role) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteNotification(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.notifications(role) }),
  });
}

// ── Settings / preferences ──
export const usePreferences = () =>
  useQuery({ queryKey: ["preferences"], queryFn: () => api.getPreferences() });

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: api.UserPreferences) => api.updatePreferences(prefs),
    onMutate: async (prefs) => {
      await qc.cancelQueries({ queryKey: ["preferences"] });
      const prev = qc.getQueryData<api.UserPreferences>(["preferences"]);
      qc.setQueryData(["preferences"], prefs); // optimistic
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev !== undefined) qc.setQueryData(["preferences"], ctx.prev);
    },
    onSuccess: (saved) => qc.setQueryData(["preferences"], saved),
  });
}
