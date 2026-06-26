"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { useAgencies, useCurrentUser, useUploadPolicy } from "@/data/hooks";
import { baselinePolicy } from "@/data/mock";
import { fileIssue } from "@/lib/intake";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function PolicyUploadDialog({ trigger }: { trigger: React.ReactNode }) {
  const { data: user } = useCurrentUser("finance");
  const isAdmin = user?.role === "admin";
  // Admins manage any agency (list endpoint is admin-only); Finance only their own,
  // so they never hit /admin/agencies — their agency comes from the session.
  const { data: agencies } = useAgencies(isAdmin);
  const upload = useUploadPolicy();
  const fileRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [agencyId, setAgencyId] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const agencyList =
    agencies ?? (user?.agencyId ? [{ id: user.agencyId, name: user.agencyName ?? "My agency" }] : []);
  // The endpoint needs an agency + a file; the version is auto-assigned and the effective
  // date is optional, so they don't gate submission.
  const valid = !!agencyId && !!file;

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const issue = fileIssue(f, baselinePolicy);
    if (issue) {
      toast.error(`${f.name}: ${issue}`);
      return;
    }
    setFile(f);
  }

  async function submit() {
    const agency = agencyList.find((a) => a.id === agencyId);
    if (!agency || !file) return;
    const doc = await upload.mutateAsync({
      agencyId,
      agencyName: agency.name,
      file,
      effectiveDate: effectiveDate || undefined,
      createdBy: user?.id ?? "",
    });
    toast.success(`${doc.name} ${doc.version} uploaded`, {
      description: "Draft created — awaiting a second approver to publish (maker-checker).",
    });
    setOpen(false);
    setAgencyId("");
    setEffectiveDate("");
    setFile(null);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update policy document</DialogTitle>
          <DialogDescription>
            Upload a new agency policy version. It is virus-scanned and extracted, then held
            as a draft until a different approver publishes it (maker-checker, §7).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="pol-agency">Agency</Label>
            <Select value={agencyId} onValueChange={setAgencyId}>
              <SelectTrigger id="pol-agency">
                <SelectValue placeholder="Select agency" />
              </SelectTrigger>
              <SelectContent>
                {agencyList.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pol-eff">Effective Date (optional)</Label>
            <Input id="pol-eff" type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Policy File</Label>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="flex w-full items-center gap-2 rounded border border-dashed border-outline-variant bg-surface-container-low px-4 py-3 text-on-surface-variant hover:border-secondary hover:text-primary"
            >
              <Icon name="upload_file" className="text-[20px]" />
              <span className="text-body-sm">{file?.name || "Click to attach (.pdf .docx …)"}</span>
            </button>
            <input ref={fileRef} type="file" accept={baselinePolicy.allowed_extensions.join(",")} className="hidden" onChange={onPickFile} />
            <p className="text-label-sm text-on-surface-variant">
              The version is assigned automatically (next version for the agency). The file is stored
              in the policy storage account, then indexed for RAG once a second approver publishes it.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid} loading={upload.isPending}>
            Upload (Draft)
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
