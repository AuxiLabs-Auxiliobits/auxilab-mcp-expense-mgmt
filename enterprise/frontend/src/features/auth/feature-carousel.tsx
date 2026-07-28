"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

/** A single highlighted capability shown in the auth hero. */
export interface AuthFeature {
  icon: string;
  title: string;
  description: string;
}

const DEFAULT_FEATURES: AuthFeature[] = [
  {
    icon: "auto_awesome",
    title: "AI Expense Management",
    description: "Policies are checked automatically the moment a sheet is submitted.",
  },
  {
    icon: "receipt_long",
    title: "Smart Receipt Processing",
    description: "Receipts are parsed, matched, and reconciled — no manual data entry.",
  },
  {
    icon: "fact_check",
    title: "Manager Approvals",
    description: "Agency-scoped review queues with full segregation of duties.",
  },
  {
    icon: "monitoring",
    title: "Finance Analytics",
    description: "Spend, KPIs, and SLA insights across every agency in real time.",
  },
  {
    icon: "smart_toy",
    title: "AI Assistant",
    description: "Ask about policy or your expenses in plain language, grounded in your data.",
  },
  {
    icon: "verified_user",
    title: "Secure Enterprise Platform",
    description: "RBAC, append-only audit, and encryption built in by default.",
  },
];

const ROTATE_MS = 6000;

/**
 * Auto-rotating, glassmorphism feature carousel for the login hero.
 * Pauses on hover/focus, honors reduced-motion, and exposes dot controls.
 */
export function FeatureCarousel({
  items = DEFAULT_FEATURES,
  className,
}: {
  items?: AuthFeature[];
  className?: string;
}) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  useEffect(() => {
    if (paused || reduced) return;
    const id = window.setInterval(
      () => setIndex((i) => (i + 1) % items.length),
      ROTATE_MS,
    );
    return () => window.clearInterval(id);
  }, [paused, reduced, items.length]);

  const active = items[index];

  return (
    <div
      className={cn("w-full max-w-md", className)}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      aria-roledescription="carousel"
      aria-label="Platform highlights"
    >
      <div className="glass elevate relative overflow-hidden rounded-3xl p-6 shadow-elevation-3">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-primary/20 blur-2xl"
        />
        <div
          key={index}
          className="relative flex animate-slide-up items-start gap-4"
          aria-live="polite"
        >
          <span className="flex h-12 w-12 shrink-0 animate-scale-in items-center justify-center rounded-2xl bg-primary/15 text-primary">
            <Icon name={active.icon} className="text-[26px]" />
          </span>
          <div className="min-w-0">
            <h3 className="text-body-lg font-semibold text-on-surface">{active.title}</h3>
            <p className="mt-1 text-body-sm text-on-surface-variant">{active.description}</p>
          </div>
        </div>

        {/* Auto-advance progress */}
        <div className="relative mt-5 h-1 w-full overflow-hidden rounded-full bg-on-surface-variant/15">
          <div
            key={index}
            className={cn(
              "h-full w-full rounded-full bg-primary auth-progress-bar",
              (paused || reduced) && "is-paused",
            )}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2" role="tablist" aria-label="Choose highlight">
        {items.map((it, i) => (
          <button
            key={it.title}
            type="button"
            role="tab"
            aria-selected={i === index}
            aria-label={it.title}
            onClick={() => setIndex(i)}
            className={cn(
              "h-1.5 rounded-full transition-all duration-300 ease-smooth focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              i === index
                ? "w-7 bg-primary"
                : "w-1.5 bg-on-surface-variant/30 hover:bg-on-surface-variant/60",
            )}
          />
        ))}
      </div>
    </div>
  );
}
