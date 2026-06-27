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
import { Badge } from "@/components/ui/badge";
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
import { cn } from "@/lib/utils";

const MANAGED_ROLES: Role[] = ["employee", "manager", "finance", "admin"];
const FILTERS: { key: "all" | Role; label: string }[] = [
  { key: "all", label: "All" },
  { key: "employee", label: "Employees" },
  { key: "manager", label: "Managers" },
  { key: "finance", label: "Finance" },
  { key: "admin", label: "Admins" },
];

interface FormState {
  id?: string; // present → editing
  name: string;
  email: string;
  role: Role;
  agencyId: string;
  password: string;
}

const EMPTY: FormState = { name: "", email: "", role: "employee", agencyId: "", password: "" };

export function UserManagement() {
  const { data: users, isLoading, isError } = useAdminUsers();
  const { data: agencies } = useAgencies();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deactivate = useDeactivateUser();

  const [filter, setFilter] = useState<"all" | Role>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY);
  const editing = !!form.id;

  const agencyName = useMemo(() => {
    const m = new Map((agencies ?? []).map((a) => [a.id, a.name]));
    return (id?: string) => (id ? m.get(id) ?? "—" : "—");
  }, [agencies]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (users ?? [])
      .filter((u) => filter === "all" || u.role === filter)
      .filter((u) => !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));
  }, [users, filter, query]);

  function openCreate() {
    setForm({ ...EMPTY, agencyId: agencies?.[0]?.id ?? "" });
    setOpen(true);
  }
  function openEdit(u: User) {
    setForm({ id: u.id, name: u.name, email: u.email, role: u.role, agencyId: u.agencyId, password: "" });
    setOpen(true);
  }

  const needsAgency = form.role !== "admin";
  const valid =
    form.name.trim().length >= 2 &&
    /.+@.+\..+/.test(form.email) &&
    (!needsAgency || !!form.agencyId) &&
    (editing || form.password.length >= 10);

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
    } catch {
      /* global toast surfaces the error */
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
      /* global toast */
    }
  }

  const columns: Column<User>[] = [
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
      key: "role",
      header: "Role",
      render: (u) => <Badge>{ROLE_LABELS[u.role]}</Badge>,
    },
    {
      key: "agency",
      header: "Agency",
      render: (u) => (
        <span className="text-on-surface-variant">
          {u.role === "admin" ? "All agencies" : agencyName(u.agencyId)}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (u) => (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-label-md",
            u.isActive ? "bg-success-green/10 text-success-green" : "bg-error-container text-error",
          )}
        >
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
          <button
            onClick={() => openEdit(u)}
            aria-label="Edit user"
            className="rounded p-1.5 text-on-surface-variant hover:bg-surface-container-high hover:text-primary"
          >
            <Icon name="edit" className="text-[18px]" />
          </button>
          <button
            onClick={() => toggleActive(u)}
            aria-label={u.isActive ? "Deactivate user" : "Reactivate user"}
            className={cn(
              "rounded p-1.5 hover:bg-surface-container-high",
              u.isActive ? "text-on-surface-variant hover:text-error" : "text-on-surface-variant hover:text-success-green",
            )}
          >
            <Icon name={u.isActive ? "person_off" : "person"} className="text-[18px]" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant bg-surface-container-lowest p-4">
        <h3 className="flex items-center gap-2 text-body-lg font-bold text-primary">
          <Icon name="group" className="text-primary" /> User Management
        </h3>
        <Button onClick={openCreate} size="sm">
          <Icon name="person_add" className="text-[18px]" /> Add user
        </Button>
      </div>

      {/* Filters + search */}
      <div className="flex flex-wrap items-center gap-2 border-b border-outline-variant p-3">
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                "rounded-full px-3 py-1 text-label-md transition-colors",
                filter === f.key
                  ? "bg-primary text-on-primary"
                  : "text-on-surface-variant hover:bg-surface-container-high",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative ml-auto w-full sm:w-64">
          <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name or email…"
            className="pl-9"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2 p-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : isError ? (
        <div className="p-8 text-center text-body-sm text-error">
          Couldn&apos;t load users. Please retry.
        </div>
      ) : (
        <DataGrid columns={columns} rows={rows} getRowId={(u) => u.id} emptyMessage="No users match." />
      )}

      {/* Create / edit dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit user" : "Onboard a user"}</DialogTitle>
            <DialogDescription>
              {editing
                ? "Update the user's details, role, or agency."
                : "Create an employee, manager, finance reviewer, or admin."}
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
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v as Role })}>
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
                <Select
                  value={form.agencyId}
                  onValueChange={(v) => setForm({ ...form, agencyId: v })}
                  disabled={!needsAgency}
                >
                  <SelectTrigger><SelectValue placeholder={needsAgency ? "Select…" : "All agencies"} /></SelectTrigger>
                  <SelectContent>
                    {(agencies ?? []).map((a) => (
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
              />
              {!editing && (
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
    </Card>
  );
}
