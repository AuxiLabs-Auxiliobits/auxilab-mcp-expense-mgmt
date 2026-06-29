# Auxilab — Expense Management Portal (Frontend)

Multi-role web portal for the enterprise expense-compliance platform described in
`../SCOPING.md`. It implements the four human role UIs — **Employee, Manager,
Finance, Admin** — over an **LLM Finance Approver** workflow with agency-scoped
policy, citation-first AI decisions, and a full audit trail.

The UI realizes the **"Auxilio Compliance"** design system from the Stitch mockups:
Signal-red primary on a monochrome surface scale, Hanken Grotesk + JetBrains Mono,
Material Symbols icons, dense data-first layouts.

---

## Tech stack

| Concern | Technology |
|---|---|
| Framework | Next.js 15 (App Router) · React 19 · TypeScript |
| Styling / components | Tailwind CSS v3 · shadcn-patterned primitives (Radix + cva) |
| Data grids | Custom grids matching the mockups (AG Grid Enterprise drop-in later) |
| Charts / KPI tiles | Apache ECharts · custom Tremor-style KPI tiles |
| Server-state | TanStack Query |
| Forms & validation | React Hook Form + Zod (mirrors server Pydantic) |
| Auth | NextAuth (Auth.js v5) → Microsoft Entra External ID |

> **Grids:** the scoping doc specifies AG Grid Enterprise (master-detail, row
> grouping, server-side rows, Excel export). Those are licensed features, so the
> grids here are custom React components that match the mockups pixel-for-pixel and
> are architected to swap in AG Grid Enterprise for the heavy queues when a license
> is available.

---

## Getting started

```bash
npm install        # if not already installed
npm run dev        # http://localhost:3000  → redirects to /employee
```

The app is fully runnable against an **in-memory mock dataset** — no backend
required. The landing page (`/login`) has demo "Enter as <role>" buttons, and the
top-nav **role switcher** walks you through all four portals.

```bash
npm run build      # production build (TypeScript checks on)
npm run lint       # ESLint (run separately from build)
```

---

## Project structure

```
src/
  app/
    (portal)/                 # shared shell (sidebar + top nav + role switcher)
      employee/               # dashboard · sheets · sheets/new · sheets/[id] · receipts · settings
      manager/                # review queue (master-detail, per-line-item actions)
      finance/                # Policy & AI Approver console · audit
      admin/                  # platform settings (agencies, baseline policy, roles, audit)
    api/auth/[...nextauth]/   # NextAuth route handlers
    login/                    # branded sign-in (Entra + demo roles)
  components/                 # cross-feature, reusable UI
    ui/                       # shadcn-style primitives (button, card, dialog, select, …)
    shared/                   # KpiTile, StatusBadge, AiCitation, DataGrid, Chart, AuditLog …
    layout/                   # Sidebar, TopNav, RoleSwitcher, PortalShell, PageContainer
  features/                   # feature modules — components co-located by role
    employee/                 # kpi-row, active-sheet-panel, recent-sheets
    manager/                  # review-queue (master-detail + per-line-item actions)
    finance/                  # console, finance-kpis, policy-documents, routed-table, review-detail
    admin/                    # settings, agency-management, baseline-policy-viewer, role-assignment-form
  data/
    types.ts                  # domain model (mirrors backend §12.1 + status glossary)
    mock.ts                   # demo dataset (compliant / violation / duplicate / missing-receipt)
    api.ts                    # typed API client (mock-backed today)
    hooks.ts                  # TanStack Query hooks
  lib/
    rbac.ts                   # roles, nav config, capability matrix, role-from-path
    status.ts                 # status → badge styling + icons
    schemas.ts                # Zod schemas for forms
    format.ts                 # currency / date / percent helpers
  auth.ts                     # NextAuth config (Entra + dev credentials)
```

---

## The four role portals

- **Employee** — KPI tiles, active draft sheet with a line-item grid + inline AI
  citations, recent sheets, sheet list/detail, and a New Sheet form (RHF + Zod).
- **Manager** — agency-scoped review queue (master list + detail), per-line-item
  approve / reject / request-info with mandatory reasons, review-progress, and an
  all-or-nothing "Approve Entire Sheet" gate. Enforces SoD (no self-approval) in the UI.
- **Finance** — Policy & AI Approver console: KPIs with an ECharts sparkline, agency
  RAG policy documents, the "Routed for Manual Review" table, and a review detail
  with **AI Decision Support** (uncertainty reason + cited clause) and a mandatory
  **override** form (RHF + Zod) feeding the audit log.
- **Admin** — Platform Settings: agency management, baseline policy (intake-tier)
  JSON viewer, quick role assignment (RHF + Zod), and the immutable audit log.

RBAC is rendered defensively (sidebar/role-switcher lock items the role can't access);
the authoritative checks live in the API. See `src/lib/rbac.ts`.

### Workflow & operations

- **Employee sheet builder** — add/edit/remove line items with full bill details
  (merchant, type, amount/currency, dates, **tax/VAT**, **receipt total**) and
  **attachments** (allow-list + size + HEIC-conversion notes). Live intake checks
  per §6.1/§20.B: amount, prohibited category, future date, **month-end cutoff**,
  **receipt-required threshold**, per-meal/hotel caps, reconciliation, tax>amount,
  and **intra-sheet / cross-sheet / cross-employee duplicates**.
- **Submit / Resubmit / Withdraw** — drafts submit; rejected/returned sheets show
  feedback and **resubmit with or without changes** (same id, version++, restart at
  manager, §5.1); in-flight sheets can be **withdrawn**. **Mixed-currency** banner (§8).
- **Manager** — per-line-item actions + **bulk-approve** selected sheets; **SLA/aging**
  badges (§6.4/§8).
- **Finance** — AI override console, **org-wide sheets grid with CSV export**, RAG
  policy **upload + maker-checker publish**, aging on the routed queue.
- **Admin** — **agency onboarding**, baseline-policy viewer, role assignment, audit log.
- **Notifications** — role-scoped bell with unread count + mark-all-read.

---

## Backend integration (Expense Management API)

The app is wired to the FastAPI backend in `postman/Expense-Management-API`. Set
in `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_USE_BACKEND=true
AUTH_LOGIN_URL=http://localhost:8000/auth/login
```

- **Transport** — `src/data/http.ts` calls the API and attaches the session
  **bearer token** (`Authorization: Bearer <access_token>`) on every request.
- **Auth** — `src/auth.ts` posts to `/auth/login` (→ `{ access_token }`), then reads
  the profile from `/auth/me`; role + agency + token go on the session.
- **Mapping** — `src/data/mappers.ts` converts the backend snake_case payloads to
  the frontend types (sheet, line item, agency, audit).
- **Toggle** — every `api.ts` function uses `backend(realCall, mockFallback)`, so
  with `NEXT_PUBLIC_USE_BACKEND=false` the app runs fully offline on the mock.

### Endpoint mapping (wired)

| Frontend (`api.ts`) | Backend |
|---|---|
| `getEmployeeSheets` | `GET /sheets` |
| `getSheet` | `GET /sheets/{id}` |
| `createSheet` | `POST /sheets` |
| `submitSheet` | `POST /sheets/{id}/submit` |
| `getManagerQueue` | `GET /manager/queue` |
| `actOnLineItem` | `POST /manager/sheets/{id}/action` |
| `getRoutedSheets` | `GET /finance/queue` |
| `financeOverride` | `POST /finance/sheets/{id}/decision` |
| `getAuditLog` | `GET /finance/audit` |
| `getAgencies` / `addAgency` | `GET` / `POST /admin/agencies` |
| `getMe`, user CRUD, agency CRUD, `getPolicies`, `publishPolicy` | `/auth/me`, `/admin/users*`, `/admin/agencies/{id}`, `/finance/policies/*` |

### Gaps (no matching API endpoint → remain client-side/mock)

The collection has no endpoints for these, so they stay on the in-memory store
even in backend mode (and would be the next backend additions):
incremental **line-item add/edit/remove**, **resubmit**, **withdraw**, manager
**bulk-approve**, **all-sheets** grid, **KPIs/spend**, **notifications**, and the
**policy upload** multipart flow (a `uploadPolicy` client + `apiUpload` helper exist
but the dialog needs to pass the real `File`). The backend model creates a sheet
*with* its line items in one `POST /sheets`, so the incremental editor is a
frontend convenience pending a backend equivalent.

## Authentication & role-based access

NextAuth (Auth.js v5) drives sign-in; the authenticated **role** flows into the
session and gates everything — UI *and* routes.

- **Login UI** (`/login`) — Auxiliobits-themed email + password form (RHF + Zod),
  optional Microsoft Entra SSO button, and offline demo accounts.
- **Credentials → your backend** — `src/auth.ts` posts `{ email, password }` to
  `AUTH_LOGIN_URL` (`/auth/login` → `{ access_token }`), then reads the profile from
  `/auth/me` (role, agency, name); the token is stored on the session for API calls.
  With `AUTH_LOGIN_URL` unset, four demo accounts work offline: `employee@demo.local`,
  `manager@demo.local`, `finance@demo.local`, `admin@demo.local` (any password).
- **Role drives permissions** — `jwt`/`session` callbacks put `role` + `agencyId`
  on the session (`src/auth.config.ts`). The role switcher, nav, and content all
  read it: an employee sees only the employee portal, finance up to finance, admin
  everything (hierarchy in `ROLE_VIEW_ACCESS`).
- **Edge middleware** (`src/middleware.ts` + `auth.config.ts`) protects every
  portal route: unauthenticated → `/login`; authenticated-but-not-permitted →
  302 to the user's home portal. Defense-in-depth beyond the UI (SCOPING.md §3.3).

Setup: copy `.env.example` → `.env.local`, run `npx auth secret`, set
`AUTH_LOGIN_URL`. For SSO, fill `AUTH_MICROSOFT_ENTRA_ID_*` **and** set
`NEXT_PUBLIC_ENTRA_ENABLED=true` (the provider is only registered when configured).

### Demo accounts (offline)

| Role | Email | Password |
|---|---|---|
| Employee | `jane.doe@crispin.com` | any |
| Manager | `mark.chen@crispin.com` | any |
| Finance | `sarah.okafor@auxilab.com` | any |
| Admin | `alex.rivera@auxilab.com` | any |

## Extending toward the full spec

- **AG Grid Enterprise** — swap `components/shared/data-grid.tsx` (and the manager
  master-detail) for AG Grid with a license key for grouping / server-side rows / Excel export.
- **Tremor** — KPI tiles are custom (Tremor-style) to avoid theme conflicts; Tremor
  can be layered in for richer analytics tiles.
- **Design tokens** — defined once in `tailwind.config.ts` from the Auxilio spec.
