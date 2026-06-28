"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useAddAgency, useAgencies, useDeleteAgency, useUpdateAgency } from "@/data/hooks";
import { DataGrid, type Column } from "@/components/shared/data-grid";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
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
import { AGENCY_STATUS_META } from "@/lib/status";
import type { Agency, AgencyTier } from "@/data/types";

const TIERS: AgencyTier[] = ["Enterprise", "Pro", "Basic"];

export function AgencyManagement() {
  const { data, isLoading } = useAgencies();
  const addAgency = useAddAgency();
  const updateAgency = useUpdateAgency();
  const deleteAgency = useDeleteAgency();
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [tier, setTier] = useState<AgencyTier>("Pro");

  function openCreate() {
    setEditId(null);
    setName("");
    setTier("Pro");
    setOpen(true);
  }
  function openRename(a: Agency) {
    setEditId(a.id);
    setName(a.name);
    setTier(a.tier);
    setOpen(true);
  }

  async function save() {
    if (name.trim().length < 2) return;
    try {
      if (editId) {
        await updateAgency.mutateAsync({ id: editId, name: name.trim() });
        toast.success(`Renamed to ${name.trim()}`);
      } else {
        const agency = await addAgency.mutateAsync({ name: name.trim(), tier });
        toast.success(`Onboarded ${agency.name}`, { description: `${agency.id} · ${tier} tier` });
      }
      setOpen(false);
      setEditId(null);
      setName("");
      setTier("Pro");
    } catch {
      /* global toast (e.g. 409 duplicate name) */
    }
  }

  async function remove(a: Agency) {
    if (!window.confirm(`Archive agency "${a.name}"? It is soft-deleted and blocked if it has open sheets.`)) {
      return;
    }
    try {
      await deleteAgency.mutateAsync(a.id);
      toast.success(`Archived ${a.name}`);
    } catch {
      /* global toast (409 if open sheets) */
    }
  }

  const columns: Column<Agency>[] = [
    { key: "name", header: "Agency Name", render: (a) => <span className="font-medium text-primary">{a.name}</span> },
    { key: "status", header: "Status", render: (a) => <StatusBadge meta={AGENCY_STATUS_META[a.status]} /> },
    { key: "users", header: "Users", render: (a) => <span className="text-on-surface-variant">{a.userCount.toLocaleString()}</span> },
    { key: "tier", header: "Tier", render: (a) => <span className="text-on-surface-variant">{a.tier}</span> },
    {
      key: "actions",
      header: "Actions",
      align: "right",
      render: (a) => (
        <div className="flex items-center justify-end gap-1">
          <button
            onClick={() => openRename(a)}
            aria-label="Rename agency"
            className="rounded p-1.5 text-on-surface-variant hover:bg-surface-container-high hover:text-primary"
          >
            <Icon name="edit" className="text-[18px]" />
          </button>
          {(() => {
            const archiving = deleteAgency.isPending && deleteAgency.variables === a.id;
            return (
              <button
                onClick={() => remove(a)}
                disabled={archiving}
                aria-label="Archive agency"
                aria-busy={archiving || undefined}
                className="rounded p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-error disabled:pointer-events-none disabled:opacity-50"
              >
                <Icon name={archiving ? "progress_activity" : "archive"} className={`text-[18px]${archiving ? " animate-spin" : ""}`} />
              </button>
            );
          })()}
        </div>
      ),
    },
  ];

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-outline-variant bg-surface-container-lowest p-4">
        <h3 className="flex items-center gap-2 text-body-lg font-bold text-primary">
          <Icon name="domain" className="text-primary" /> Agency Management
        </h3>
        <button
          onClick={openCreate}
          className="flex items-center gap-1 text-body-sm text-primary hover:underline"
        >
          <Icon name="add" className="text-[16px]" /> Onboard Agency
        </button>
      </div>
      {isLoading ? (
        <div className="space-y-2 p-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </div>
      ) : (
        <DataGrid columns={columns} rows={data ?? []} getRowId={(a) => a.id} />
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editId ? "Rename agency" : "Onboard agency"}</DialogTitle>
            <DialogDescription>
              {editId
                ? "Update the agency name. The change is recorded in the audit log."
                : "Creates the agency and records it in the immutable audit log (§7 lifecycle)."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="agency-name">Agency Name</Label>
              <Input id="agency-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Northwind Media" />
            </div>
            {!editId && (
              <div className="space-y-1.5">
                <Label htmlFor="agency-tier">Tier</Label>
                <Select value={tier} onValueChange={(v) => setTier(v as AgencyTier)}>
                  <SelectTrigger id="agency-tier">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TIERS.map((t) => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={save}
              loading={addAgency.isPending || updateAgency.isPending}
              disabled={name.trim().length < 2}
            >
              {editId ? "Save" : "Onboard"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
