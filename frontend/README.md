# Expense Management — Frontend

> **⚠️ REFERENCE SCAFFOLD ONLY — not a finished app.**
> This package exists to communicate the intended frontend architecture and folder
> structure for the portal described in [`../SCOPING.md`](../SCOPING.md) §10. The
> **backend is the real deliverable.** Every page/component here is a clean, typed
> stub with `TODO(reference)` markers. **Nothing has been installed or built**;
> there are no `node_modules` or lockfiles. Do not treat this as production code.

The repo root README still lists `portal/` in the monorepo layout — this `frontend/`
directory is the same role-scoped portal, created under a different name per request.

---

## Stack (SCOPING §10)

| Concern | Technology |
|---|---|
| Framework | Next.js 15 (App Router) + React 19 + TypeScript 5 |
| Styling / components | Tailwind CSS + shadcn/ui |
| Data grids (sheet / line-item queues) | AG Grid Enterprise (master-detail, server-side rows, Excel export) |
| Charts / analytics | Apache ECharts + Tremor (KPI tiles) |
| Server state | TanStack Query |
| Forms & validation | React Hook Form + Zod (mirrors server Pydantic) |
| Auth | NextAuth / Auth.js → Microsoft Entra External ID |

---

## Folder map

```
frontend/
├── package.json            # manifest only — NOT installed
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── .eslintrc.json
├── .env.example            # NextAuth + Entra/Azure AD + NEXT_PUBLIC_API_BASE_URL
├── next-env.d.ts
│
├── app/                    # App Router
│   ├── layout.tsx          # root layout + Providers
│   ├── providers.tsx       # 'use client' — TanStack Query provider
│   ├── globals.css         # Tailwind + shadcn theme tokens
│   ├── page.tsx            # landing → redirect to role dashboard
│   ├── (auth)/login/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx              # shared chrome + RoleNav
│   │   ├── employee/page.tsx       # my sheets + submit
│   │   ├── manager/page.tsx        # per-line-item approval queue (own agency only)
│   │   ├── finance/page.tsx        # routed/manual queue + overrides + policy docs + reporting
│   │   ├── admin/page.tsx          # agencies + users + baseline policy config
│   │   └── sheets/[sheetId]/page.tsx  # sheet detail (master-detail placeholder)
│   └── api/auth/[...nextauth]/route.ts  # NextAuth → Entra provider (stub)
│
├── components/
│   ├── ui/README.md        # shadcn/ui primitives placeholder
│   ├── SheetGrid.tsx       # AG Grid master-detail stub (sheets → line items)
│   ├── KpiTiles.tsx        # Tremor KPI stub
│   ├── SpendChart.tsx      # ECharts stub
│   └── RoleNav.tsx         # role-aware nav (renders permitted links only)
│
├── lib/
│   ├── api-client.ts       # typed fetch wrapper → FastAPI (bearer auth header)
│   ├── auth.ts             # NextAuth config + session role/agency typing
│   ├── query-client.ts     # TanStack Query client + query keys
│   ├── rbac.ts             # client-side permission helpers (mirror §3.2; server authoritative)
│   ├── schemas.ts          # Zod schemas (mirror backend Pydantic)
│   └── utils.ts            # cn() class-merge helper
│
└── types/
    └── index.ts            # Role, SheetStatus, LineItemStatus, FinanceDecision + entities (§F)
```

---

## How it maps to roles & the permission matrix (SCOPING §3)

Four **human** role UIs (the LLM Approver is a backend worker, not a UI):

- **Employee** — `app/(dashboard)/employee` — view + submit/resubmit own sheets.
- **Manager** — `app/(dashboard)/manager` — per-line-item approval queue, **own agency only**.
- **Finance** — `app/(dashboard)/finance` — routed/manual-review queue, override LLM
  decisions (logged reason), policy-document management, org-wide reporting, audit log.
- **Admin** — `app/(dashboard)/admin` — agency lifecycle, users & roles, baseline policy config.

`lib/rbac.ts` is a **direct transcription of the §3.2 permission matrix** plus the
agency-scope and segregation-of-duties rules (§3.3). It drives UI affordances only
(`RoleNav`, action buttons). **The FastAPI backend re-enforces RBAC + agency scope at
the route, data-query, and RAG-retrieval layers and is authoritative.** Every
authenticated user carries exactly one **role + agency**; managers and finance are
agency-scoped (noted in comments throughout).

---

## How it talks to the backend + Entra

- **Auth:** `lib/auth.ts` configures NextAuth/Auth.js v5 with the Microsoft Entra
  External ID provider (SCOPING §10/§13). Entra brokers Google/Microsoft/SSO and
  issues OIDC tokens carrying **role + agency** claims, which we surface on the session.
- **API:** `lib/api-client.ts` is a typed `fetch` wrapper that targets
  `NEXT_PUBLIC_API_BASE_URL` (the FastAPI API, SCOPING §11) and attaches the session
  bearer token. The server validates the JWT and enforces all access control.
- **Server state:** TanStack Query (`lib/query-client.ts`) with centralized query keys.
- **Forms:** React Hook Form + Zod (`lib/schemas.ts`) mirror the backend Pydantic v2
  models for defense-in-depth validation (SCOPING §9.1) — the server is authoritative.

---

## What's real vs stubbed

**Real (usable as written):**
- All config files (`package.json` manifest, `tsconfig`, `next.config`, Tailwind/PostCSS, ESLint, `.env.example`).
- Type definitions (`types/index.ts`) matching the SCOPING §F status glossary and §5 domain model.
- `lib/rbac.ts` permission logic, `lib/schemas.ts` Zod schemas, `lib/query-client.ts` keys, `lib/utils.ts`.
- App Router file/route topology and the `RoleNav` role-filtering logic.

**Stubbed (typed placeholders with `TODO(reference)` markers):**
- All page bodies render descriptive placeholders, not live data.
- `SheetGrid` / `KpiTiles` / `SpendChart` describe their AG Grid / Tremor / ECharts
  wiring in comments but do not import or render those libraries.
- NextAuth sign-in flow, session reads, and all backend `fetch` calls are not executed.
- `components/ui/` contains no generated shadcn primitives (a README explains how).

---

## Running (for a real build — NOT done here)

```bash
cp .env.example .env.local   # fill in Entra + API base URL
npm install                  # NOT run in this scaffold
npm run dev                  # Next.js dev server on :3000
```
