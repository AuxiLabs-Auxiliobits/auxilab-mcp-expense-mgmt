# Auxilab Expense Management — Frontend (agent notes)

This is a **Next.js 15 (App Router) + React 19 + TypeScript** app, pinned deliberately
to Next 15 to match the project scoping doc. Standard Next 15 conventions apply
(async `params`/`searchParams`, route handlers, RSC + client components).

## Stack
- Tailwind CSS **v3** (`tailwind.config.ts`) — design tokens mirror the "Auxilio
  Compliance" Stitch mockups (Signal-red primary, Hanken Grotesk + JetBrains Mono,
  Material Symbols icon font loaded in `layout.tsx`).
- shadcn-patterned UI primitives in `src/components/ui` (Radix + cva), themed to the
  Auxilio tokens directly (no separate shadcn CSS-variable theme).
- **TanStack Query** for server-state; **React Hook Form + Zod** for forms;
  **Apache ECharts** for charts; **NextAuth v5** → Microsoft Entra External ID.

## Where things live
- `src/data/types.ts` — domain model (mirrors backend §12.1)
- `src/data/mock.ts` — in-memory demo dataset
- `src/data/api.ts` — typed API client (swap mock bodies for `fetch()` to go live)
- `src/data/hooks.ts` — TanStack Query hooks (the stable contract for pages)
- `src/lib/{rbac,status,schemas,format}.ts` — RBAC/nav, status metadata, Zod, formatters
- `src/app/(portal)/{employee,manager,finance,admin}` — route entry points (thin pages)
- `src/features/{employee,manager,finance,admin}` — role-specific components (feature modules)
- `src/components/{ui,layout,shared}` — cross-feature, reusable UI

## Conventions
- Reference design tokens by name (`bg-primary`, `text-on-surface`, `font-mono text-label-md`).
- Icons via `<Icon name="..." />` (Material Symbols), not lucide, to match the mockups.
- Data grids are custom (`src/components/shared/data-grid.tsx`) — AG Grid Enterprise
  can replace them later for the heavy queues (master-detail / server-side rows).
- `npm run lint` is run separately; `next build` keeps TypeScript checks on.
