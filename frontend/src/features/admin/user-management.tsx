"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  useAdminUsers,
  useAgencies,
  useCreateUser,
  useDeactivateUser,
  useUpdateUser,
} from "@/data/hooks";
import { DataGrid, type Column } from "@/components/shared/data-grid";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ROLE_LABELS, type Role, type User } from "@/data/types";
import { formatDateTimeIST, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

const MANAGED_ROLES: Role[] = ["employee", "manager", "finance", "admin"];
const AGENCY_ROLES: Role[] = ["employee", "manager", "finance"];
const ROLE_TABS: { key: Role; label: string }[] = [
  { key: "employee", label: "Employees" },
  { key: "manager", label: "Managers" },
  { key: "finance", label: "Finance" },
];

interface FormState {
  id?: string;
  name: string;
  email: string;
  role: Role;
  agencyId: string;
  password: string;
}

const EMPTY: FormState = { name: "", email: "", role: "employee", agencyId: "", password: "" };

export function UserManagement({ view = "all" }: { view?: "all" | "agency" | "admins" }) {
  const { data: users, isLoading, isError } = useAdminUsers();
  const { data: agencies } = useAgencies();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deactivate = useDeactivateUser();

  const activeAgencies = useMemo(() => (agencies ?? []).filter((a) => a.status === "active"), [agencies]);

  const [selectedAgencyId, setSelectedAgencyId] = useState<string>("");
  const [roleTab, setRoleTab] = useState<Role>("employee");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY);
  const editing = !!form.id;

  // Pick the first agency once loaded
  const currentAgencyId = selectedAgencyId || activeAgencies[0]?.id || "";
  const currentAgency = activeAgencies.find((a) => a.id === currentAgencyId);

  const agencyUsers = useMemo(() => {
    if (!currentAgencyId) return [];
    return (users ?? []).filter((u) => u.agencyId === currentAgencyId && u.role === roleTab);
  }, [users, currentAgencyId, roleTab]);

  const adminUsers = useMemo(() => (users ?? []).filter((u) => u.role === "admin"), [users]);

  function openCreate(defaultRole: Role = "employee", defaultAgencyId?: string) {
    setForm({ ...EMPTY, role: defaultRole, agencyId: defaultAgencyId ?? currentAgencyId });
    setOpen(true);
  }
  function openEdit(u: User) {
    setForm({ id: u.id, name: u.name, email: u.email, role: u.role, agencyId: u.agencyId ?? "", password: "" });
    setOpen(true);
  }

  const needsAgency = form.role !== "admin";
  const passwordOk = editing
    ? !form.password || form.password.length >= 10  // optional in edit; if provided must be ≥10
    : form.password.length >= 10;                   // required on create
  const valid =
    form.name.trim().length >= 2 &&
    /.+@.+\..+/.test(form.email) &&
    (!needsAgency || !!form.agencyId) &&
    passwordOk;

  async function save() {
    if (!valid) return;
    try {
      if (editing && form.id) {
        await updateUser.mutateAsync({
          id: form.id,
          patch: {
            name: form.name.trim(),
            email: form.email.trim().toLowerCase(),
            role: form.role,
            agencyId: needsAgency ? form.agencyId : undefined,
            ...(form.password ? { password: form.password } : {}),
          },
        });
        toast.success(`Updated ${form.name}`);
      } else {
        await createUser.mutateAsync({
          name: form.name.trim(),
          email: form.email.trim().toLowerCase(),
          role: form.role,
          password: form.password,
          agencyId: needsAgency ? form.agencyId : undefined,
        });
        toast.success(`Onboarded ${form.name} as ${ROLE_LABELS[form.role]}`);
      }
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save changes. Please try again.");
    }
  }

  async function toggleActive(u: User) {
    try {
      if (u.isActive) {
        await deactivate.mutateAsync(u.id);
        toast.success(`Deactivated ${u.name}`);
      } else {
        await updateUser.mutateAsync({ id: u.id, patch: { isActive: true } });
        toast.success(`Reactivated ${u.name}`);
      }
    } catch {
      // Global error toast is already handled by the shared query client.
    }
  }

  const userColumns: Column<User>[] = [
    {
      key: "name",
      header: "Name",
      render: (u) => (
        <div className="flex flex-col">
          <span className="font-medium text-on-surface">{u.name}</span>
          <span className="text-label-md text-on-surface-variant">{u.email}</span>
        </div>
      ),
    },
    {
      key: "joined",
      header: "Joined (IST)",
      render: (u) =>
        u.createdAt ? (
          <span
            className="font-mono text-label-md text-on-surface-variant"
            title={formatRelative(u.createdAt)}
          >
            {formatDateTimeIST(u.createdAt)}
          </span>
        ) : (
          <span className="text-on-surface-variant">—</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      render: (u) => (
        <span className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-label-md",
          u.isActive ? "bg-success-green/10 text-success-green" : "bg-error-container text-error",
        )}>
          <span className={cn("h-1.5 w-1.5 rounded-full", u.isActive ? "bg-success-green" : "bg-error")} />
          {u.isActive ? "Active" : "Inactive"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      align: "right",
      render: (u) => (
        <div className="flex items-center justify-end gap-1">
          <button onClick={() => openEdit(u)} aria-label="Edit user"
            className="rounded p-1.5 text-on-surface-variant hover:bg-surface-container-high hover:text-primary">
            <Icon name="edit" className="text-[18px]" />
          </button>
          <button onClick={() => toggleActive(u)} aria-label={u.isActive ? "Deactivate" : "Reactivate"}
            className={cn("rounded p-1.5 hover:bg-surface-container-high",
              u.isActive ? "text-on-surface-variant hover:text-error" : "text-on-surface-variant hover:text-success-green")}>
            <Icon name={u.isActive ? "person_off" : "person"} className="text-[18px]" />
          </button>
        </div>
      ),
    },
  ];

  const adminColumns: Column<User>[] = [
    {
      key: "name",
      header: "Name",
      render: (u) => (
        <div className="flex flex-col">
          <span className="font-medium text-on-surface">{u.name}</span>
          <span className="text-label-md text-on-surface-variant">{u.email}</span>
        </div>
      ),
    },
    {
      key: "scope",
      header: "Scope",
      render: () => <span className="text-on-surface-variant">All agencies</span>,
    },
    {
      key: "joined",
      header: "Joined (IST)",
      render: (u) =>
        u.createdAt ? (
          <span
            className="font-mono text-label-md text-on-surface-variant"
            title={formatRelative(u.createdAt)}
          >
            {formatDateTimeIST(u.createdAt)}
          </span>
        ) : (
          <span className="text-on-surface-variant">—</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      render: (u) => (
        <span className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-label-md",
          u.isActive ? "bg-success-green/10 text-success-green" : "bg-error-container text-error",
        )}>
          <span className={cn("h-1.5 w-1.5 rounded-full", u.isActive ? "bg-success-green" : "bg-error")} />
          {u.isActive ? "Active" : "Inactive"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      align: "right",
      render: (u) => (
        <div className="flex items-center justify-end gap-1">
          <button onClick={() => openEdit(u)} aria-label="Edit user"
            className="rounded p-1.5 text-on-surface-variant hover:bg-surface-container-high hover:text-primary">
            <Icon name="edit" className="text-[18px]" />
          </button>
          <button onClick={() => toggleActive(u)} aria-label={u.isActive ? "Deactivate" : "Reactivate"}
            className={cn("rounded p-1.5 hover:bg-surface-container-high",
              u.isActive ? "text-on-surface-variant hover:text-error" : "text-on-surface-variant hover:text-success-green")}>
            <Icon name={u.isActive ? "person_off" : "person"} className="text-[18px]" />
          </button>
        </div>
      ),
    },
  ];

  const agencyCard = (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant bg-surface-container-lowest p-4">
        <h3 className="flex items-center gap-2 text-body-lg font-bold text-primary">
          <Icon name="group" className="text-primary" /> User Management
        </h3>
        <Button onClick={() => openCreate(roleTab, currentAgencyId)} size="sm">
          <Icon name="person_add" className="text-[18px]" /> Add user
        </Button>
      </div>

      <div className="border-b border-outline-variant bg-surface-container-lowest px-4 py-3">
        <div className="flex items-center gap-3">
          <Icon name="business" className="shrink-0 text-[18px] text-on-surface-variant" />
          <Select
            value={currentAgencyId}
            onValueChange={(v) => { setSelectedAgencyId(v); setRoleTab("employee"); }}
          >
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Select agency…" />
            </SelectTrigger>
            <SelectContent>
              {activeAgencies.map((a) => (
                <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {currentAgency && (
            <span className="text-label-md text-on-surface-variant">
              {(users ?? []).filter((u) => u.agencyId === currentAgencyId && AGENCY_ROLES.includes(u.role)).length} members
            </span>
          )}
        </div>
      </div>

      <div className="flex gap-1 border-b border-outline-variant px-4 pt-3 pb-0">
        {ROLE_TABS.map((t) => {
          const count = (users ?? []).filter((u) => u.agencyId === currentAgencyId && u.role === t.key).length;
          return (
            <button
              key={t.key}
              onClick={() => setRoleTab(t.key)}
              className={cn(
                "flex items-center gap-1.5 rounded-t-md px-4 py-2 text-label-md font-medium transition-colors",
                roleTab === t.key
                  ? "border-b-2 border-primary bg-primary/5 text-primary"
                  : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
              )}
            >
              {t.label}
              <span className={cn(
                "rounded-full px-1.5 py-0.5 text-label-sm",
                roleTab === t.key ? "bg-primary/15 text-primary" : "bg-surface-container-high text-on-surface-variant",
              )}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <div className="space-y-2 p-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}
        </div>
      ) : isError ? (
        <div className="p-8 text-center text-body-sm text-error">Couldn&apos;t load users. Please retry.</div>
      ) : (
        <DataGrid
          columns={userColumns}
          rows={agencyUsers}
          getRowId={(u) => u.id}
          emptyMessage={`No ${ROLE_LABELS[roleTab].toLowerCase()}s in ${currentAgency?.name ?? "this agency"}.`}
        />
      )}
    </Card>
  );

  const adminsCard = (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant bg-surface-container-lowest p-4">
        <h3 className="flex items-center gap-2 text-body-lg font-bold text-secondary">
          <Icon name="admin_panel_settings" className="text-secondary" /> Platform Admins
        </h3>
        <Button variant="outline" onClick={() => openCreate("admin")} size="sm">
          <Icon name="person_add" className="text-[18px]" /> Add admin
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2 p-3">
          {[0, 1].map((i) => <Skeleton key={i} className="h-12" />)}
        </div>
      ) : (
        <DataGrid
          columns={adminColumns}
          rows={adminUsers}
          getRowId={(u) => u.id}
          emptyMessage="No platform admins."
        />
      )}
    </Card>
  );

  return (
    <div className="space-y-4">
      {(view === "all" || view === "agency") && agencyCard}
      {(view === "all" || view === "admins") && adminsCard}

      {/* ── Create / edit dialog ── */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit user" : "Onboard a user"}</DialogTitle>
            <DialogDescription>
              {editing ? "Update the user's details, role, or agency." : "Create an employee, manager, finance reviewer, or admin."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="u-name">Full name</Label>
              <Input id="u-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Jane Doe" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="u-email">Email</Label>
              <Input id="u-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="jane@agency.com" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v as Role, agencyId: v === "admin" ? "" : form.agencyId })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {MANAGED_ROLES.map((r) => (
                      <SelectItem key={r} value={r}>{ROLE_LABELS[r]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Agency</Label>
                <Select value={form.agencyId} onValueChange={(v) => setForm({ ...form, agencyId: v })} disabled={!needsAgency}>
                  <SelectTrigger><SelectValue placeholder={needsAgency ? "Select…" : "All agencies"} /></SelectTrigger>
                  <SelectContent>
                    {activeAgencies.map((a) => (
                      <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="u-pass">{editing ? "Reset password (optional)" : "Temporary password"}</Label>
              <Input
                id="u-pass"
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder={editing ? "Leave blank to keep current" : "Min 10 chars, upper/lower/number"}
                autoComplete="new-password"
                className={cn(!passwordOk && form.password ? "border-error" : "")}
              />
              {form.password && !passwordOk ? (
                <p className="text-label-sm text-error">Password must be at least 10 characters.</p>
              ) : editing ? (
                <p className="text-label-sm text-on-surface-variant">Leave blank to keep the current password.</p>
              ) : (
                <p className="text-label-sm text-on-surface-variant">
                  Local sign-in. Azure SSO users sign in with Microsoft instead.
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={!valid || createUser.isPending || updateUser.isPending}>
              {editing ? "Save changes" : "Create user"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
