"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useCurrentUser, useCreateSheet } from "@/data/hooks";
import { useSessionRole } from "@/components/session-role";
import { can } from "@/lib/rbac";
import { newSheetSchema, type NewSheetValues } from "@/lib/schemas";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Reveal } from "@/components/shared/reveal";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Icon } from "@/components/ui/icon";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * Expense periods: every month of the current calendar year up to and including
 * the current month, newest first. Future months are never selectable — you
 * can't incur an expense that hasn't happened yet.
 */
function buildPeriods(now = new Date()): string[] {
  const year = now.getFullYear();
  const list: string[] = [];
  for (let m = now.getMonth(); m >= 0; m--) {
    list.push(format(new Date(year, m, 1), "MMM yyyy"));
  }
  return list;
}

function Step({
  index,
  title,
  description,
  done,
  children,
}: {
  index: number;
  title: string;
  description: string;
  done: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div
          className={
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border font-mono text-label-sm transition-colors duration-300 " +
            (done
              ? "border-primary bg-primary text-on-primary"
              : "border-outline-variant bg-surface-container-low text-on-surface-variant")
          }
          aria-hidden
        >
          {done ? <Icon name="check" className="text-[18px]" /> : index}
        </div>
        <div className="mt-2 w-px flex-1 bg-outline-variant" aria-hidden />
      </div>
      <div className="flex-1 pb-7">
        <h3 className="text-body-lg font-semibold text-on-surface">{title}</h3>
        <p className="mt-0.5 text-body-sm text-on-surface-variant">{description}</p>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}

export default function NewSheetPage() {
  const router = useRouter();
  const { sessionRole, status } = useSessionRole();
  const { data: user } = useCurrentUser("employee");
  const createSheet = useCreateSheet();

  const periods = useMemo(() => buildPeriods(), []);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<NewSheetValues>({
    resolver: zodResolver(newSheetSchema),
    defaultValues: { title: "", period: periods[0] },
  });

  const title = watch("title");
  const period = watch("period");
  const titleValid = (title?.trim().length ?? 0) >= 3;

  async function onSubmit(values: NewSheetValues) {
    if (!user) return;
    const sheet = await createSheet.mutateAsync({ ...values, employee: user });
    toast.success(`Draft ${sheet.id} created`, {
      description: "Now add line items and attachments.",
    });
    router.push(`/employee/sheets/${sheet.id}`);
  }

  // Wait for the session before deciding (avoids briefly showing the form).
  if (status === "loading") {
    return (
      <PageContainer className="max-w-5xl">
        <Skeleton className="mt-6 h-80 rounded-lg" />
      </PageContainer>
    );
  }

  // Submitting expense sheets is employee-only.
  if (!can(sessionRole, "submit_sheet")) {
    return (
      <PageContainer className="max-w-2xl">
        <Card className="mt-6">
          <EmptyState
            icon="block"
            title="Submitting expense sheets is employee-only"
            description="Your role can review and decide on sheets, but only employees create and submit them."
          >
            <Button variant="outline" className="mt-2" onClick={() => router.back()}>
              Go back
            </Button>
          </EmptyState>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer className="max-w-5xl">
      <PageHeader
        title="New Expense Sheet"
        description="Two quick steps to open a draft — then you'll add line items and attachments."
        tone="primary"
        size="xl"
      />

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        {/* ── Form (steps) ── */}
        <Reveal>
          <Card>
            <CardContent className="p-5 md:p-6">
              <form onSubmit={handleSubmit(onSubmit)}>
                <Step
                  index={1}
                  title="Name the sheet"
                  description="A clear, descriptive title makes review faster and easier to find later."
                  done={titleValid}
                >
                  <div className="space-y-2">
                    <Label htmlFor="title">Sheet Title</Label>
                    <Input
                      id="title"
                      placeholder="e.g. Q3 Engineering Offsite"
                      autoFocus
                      autoComplete="off"
                      {...register("title")}
                      aria-invalid={!!errors.title}
                      aria-describedby="title-help"
                    />
                    {errors.title ? (
                      <p className="text-label-md text-error">{errors.title.message}</p>
                    ) : (
                      <p id="title-help" className="text-body-sm text-on-surface-variant">
                        Group expenses by trip, project, or month — e.g. &ldquo;Client
                        Visit · Berlin&rdquo;.
                      </p>
                    )}
                  </div>
                </Step>

                <Step
                  index={2}
                  title="Pick the period"
                  description="The calendar month these expenses belong to. This drives the submission cutoff."
                  done={!!period}
                >
                  <div className="space-y-2">
                    <Label htmlFor="period">Expense Period</Label>
                    <Select
                      value={period}
                      onValueChange={(v) =>
                        setValue("period", v, { shouldValidate: true })
                      }
                    >
                      <SelectTrigger id="period" aria-invalid={!!errors.period}>
                        <SelectValue placeholder="Select period" />
                      </SelectTrigger>
                      <SelectContent>
                        {periods.map((p) => (
                          <SelectItem key={p} value={p}>
                            {p}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {errors.period && (
                      <p className="text-label-md text-error">{errors.period.message}</p>
                    )}
                  </div>

                  <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-outline-variant bg-surface-container-low p-3.5 text-body-sm text-on-surface-variant">
                    <Icon
                      name="schedule"
                      className="mt-px shrink-0 text-[18px] text-secondary"
                    />
                    <p>
                      Submissions must be made before the end of the calendar month in
                      which the expense was incurred (configurable month-end cutoff).
                    </p>
                  </div>
                </Step>

                <div className="flex flex-col-reverse gap-3 border-t border-outline-variant pt-5 sm:flex-row sm:items-center sm:justify-between">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => router.back()}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={isSubmitting}
                    className="sm:min-w-44"
                  >
                    {isSubmitting ? (
                      "Creating…"
                    ) : (
                      <>
                        Create draft &amp; add items
                        <Icon name="arrow_forward" className="ml-1.5 text-[18px]" />
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </Reveal>

        {/* ── Side summary / brand panel ── */}
        <Reveal delay={80} className="lg:sticky lg:top-6 lg:self-start">
          <Card className="overflow-hidden">
            <div className="border-b border-outline-variant bg-surface-container-high px-5 py-4">
              <p className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                Draft Preview
              </p>
              <p className="mt-1 text-body-lg font-semibold leading-snug text-balance text-on-surface">
                {titleValid ? title : "Untitled expense sheet"}
              </p>
            </div>

            <CardContent className="space-y-4 p-5">
              <dl className="space-y-3.5">
                <div className="flex items-center justify-between gap-4">
                  <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                    Period
                  </dt>
                  <dd className="text-body-md font-medium text-on-surface">
                    {period || "—"}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                    Status
                  </dt>
                  <dd className="text-body-md font-medium text-on-surface">Draft</dd>
                </div>
                {user && (
                  <div className="flex items-center justify-between gap-4">
                    <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                      Owner
                    </dt>
                    <dd className="truncate text-body-md font-medium text-on-surface">
                      {user.name}
                    </dd>
                  </div>
                )}
              </dl>

              <div className="border-t border-outline-variant pt-4">
                <p className="text-body-sm text-on-surface-variant">
                  After you create the draft, add line items with receipts and submit for
                  approval. Drafts stay editable until you submit them.
                </p>
              </div>

              <ul className="space-y-2">
                {[
                  "Itemize each expense with a receipt",
                  "Mismatches are flagged before approval",
                  "Withdraw or edit any time while in draft",
                ].map((tip) => (
                  <li
                    key={tip}
                    className="flex items-start gap-2 text-body-sm text-on-surface-variant"
                  >
                    <Icon
                      name="check_circle"
                      className="mt-px shrink-0 text-[16px] text-success-green"
                    />
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </Reveal>
      </div>
    </PageContainer>
  );
}
