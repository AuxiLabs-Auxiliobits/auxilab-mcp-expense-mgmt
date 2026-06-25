"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useCurrentUser, usePolicyDocuments, useAgencies } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { EmptyState } from "@/components/shared/empty-state";
import { Markdown } from "@/components/shared/markdown";
import { Reveal } from "@/components/shared/reveal";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDate, formatRelative } from "@/lib/format";
import { getPolicyContent } from "@/data/policy-content";
import type { AgencyPolicyDocument } from "@/data/types";

const STATUS_META: Record<string, { label: string; className: string; dot: string }> = {
  active: {
    label: "Active",
    className: "bg-success-green/10 text-success-green border border-success-green/20",
    dot: "bg-success-green",
  },
  draft: {
    label: "Draft",
    className: "bg-yellow-500/10 text-yellow-600 border border-yellow-500/20",
    dot: "bg-yellow-500",
  },
  archived: {
    label: "Archived",
    className:
      "bg-surface-container-highest text-on-surface-variant border border-outline-variant",
    dot: "bg-on-surface-variant",
  },
};

/** Stable url-safe id for an `## Heading`. */
function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

/** Extracts the level-2 (`## `) headings from a policy markdown body for the TOC. */
function extractSections(content: string | undefined): { id: string; title: string }[] {
  if (!content) return [];
  return content
    .split("\n")
    .filter((line) => /^##\s+/.test(line))
    .map((line) => {
      const title = line.replace(/^##\s+/, "").trim();
      return { id: slugify(title), title };
    });
}

export default function ManagerPolicyPage() {
  const { data: user } = useCurrentUser("manager");
  const { data: docs, isLoading } = usePolicyDocuments();
  // Listing agencies is admin-only; gate so non-admins never fire a guaranteed-403 request.
  const { data: agencies } = useAgencies(user?.role === "admin");

  const myDocs = useMemo(
    () =>
      (docs ?? [])
        .filter((d) => d.agencyId === user?.agencyId)
        .sort((a, b) => (a.status === "active" ? -1 : b.status === "active" ? 1 : 0)),
    [docs, user?.agencyId],
  );

  const [activeId, setActiveId] = useState<string | null>(null);
  const activeDoc: AgencyPolicyDocument | undefined =
    myDocs.find((d) => d.id === activeId) ?? myDocs[0];

  const agencyName =
    agencies?.find((a) => a.id === user?.agencyId)?.name ?? user?.agencyId ?? "Your agency";

  const content = activeDoc ? getPolicyContent(activeDoc.id) : undefined;
  const sections = useMemo(() => extractSections(content), [content]);

  if (isLoading) {
    return (
      <PageContainer className="max-w-6xl">
        <Skeleton className="h-32 rounded-lg" />
        <div className="mt-6 grid gap-6 lg:grid-cols-[220px_1fr]">
          <Skeleton className="hidden h-64 rounded-lg lg:block" />
          <Skeleton className="h-[28rem] rounded-lg" />
        </div>
      </PageContainer>
    );
  }

  if (myDocs.length === 0) {
    return (
      <PageContainer className="max-w-3xl">
        <header className="border-b border-outline-variant pb-6">
          <p className="font-mono text-label-sm uppercase tracking-wider text-secondary">
            {agencyName}
          </p>
          <h1 className="mt-2 text-headline-lg text-on-surface">Agency Policy</h1>
        </header>
        <Card className="mt-8">
          <EmptyState
            icon="gavel"
            title="No policy documents"
            description="Your agency has no published policy documents yet. Finance maintains these — check back once a policy is published."
          />
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer className="max-w-6xl">
      {/* Document masthead */}
      <Reveal>
        <header className="rounded-lg border border-outline-variant bg-surface-container-lowest p-gutter shadow-xs md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="font-mono text-label-sm uppercase tracking-wider text-secondary">
                {agencyName} · Travel &amp; Expense Policy
              </p>
              <h1 className="mt-2 text-balance text-headline-lg text-on-surface">
                {activeDoc?.name}
              </h1>
            </div>
            <span
              className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-outline-variant bg-surface-container-low px-3 py-1.5 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant"
              title="You can read this policy but cannot edit or delete it — Finance maintains it."
            >
              <Icon name="lock" className="text-[15px] text-secondary" />
              Read-only
            </span>
          </div>

          {/* Metadata strip */}
          <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-outline-variant pt-6 sm:grid-cols-4">
            <MetaItem label="Version" value={activeDoc?.version ?? "—"} mono />
            <MetaItem
              label="Effective"
              value={activeDoc ? formatDate(activeDoc.effectiveDate) : "—"}
            />
            <MetaItem
              label="Indexed"
              value={activeDoc ? formatRelative(activeDoc.indexedAt) : "—"}
              hint={activeDoc ? formatDate(activeDoc.indexedAt) : undefined}
            />
            <div className="min-w-0">
              <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                Status
              </dt>
              <dd className="mt-1">
                {activeDoc && (
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-label-md font-medium",
                      (STATUS_META[activeDoc.status] ?? STATUS_META.archived).className,
                    )}
                  >
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        (STATUS_META[activeDoc.status] ?? STATUS_META.archived).dot,
                      )}
                    />
                    {(STATUS_META[activeDoc.status] ?? STATUS_META.archived).label}
                  </span>
                )}
              </dd>
            </div>
          </dl>

          {/* Version switcher (only when the agency has more than one document) */}
          {myDocs.length > 1 && (
            <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-outline-variant pt-5">
              <span className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                Documents
              </span>
              {myDocs.map((doc) => {
                const selected = doc.id === activeDoc?.id;
                return (
                  <button
                    key={doc.id}
                    type="button"
                    onClick={() => setActiveId(doc.id)}
                    aria-pressed={selected}
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-body-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                      selected
                        ? "border-primary bg-primary text-on-primary"
                        : "border-outline-variant bg-surface text-on-surface-variant hover:bg-surface-container-low",
                    )}
                  >
                    {doc.version}
                  </button>
                );
              })}
            </div>
          )}
        </header>
      </Reveal>

      {/* Reading area: sticky TOC + document body */}
      <div className="mt-8 grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)]">
        {/* Table of contents (desktop) */}
        {sections.length > 0 && (
          <aside className="hidden lg:block">
            <nav
              aria-label="Sections in this policy"
              className="sticky top-24 space-y-1"
            >
              <p className="mb-3 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                On this page
              </p>
              {sections.map((s) => (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  className="block rounded-md border-l-2 border-transparent py-1.5 pl-3 text-body-sm text-on-surface-variant transition-colors hover:border-secondary hover:bg-surface-container-low hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  {s.title}
                </a>
              ))}
            </nav>
          </aside>
        )}

        {/* Document body */}
        <Reveal delay={80} className="min-w-0">
          <article className="rounded-lg border border-outline-variant bg-surface-container-lowest shadow-xs">
            {content ? (
              <PolicyBody content={content} />
            ) : (
              <div className="flex flex-col items-center gap-3 px-gutter py-16 text-center text-on-surface-variant">
                <Icon name="description" className="text-[32px] text-secondary" />
                <p className="text-body-md">
                  A readable preview isn&apos;t available for this version.
                </p>
                <p className="max-w-sm text-body-sm">
                  This document is indexed for the AI approver, but its extracted text
                  isn&apos;t published for in-app reading.
                </p>
              </div>
            )}
          </article>

          <p className="mt-4 flex items-center gap-2 font-mono text-label-sm text-on-surface-variant">
            <Icon name="auto_awesome" className="text-[14px] text-secondary" />
            This is the source the AI approver applies to {agencyName} expense reports ·
            RAG-indexed
          </p>
        </Reveal>
      </div>
    </PageContainer>
  );
}

function MetaItem({
  label,
  value,
  hint,
  mono,
}: {
  label: string;
  value: string;
  hint?: string;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
        {label}
      </dt>
      <dd
        className={cn(
          "mt-1 truncate text-body-md font-semibold text-on-surface",
          mono && "font-mono",
        )}
        title={hint ?? value}
      >
        {value}
      </dd>
    </div>
  );
}

/**
 * Renders the policy markdown with a generous reading measure (max-w-prose).
 *
 * The shared <Markdown> renderer doesn't emit heading ids, so after mount we walk the
 * rendered `h2` elements and assign slug ids matching the TOC, plus a scroll offset for
 * the sticky header. This keeps the shared component untouched while enabling deep-links.
 */
function PolicyBody({ content }: { content: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    root.querySelectorAll("h2").forEach((h) => {
      const id = slugify(h.textContent ?? "");
      if (id) {
        h.id = id;
        h.style.scrollMarginTop = "6rem";
      }
    });
  }, [content]);

  return (
    <div ref={ref} className="px-gutter py-8 md:px-10 md:py-10">
      <div className="max-w-prose">
        <Markdown content={content} className="text-body-md leading-relaxed" />
      </div>
    </div>
  );
}
