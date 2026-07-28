"use client";

import { useMemo, useState } from "react";
import { Icon } from "@/components/ui/icon";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/**
 * Column-driven enterprise data grid: dense 13px rows, sticky mono header,
 * optional per-column sorting (asc → desc → off), client pagination, and
 * optional row selection with a bulk-action bar.
 */
export interface Column<T> {
  key: string;
  header: React.ReactNode;
  align?: "left" | "right" | "center";
  width?: string;
  headerClassName?: string;
  cellClassName?: string;
  render: (row: T) => React.ReactNode;
  /** Provide to make this column sortable. */
  sortAccessor?: (row: T) => string | number;
}

const alignClass = {
  left: "text-left",
  right: "text-right",
  center: "text-center",
} as const;

export function DataGrid<T>({
  columns,
  rows,
  getRowId,
  onRowClick,
  emptyMessage = "No records",
  pageSize,
  selectable = false,
  bulkActions,
  columnManagement = false,
  className,
}: {
  columns: Column<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  /** Enables pagination at this page size. */
  pageSize?: number;
  /** Enables a checkbox column + bulk-action bar. */
  selectable?: boolean;
  bulkActions?: (selected: T[], clear: () => void) => React.ReactNode;
  /** Enables a "Columns" menu to show/hide columns. */
  columnManagement?: boolean;
  className?: string;
}) {
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const visibleColumns = columns.filter((c) => !hidden.has(c.key));

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortAccessor) return rows;
    const acc = col.sortAccessor;
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = acc(a);
      const bv = acc(b);
      if (av < bv) return -dir;
      if (av > bv) return dir;
      return 0;
    });
  }, [rows, sort, columns]);

  const total = sorted.length;
  const pageCount = pageSize ? Math.max(1, Math.ceil(total / pageSize)) : 1;
  const safePage = Math.min(page, pageCount - 1);
  const view = pageSize
    ? sorted.slice(safePage * pageSize, safePage * pageSize + pageSize)
    : sorted;

  const selectedRows = useMemo(
    () => sorted.filter((r) => selectedIds.has(getRowId(r))),
    [sorted, selectedIds, getRowId],
  );
  const allViewSelected = view.length > 0 && view.every((r) => selectedIds.has(getRowId(r)));
  const colSpan = visibleColumns.length + (selectable ? 1 : 0);

  function toggleColumn(key: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else if (columns.length - next.size > 1) next.add(key); // keep ≥ 1 column
      return next;
    });
  }
  const columnLabel = (c: Column<T>) => (typeof c.header === "string" ? c.header : c.key);

  function toggleSort(key: string) {
    setPage(0);
    setSort((s) => {
      if (s?.key !== key) return { key, dir: "asc" };
      if (s.dir === "asc") return { key, dir: "desc" };
      return null;
    });
  }
  function toggleRow(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function toggleAll() {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      const ids = view.map(getRowId);
      if (ids.every((id) => next.has(id))) ids.forEach((id) => next.delete(id));
      else ids.forEach((id) => next.add(id));
      return next;
    });
  }
  const clearSelection = () => setSelectedIds(new Set());

  return (
    <div className={cn("w-full", className)}>
      {selectable && selectedRows.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant bg-secondary-container/40 px-4 py-2">
          <span className="text-body-sm font-medium text-on-surface">
            {selectedRows.length} selected
          </span>
          <div className="flex items-center gap-2">
            {bulkActions?.(selectedRows, clearSelection)}
            <button
              onClick={clearSelection}
              className="rounded px-2 py-1 text-label-md font-medium text-on-surface-variant transition-colors hover:text-on-surface"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {columnManagement && (
        <div className="flex justify-end border-b border-outline-variant px-3 py-2">
          <DropdownMenu>
            <DropdownMenuTrigger className="flex h-8 items-center gap-1.5 rounded-md border border-outline-variant px-2.5 text-label-md font-medium text-on-surface-variant transition-colors hover:bg-surface-container-low focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary">
              <Icon name="view_column" className="text-[16px]" /> Columns
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[12rem]">
              <DropdownMenuLabel>Show columns</DropdownMenuLabel>
              {columns.map((c) => {
                const shown = !hidden.has(c.key);
                return (
                  <DropdownMenuItem
                    key={c.key}
                    onSelect={(e) => {
                      e.preventDefault();
                      toggleColumn(c.key);
                    }}
                  >
                    <Icon
                      name={shown ? "check_box" : "check_box_outline_blank"}
                      className={cn("text-[18px]", shown ? "text-secondary" : "text-on-surface-variant")}
                    />
                    {columnLabel(c)}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

      <div className="w-full overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead className="bg-surface-container-highest">
            <tr>
              {selectable && (
                <th className="sticky top-0 z-10 w-10 border-b border-outline-variant bg-surface-container-highest px-4 py-3">
                  <input
                    type="checkbox"
                    aria-label="Select all rows"
                    checked={allViewSelected}
                    onChange={toggleAll}
                    className="h-4 w-4 rounded border-outline text-secondary focus:ring-secondary"
                  />
                </th>
              )}
              {visibleColumns.map((col) => {
                const sortable = !!col.sortAccessor;
                const active = sort?.key === col.key;
                return (
                  <th
                    key={col.key}
                    style={col.width ? { width: col.width } : undefined}
                    aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}
                    className={cn(
                      "sticky top-0 z-10 border-b border-outline-variant bg-surface-container-highest px-4 py-3 text-[13px] font-semibold text-on-surface-variant",
                      alignClass[col.align ?? "left"],
                      col.headerClassName,
                    )}
                  >
                    {sortable ? (
                      <button
                        onClick={() => toggleSort(col.key)}
                        className={cn(
                          "inline-flex items-center gap-1 transition-colors hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary",
                          col.align === "right" && "flex-row-reverse",
                          active && "text-on-surface",
                        )}
                      >
                        {col.header}
                        <Icon
                          name={active ? (sort!.dir === "asc" ? "arrow_upward" : "arrow_downward") : "unfold_more"}
                          className={cn("text-[14px]", !active && "opacity-40")}
                        />
                      </button>
                    ) : (
                      col.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {view.length === 0 ? (
              <tr>
                <td
                  colSpan={colSpan}
                  className="px-4 py-10 text-center text-body-sm text-on-surface-variant"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              view.map((row) => {
                const id = getRowId(row);
                const selected = selectedIds.has(id);
                return (
                  <tr
                    key={id}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    tabIndex={onRowClick ? 0 : undefined}
                    role={onRowClick ? "button" : undefined}
                    aria-selected={selectable ? selected : undefined}
                    onKeyDown={
                      onRowClick
                        ? (e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              onRowClick(row);
                            }
                          }
                        : undefined
                    }
                    className={cn(
                      "group transition-colors duration-150",
                      selected
                        ? "bg-secondary-container/40 shadow-[inset_2px_0_0_rgb(var(--primary))]"
                        : "bg-surface-container-lowest hover:bg-surface-container-low",
                      onRowClick &&
                        "cursor-pointer focus:outline-none focus-visible:bg-surface-container-low focus-visible:shadow-[inset_0_0_0_2px_rgb(var(--secondary))]",
                    )}
                  >
                    {selectable && (
                      <td className="w-10 px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          aria-label="Select row"
                          checked={selected}
                          onChange={() => toggleRow(id)}
                          className="h-4 w-4 rounded border-outline text-secondary focus:ring-secondary"
                        />
                      </td>
                    )}
                    {visibleColumns.map((col) => (
                      <td
                        key={col.key}
                        className={cn(
                          "px-4 py-3 text-[13px] leading-5 text-on-surface",
                          alignClass[col.align ?? "left"],
                          col.cellClassName,
                        )}
                      >
                        {col.render(row)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {pageSize && total > pageSize && (
        <div className="flex items-center justify-between gap-3 border-t border-outline-variant px-4 py-2.5 text-label-md text-on-surface-variant">
          <span>
            Showing {safePage * pageSize + 1}–{Math.min(total, (safePage + 1) * pageSize)} of {total}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(Math.max(0, safePage - 1))}
              disabled={safePage === 0}
              className="flex h-8 items-center gap-1 rounded-md px-2.5 font-medium transition-colors hover:bg-surface-container-low disabled:pointer-events-none disabled:opacity-40"
            >
              <Icon name="chevron_left" className="text-[16px]" /> Prev
            </button>
            <span className="px-2 font-mono">
              {safePage + 1} / {pageCount}
            </span>
            <button
              onClick={() => setPage(Math.min(pageCount - 1, safePage + 1))}
              disabled={safePage >= pageCount - 1}
              className="flex h-8 items-center gap-1 rounded-md px-2.5 font-medium transition-colors hover:bg-surface-container-low disabled:pointer-events-none disabled:opacity-40"
            >
              Next <Icon name="chevron_right" className="text-[16px]" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
