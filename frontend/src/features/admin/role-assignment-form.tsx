"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAssignRole } from "@/data/hooks";
import { roleAssignmentSchema, type RoleAssignmentValues } from "@/lib/schemas";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ROLE_LABELS, type Role } from "@/data/types";

const ROLES: Role[] = ["employee", "manager", "finance", "admin"];

export function RoleAssignmentForm() {
  const assignRole = useAssignRole();
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<RoleAssignmentValues>({
    resolver: zodResolver(roleAssignmentSchema),
    defaultValues: { email: "", role: "employee" },
  });

  async function onSubmit(values: RoleAssignmentValues) {
    await assignRole.mutateAsync(values);
    toast.success("Access granted", {
      description: `${values.email} → ${ROLE_LABELS[values.role]} (logged to audit).`,
    });
    reset();
  }

  return (
    <Card className="p-5">
      <h3 className="mb-4 flex items-center gap-2 text-body-lg font-bold text-primary">
        <Icon name="manage_accounts" className="text-primary" /> Quick Role Assignment
      </h3>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-1">
          <Label htmlFor="role-email">User Email</Label>
          <Input id="role-email" type="email" placeholder="user@agency.com" {...register("email")} />
          {errors.email && <p className="text-label-md text-error">{errors.email.message}</p>}
        </div>
        <div className="space-y-1">
          <Label htmlFor="role-select">Assign Role</Label>
          <Select
            value={watch("role")}
            onValueChange={(v) => setValue("role", v as Role, { shouldValidate: true })}
          >
            <SelectTrigger id="role-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROLES.map((r) => (
                <SelectItem key={r} value={r}>
                  {ROLE_LABELS[r]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Granting…" : "Grant Access"}
        </Button>
      </form>
    </Card>
  );
}
