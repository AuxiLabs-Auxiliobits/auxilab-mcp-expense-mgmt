"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Icon } from "@/components/ui/icon";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const OPTIONS = [
  { key: "light", label: "Light", icon: "light_mode" },
  { key: "dark", label: "Dark", icon: "dark_mode" },
  { key: "high-contrast", label: "High contrast", icon: "contrast" },
] as const;

const ICON: Record<string, string> = {
  light: "light_mode",
  dark: "dark_mode",
  "high-contrast": "contrast",
};

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const current = mounted ? theme ?? "light" : "light";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Theme"
        className="rounded p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
      >
        <Icon name={ICON[current] ?? "light_mode"} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {OPTIONS.map((o) => (
          <DropdownMenuItem key={o.key} onClick={() => setTheme(o.key)}>
            <Icon name={o.icon} className="text-[18px]" />
            {o.label}
            {current === o.key && (
              <Icon name="check" className="ml-auto text-[16px] text-secondary" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
