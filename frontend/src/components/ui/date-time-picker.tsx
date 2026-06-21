"use client";

import * as React from "react";
import {
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  parse,
  parseISO,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { Button } from "./button";
import { Icon } from "./icon";
import { cn } from "@/lib/utils";

type Mode = "date" | "datetime";

interface DateTimePickerProps {
  value?: string;
  onChange: (value: string) => void;
  mode?: Mode;
  id?: string;
  placeholder?: string;
}

const DEMO_TODAY = new Date(2026, 5, 14);
const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function parseValue(value: string | undefined, mode: Mode): Date | null {
  if (!value) return null;
  try {
    const d = mode === "datetime" ? parseISO(value) : parse(value, "yyyy-MM-dd", new Date());
    return Number.isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}

export function DateTimePicker({
  value,
  onChange,
  mode = "datetime",
  id,
  placeholder = "Select…",
}: DateTimePickerProps) {
  const [open, setOpen] = React.useState(false);
  const parsed = parseValue(value, mode);
  const [view, setView] = React.useState<Date>(parsed ?? DEMO_TODAY);
  const [draft, setDraft] = React.useState<Date | null>(parsed);

  // Re-sync from the incoming value each time the popover opens.
  React.useEffect(() => {
    if (open) {
      const p = parseValue(value, mode);
      setDraft(p);
      setView(p ?? DEMO_TODAY);
    }
  }, [open, value, mode]);

  const days = eachDayOfInterval({
    start: startOfWeek(startOfMonth(view)),
    end: endOfWeek(endOfMonth(view)),
  });

  const hours12 = draft ? draft.getHours() % 12 || 12 : 12;
  const minutes = draft ? draft.getMinutes() : 0;
  const ampm = draft ? (draft.getHours() < 12 ? "AM" : "PM") : "AM";

  function pickDay(day: Date) {
    const next = new Date(day);
    if (mode === "datetime") {
      const base = draft ?? DEMO_TODAY;
      next.setHours(base.getHours(), base.getMinutes(), 0, 0);
    }
    setDraft(next);
  }

  function setTime(h12: number, m: number, ap: "AM" | "PM") {
    const base = draft ?? DEMO_TODAY;
    const h24 = (h12 % 12) + (ap === "PM" ? 12 : 0);
    const next = new Date(base);
    next.setHours(h24, m, 0, 0);
    setDraft(next);
  }

  function commit() {
    if (!draft) {
      onChange("");
    } else {
      onChange(format(draft, mode === "datetime" ? "yyyy-MM-dd'T'HH:mm" : "yyyy-MM-dd"));
    }
    setOpen(false);
  }

  const display = parsed
    ? format(parsed, mode === "datetime" ? "MMM d, yyyy · h:mm a" : "MMM d, yyyy")
    : "";

  const selectClass =
    "rounded border border-outline-variant bg-surface-container-lowest px-2 py-1 text-body-sm focus:border-secondary focus:outline-none focus:ring-1 focus:ring-secondary";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          id={id}
          type="button"
          className="flex h-9 w-full min-w-0 items-center justify-between gap-2 rounded border border-outline-variant bg-surface-container-lowest px-3 text-left text-body-sm text-on-surface focus:border-secondary focus:outline-none focus:ring-1 focus:ring-secondary"
        >
          <span className={cn("truncate", !display && "text-on-surface-variant/60")}>
            {display || placeholder}
          </span>
          <Icon
            name={mode === "datetime" ? "event" : "calendar_today"}
            className="shrink-0 text-[18px] text-on-surface-variant"
          />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0">
        <div className="flex flex-col sm:flex-row">
          {/* Calendar */}
          <div className="p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-body-sm font-semibold text-on-surface">
                {format(view, "MMMM yyyy")}
              </span>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setView((v) => addMonths(v, -1))}
                  className="rounded p-1 text-on-surface-variant hover:bg-surface-container-low hover:text-primary"
                  aria-label="Previous month"
                >
                  <Icon name="chevron_left" className="text-[18px]" />
                </button>
                <button
                  type="button"
                  onClick={() => setView((v) => addMonths(v, 1))}
                  className="rounded p-1 text-on-surface-variant hover:bg-surface-container-low hover:text-primary"
                  aria-label="Next month"
                >
                  <Icon name="chevron_right" className="text-[18px]" />
                </button>
              </div>
            </div>
            <div className="grid grid-cols-7 gap-0.5">
              {WEEKDAYS.map((w) => (
                <div key={w} className="py-1 text-center font-mono text-label-sm text-on-surface-variant">
                  {w}
                </div>
              ))}
              {days.map((day) => {
                const selected = draft && isSameDay(day, draft);
                const today = isSameDay(day, DEMO_TODAY);
                const outside = !isSameMonth(day, view);
                return (
                  <button
                    key={day.toISOString()}
                    type="button"
                    onClick={() => pickDay(day)}
                    className={cn(
                      "h-8 w-8 rounded text-body-sm transition-colors",
                      outside && "text-on-surface-variant/40",
                      !selected && "hover:bg-surface-container-low",
                      selected && "bg-secondary font-semibold text-on-secondary",
                      !selected && today && "ring-1 ring-secondary",
                    )}
                  >
                    {format(day, "d")}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Time */}
          {mode === "datetime" && (
            <div className="flex flex-col justify-center gap-2 border-t border-outline-variant p-3 sm:border-l sm:border-t-0">
              <span className="font-mono text-label-sm uppercase tracking-wide text-on-surface-variant">
                Time
              </span>
              <div className="flex items-center gap-1.5">
                <select
                  className={selectClass}
                  value={hours12}
                  onChange={(e) => setTime(Number(e.target.value), minutes, ampm)}
                  aria-label="Hour"
                >
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((h) => (
                    <option key={h} value={h}>
                      {String(h).padStart(2, "0")}
                    </option>
                  ))}
                </select>
                <span className="text-on-surface-variant">:</span>
                <select
                  className={selectClass}
                  value={minutes}
                  onChange={(e) => setTime(hours12, Number(e.target.value), ampm)}
                  aria-label="Minute"
                >
                  {Array.from({ length: 60 }, (_, i) => i).map((m) => (
                    <option key={m} value={m}>
                      {String(m).padStart(2, "0")}
                    </option>
                  ))}
                </select>
                <select
                  className={selectClass}
                  value={ampm}
                  onChange={(e) => setTime(hours12, minutes, e.target.value as "AM" | "PM")}
                  aria-label="AM/PM"
                >
                  <option value="AM">AM</option>
                  <option value="PM">PM</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-outline-variant px-3 py-2">
          <button
            type="button"
            onClick={() => {
              setDraft(null);
              onChange("");
              setOpen(false);
            }}
            className="font-mono text-label-md text-on-surface-variant hover:text-primary"
          >
            Clear
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setView(DEMO_TODAY);
                pickDay(DEMO_TODAY);
              }}
              className="font-mono text-label-md text-secondary hover:underline"
            >
              Today
            </button>
            <Button type="button" size="sm" onClick={commit}>
              OK
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
