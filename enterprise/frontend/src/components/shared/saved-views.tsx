"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type SavedView<T> = { id: string; name: string; state: T };

/**
 * Saved-views control: persists the current list filter state under `storageKey`
 * (localStorage) so users can name and restore views — a ServiceNow/Jira staple.
 */
export function SavedViewsMenu<T>({
  storageKey,
  current,
  onApply,
}: {
  storageKey: string;
  current: T;
  onApply: (state: T) => void;
}) {
  const [views, setViews] = useState<SavedView<T>[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) setViews(JSON.parse(raw));
    } catch {
      /* ignore malformed storage */
    }
  }, [storageKey]);

  function persist(next: SavedView<T>[]) {
    setViews(next);
    localStorage.setItem(storageKey, JSON.stringify(next));
  }

  function save() {
    const trimmed = name.trim();
    if (!trimmed) return;
    persist([...views, { id: `${storageKey}-${views.length}-${trimmed}`, name: trimmed, state: current }]);
    setName("");
    setDialogOpen(false);
  }

  function remove(id: string) {
    persist(views.filter((v) => v.id !== id));
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <Icon name="bookmark" /> Views
            {views.length > 0 && (
              <span className="ml-0.5 rounded-full bg-surface-container-high px-1.5 font-mono text-label-sm">
                {views.length}
              </span>
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[15rem]">
          <DropdownMenuLabel>Saved views</DropdownMenuLabel>
          {views.length === 0 ? (
            <p className="px-2 py-2 text-body-sm text-on-surface-variant">No saved views yet.</p>
          ) : (
            views.map((v) => (
              <DropdownMenuItem
                key={v.id}
                onSelect={() => onApply(v.state)}
                className="justify-between gap-2"
              >
                <span className="flex items-center gap-2">
                  <Icon name="bookmark" className="text-[16px] text-secondary" />
                  {v.name}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(v.id);
                  }}
                  aria-label={`Delete view ${v.name}`}
                  className="rounded p-0.5 text-on-surface-variant transition-colors hover:text-error"
                >
                  <Icon name="close" className="text-[16px]" />
                </button>
              </DropdownMenuItem>
            ))
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setDialogOpen(true)}>
            <Icon name="add" className="text-[18px]" /> Save current view…
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Save view</DialogTitle>
          </DialogHeader>
          <div className="space-y-1.5">
            <label htmlFor="view-name" className="block text-body-sm font-medium text-on-surface">
              View name
            </label>
            <Input
              id="view-name"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Manual review · Crispin"
              onKeyDown={(e) => {
                if (e.key === "Enter") save();
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={save} disabled={!name.trim()}>
              Save view
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
