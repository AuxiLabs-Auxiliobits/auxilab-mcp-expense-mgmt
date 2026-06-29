"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { useTheme } from "next-themes";
import { signOut } from "next-auth/react";
import { useSessionRole } from "@/components/session-role";
import { buildCommands, GROUP_ORDER, type AppCommand } from "@/lib/command-registry";
import { bestFuzzyScore } from "@/lib/command-fuzzy";
import { rankRecent, recordCommand } from "@/lib/use-command-history";
import { broadcastLogout, setRememberMe } from "@/lib/session";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Highlight } from "@/components/command-highlight";
import { CommandSearchResults } from "@/components/command-palette-search";

export const OPEN_COMMAND_EVENT = "auxilab:open-command";

function CommandRow({
  cmd,
  query,
  onRun,
}: {
  cmd: AppCommand;
  query: string;
  onRun: (c: AppCommand) => void;
}) {
  return (
    <Command.Item
      value={cmd.id}
      keywords={cmd.keywords}
      onSelect={() => onRun(cmd)}
      className="flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-body-sm text-on-surface outline-none transition-colors data-[selected=true]:bg-surface-container-high"
    >
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-surface-container-high/60 text-on-surface-variant">
        <Icon name={cmd.icon} className="text-[17px]" />
      </span>
      <span className="min-w-0 flex-1 truncate">
        <Highlight query={query} text={cmd.label} />
      </span>
      {cmd.kind === "ai" && (
        <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-label-sm font-medium text-primary">
          AI
        </span>
      )}
      {cmd.shortcut && (
        <kbd className="shrink-0 rounded border border-outline-variant px-1.5 py-0.5 font-mono text-label-sm text-on-surface-variant">
          {cmd.shortcut}
        </kbd>
      )}
    </Command.Item>
  );
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query); // keeps typing snappy (Phase 9)
  const router = useRouter();
  const { setTheme, resolvedTheme } = useTheme();
  const { sessionRole } = useSessionRole();

  // Global activation: Ctrl/Cmd+K, plus the top-nav "Search or jump to" button event.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    function onOpenEvent() {
      setOpen(true);
    }
    document.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_COMMAND_EVENT, onOpenEvent);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_COMMAND_EVENT, onOpenEvent);
    };
  }, []);

  // Reset the query whenever the palette closes so it always opens fresh.
  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const commands = useMemo(() => buildCommands(sessionRole), [sessionRole]);
  const q = deferredQuery.trim();

  // Rank commands by fuzzy score over label + NL synonym keywords (Phase 8).
  const ranked = useMemo(() => {
    if (!q) return commands.map((c) => ({ cmd: c, score: 0 }));
    return commands
      .map((c) => ({ cmd: c, score: bestFuzzyScore(q, [c.label, ...(c.keywords ?? [])]) }))
      .filter((x) => x.score >= 0)
      .sort((a, b) => b.score - a.score);
  }, [commands, q]);

  // Group ranked commands, honoring GROUP_ORDER.
  const grouped = useMemo(() => {
    const map = new Map<string, AppCommand[]>();
    for (const { cmd } of ranked) {
      const arr = map.get(cmd.group) ?? [];
      arr.push(cmd);
      map.set(cmd.group, arr);
    }
    return GROUP_ORDER.filter((g) => map.has(g)).map((g) => [g, map.get(g)!] as const);
  }, [ranked]);

  // Recent / frequently-used commands (Phase 6) — only when there's no active query.
  const recent = useMemo(() => {
    if (q || !open) return [];
    const valid = new Set(commands.map((c) => c.id));
    const ids = rankRecent(valid, 5);
    const byId = new Map(commands.map((c) => [c.id, c]));
    return ids.map((id) => byId.get(id)!).filter(Boolean);
  }, [commands, q, open]);

  function runCommand(c: AppCommand) {
    recordCommand(c.id);
    setOpen(false);
    requestAnimationFrame(() => {
      if (c.intent === "toggle-theme") {
        setTheme(resolvedTheme === "dark" ? "light" : "dark");
      } else if (c.intent === "sign-out") {
        setRememberMe(false);
        broadcastLogout("manual");
        signOut({ redirectTo: "/login" });
      } else if (c.href) {
        router.push(c.href);
      }
    });
  }

  function navigateTo(href: string) {
    setOpen(false);
    requestAnimationFrame(() => router.push(href));
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="top-[12%] max-w-xl translate-y-0 gap-0 overflow-hidden rounded-2xl border border-outline-variant/60 bg-surface-container-lowest/80 p-0 shadow-elevation-3 backdrop-blur-2xl"
        aria-label="Command palette"
      >
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <Command shouldFilter={false} loop label="Global command palette">
          {/* Search input */}
          <div className="flex items-center gap-2.5 border-b border-outline-variant px-4">
            <Icon name="search" className="text-[18px] text-on-surface-variant" />
            <Command.Input
              autoFocus
              value={query}
              onValueChange={setQuery}
              placeholder="Search or type a command…"
              className="h-12 flex-1 bg-transparent text-body-md text-on-surface placeholder:text-on-surface-variant/60 focus:outline-none"
            />
            <kbd className="rounded border border-outline-variant px-1.5 py-0.5 font-mono text-label-sm text-on-surface-variant">
              ESC
            </kbd>
          </div>

          <Command.List className="max-h-[60vh] overflow-y-auto scroll-py-2 p-2">
            <Command.Empty className="px-2 py-10 text-center text-body-sm text-on-surface-variant">
              <Icon name="search_off" className="mb-2 block text-[28px] text-on-surface-variant/50" />
              No results for “{query}”.
            </Command.Empty>

            {/* Recents (no query) */}
            {recent.length > 0 && (
              <Command.Group
                heading="Recent"
                className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5"
              >
                {recent.map((c) => (
                  <CommandRow key={`recent-${c.id}`} cmd={c} query="" onRun={runCommand} />
                ))}
              </Command.Group>
            )}

            {/* Commands (navigation / actions / AI / system) */}
            {grouped.map(([group, items]) => (
              <Command.Group
                key={group}
                heading={group}
                className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5"
              >
                {items.map((c) => (
                  <CommandRow key={c.id} cmd={c} query={q} onRun={runCommand} />
                ))}
              </Command.Group>
            ))}

            {/* Global entity search — lazy-mounted only while querying (Phase 4/9) */}
            {q.length > 0 && (
              <CommandSearchResults role={sessionRole} query={q} onRun={navigateTo} />
            )}
          </Command.List>

          {/* Footer hints */}
          <div className="flex items-center justify-between border-t border-outline-variant px-3 py-2 text-label-md text-on-surface-variant">
            <span className="flex items-center gap-1.5">
              <kbd className="rounded border border-outline-variant px-1 font-mono">↑↓</kbd> navigate
              <kbd className="ml-2 rounded border border-outline-variant px-1 font-mono">↵</kbd> select
            </span>
            <span className="flex items-center gap-1">
              <Icon name="bolt" className="text-[14px] text-primary" /> Auxilab EM
            </span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
