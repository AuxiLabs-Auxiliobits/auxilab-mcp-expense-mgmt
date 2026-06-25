"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useAddAgency, useAgencies } from "@/data/hooks";
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
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [tier, setTier] = useState<AgencyTier>("Pro");

  async function onboard() {
    if (name.trim().length < 2) return;
    const agency = await addAgency.mutateAsync({ name: name.trim(), tier });
    toast.success(`Onboarded ${agency.name}`, { description: `${agency.id} · ${tier} tier` });
    setOpen(false);
    setName("");
    setTier("Pro");
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
      render: () => (
        <button className="text-on-surface-variant opacity-0 transition-opacity hover:text-primary group-hover:opacity-100">
          <Icon name="edit" className="text-[18px]" />
        </button>
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
          onClick={() => setOpen(true)}
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
            <DialogTitle>Onboard agency</DialogTitle>
            <DialogDescription>
              Creates the agency and records it in the immutable audit log (§7 lifecycle).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="agency-name">Agency Name</Label>
              <Input id="agency-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Northwind Media" />
            </div>
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
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={onboard} loading={addAgency.isPending} disabled={name.trim().length < 2}>
              Onboard
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
