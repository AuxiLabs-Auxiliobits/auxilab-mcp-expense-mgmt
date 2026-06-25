"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { useAgencies, useUploadPolicy } from "@/data/hooks";
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
  const { data: agencies } = useAgencies();
  const upload = useUploadPolicy();
  const fileRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [agencyId, setAgencyId] = useState("");
  const [name, setName] = useState("");
  const [version, setVersion] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [fileName, setFileName] = useState("");

  const agencyList = agencies ?? [];
  const valid = agencyId && name.trim() && version.trim() && effectiveDate && fileName;

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const issue = fileIssue(f, baselinePolicy);
    if (issue) {
      toast.error(`${f.name}: ${issue}`);
      return;
    }
    setFileName(f.name);
  }

  async function submit() {
    const agency = agencyList.find((a) => a.id === agencyId);
    if (!agency) return;
    const doc = await upload.mutateAsync({
      agencyId,
      agencyName: agency.name,
      name: name.trim(),
      version: version.trim(),
      fileName,
      effectiveDate,
      createdBy: "sarah.okafor",
    });
    toast.success(`${doc.name} ${doc.version} uploaded`, {
      description: "Draft created — awaiting a second approver to publish (maker-checker).",
    });
    setOpen(false);
    setAgencyId("");
    setName("");
    setVersion("");
    setEffectiveDate("");
    setFileName("");
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
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="pol-name">Document Name</Label>
              <Input id="pol-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Crispin Finance Rules" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pol-version">Version</Label>
              <Input id="pol-version" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="v2.2" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pol-eff">Effective Date</Label>
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
              <span className="text-body-sm">{fileName || "Click to attach (.pdf .docx …)"}</span>
            </button>
            <input ref={fileRef} type="file" accept={baselinePolicy.allowed_extensions.join(",")} className="hidden" onChange={onPickFile} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} loading={upload.isPending} disabled={!valid}>
            Upload (Draft)
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
