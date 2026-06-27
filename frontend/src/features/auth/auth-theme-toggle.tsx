"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { key: "light", icon: "light_mode", label: "Light" },
  { key: "dark", icon: "dark_mode", label: "Dark" },
] as const;

/**
 * Inline segmented theme switcher (light / system / dark) for the auth screen.
 * Preference is persisted by next-themes; mounted-guard avoids hydration flicker.
 */
export function AuthThemeToggle({ className }: { className?: string }) {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const current = mounted ? resolvedTheme ?? "light" : "light";

  return (
    <div
      role="radiogroup"
      aria-label="Color theme"
      className={cn("glass inline-flex items-center gap-0.5 rounded-full p-1", className)}
    >
      {OPTIONS.map((o) => {
        const isActive = current === o.key;
        return (
          <button
            key={o.key}
            type="button"
            role="radio"
            aria-checked={isActive}
            aria-label={o.label}
            title={o.label}
            onClick={() => setTheme(o.key)}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-full transition-all duration-200 ease-smooth focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary",
              isActive
                ? "bg-primary text-on-primary shadow-sm"
                : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface",
            )}
          >
            <Icon name={o.icon} className="text-[18px]" />
          </button>
        );
      })}
    </div>
  );
}
