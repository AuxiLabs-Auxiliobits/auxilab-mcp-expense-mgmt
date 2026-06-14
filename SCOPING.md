# Expense Management Platform — Final Scoping & Tech Stack Document

**Status:** Final (for build kickoff)
**Date:** 2026-06-14
**Origin brief:** #4 — Finance / Employee Expense Management (MCP Server)
**Now scoped as:** A production, enterprise-grade expense compliance platform — MCP server + multi-role web portal + agency-aware document RAG + an **LLM Finance Approver agent**, built for scalability, reliability, and security.
**Publishable core:** `auxilab-mcp-expense-mgmt` (MCP server package)

---

## 1. What we are building

An enterprise platform that automates the **compliance, approval, and data-quality layer** of employee expense management across **multiple agencies** (e.g., Crispin, SKDK, JetFuel). It:

- Accepts **expense sheets** — each containing **multiple line items**, and **each line item with its own attachments**.
- Routes every sheet through a multi-stage workflow: **Employee submit → Manager per-line-item approval → LLM Finance Approver (agency-policy-driven) → payment**.
- Validates line items against a baseline policy ruleset and **agency-specific finance policy documents** held in RAG.
- Parses receipts, classifies spend, detects duplicates, and summarises sheets.
- Lets Finance/Admin maintain agency policy documents the approver agent reasons over.
- Exposes analysis capabilities as **MCP tools** for AI agents **and** through a **role-restricted web portal** for humans.

This is a production system end users rely on directly, so **scalability, reliability, and security are first-class requirements**.

> **Governing principle — bounded LLM authority + deterministic guardrails.**
> Intake and baseline checks are **deterministic**. At the finance gate, the **LLM Finance Approver Agent** has explicit, *bounded* authority to **Approve**, **Reject (with cited policy reasons)**, or **Route to human** — and it **must** route whenever its confidence is low, the agency policy is missing/ambiguous, or a deterministic numeric cross-check disagrees with it. Every decision **cites the agency policy clause**, runs alongside deterministic numeric checks, is **fully audited**, and is **human-overridable**.

---

## 2. Architecture (layered)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  IDENTITY (Microsoft Entra External ID — brokers Google / Microsoft / SSO)     │
└──────────────────────────────────────────────────────────────────────────────┘
            │ OIDC tokens (role + agency claims)
            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  EDGE:  Azure Front Door + WAF  →  Azure API Management (rate limit, schema)    │
└──────────────────────────────────────────────────────────────────────────────┘
            │
   ┌────────┴───────────────────────────────────┐
   ▼                                             ▼
┌──────────────────────┐               ┌─────────────────────────┐
│  Next.js Portal       │               │  AI Agent (MCP host)    │
│  (4 human role UIs)   │               │                         │
└──────────┬───────────┘               └────────────┬────────────┘
           │ REST/HTTPS                              │ MCP
           ▼                                         ▼
┌──────────────────────┐               ┌─────────────────────────┐
│  Web API (FastAPI)    │               │  MCP Server (MCP SDK)   │
│  ← RBAC enforced here │               │  ← stateless tools      │
└──────────┬───────────┘               └────────────┬────────────┘
           │                                         │
           │            ┌────────────────────────────┴───────────┐
           │            ▼                                          │
           │   ┌──────────────────────────────┐                   │
           │   │  LLM FINANCE APPROVER AGENT   │                   │
           │   │  (LangGraph worker)           │                   │
           │   │  • reads agency policy (RAG)  │                   │
           │   │  • iterates line items        │                   │
           │   │  • Approve / Reject / Route   │                   │
           │   └───────────────┬──────────────┘                   │
           └──────────────────┬┴──────────────────────────────────┘
                              ▼
              ┌──────────────────────────────────┐
              │   CORE ENGINE (pure Python)        │
              │   • Policy checker (rules)         │
              │   • Receipt parser (LLM + math)    │
              │   • Category classifier (LLM)      │
              │   • Duplicate detector (rules)     │
              │   • Report summariser (agg + LLM)  │
              └───────┬───────────────────┬────────┘
                      ▼                   ▼
        ┌──────────────────────┐   ┌────────────────────────────────┐
        │  LLM Gateway (adapter)│   │  Agency Policy RAG              │
        │  → Azure AI Foundry   │   │  → Azure AI Search (per-agency) │
        │    (model-agnostic)   │   │    + Document Intelligence      │
        └──────────┬───────────┘   └─────────────┬──────────────────┘
                   │                              │
                   ▼                              ▼
        ┌──────────────────────┐   ┌────────────────────────────────┐
        │  Guardrails           │   │  Azure Blob Storage             │
        │  AI Content Safety /  │   │  (attachments + agency policy   │
        │  Prompt Shields       │   │   docs, ACL + agency-tagged)    │
        └──────────────────────┘   └────────────────────────────────┘
                   │
                   ▼
        ┌────────────────────────────────────────────────────────┐
        │  DATA: Azure PostgreSQL (Flexible Server, HA)            │
        │  + Azure Cache for Redis  + Azure Service Bus (async)    │
        └────────────────────────────────────────────────────────┘
```

**Key separations:** RBAC + identity live in the **portal/API layer**; MCP tools stay **stateless**; the **LLM Finance Approver** is a backend worker that consumes the finance queue and uses the engine + agency-scoped RAG.

---

## 3. Users, roles & RBAC

> **Actors:** **Employee · Manager · Finance · Admin · LLM Approver Agent** (Auditor role removed — the immutable audit log remains and is viewable by Finance & Admin).
> **Agency binding:** every employee belongs to exactly one **agency**. An expense sheet inherits the submitter's agency, and the LLM approver evaluates it against **only that agency's** policy.

### 3.1 Roles & responsibilities

| Actor | Responsibilities |
|---|---|
| **Employee** | Creates/submits/resubmits expense sheets (multi line item, attachments per item); tracks status; responds to info requests |
| **Manager** | Reviews each sheet **in their own agency**, **per line item** — approve / reject / request info per item; a sheet advances to Finance only when **all** its line items are manager-approved |
| **Finance** | Handles sheets the LLM **routed for manual intervention**; can override LLM decisions (with reason); **updates agency policy documents**; org-wide reporting; payment authorisation; views audit log |
| **Admin** | **Onboards / deletes agencies**, **creates policies**, manages users & roles, platform configuration; views audit log |
| **LLM Approver Agent** | Automated finance approver — retrieves the sheet's **agency policy** from RAG, iterates each line item, returns **Approve / Reject-with-comments / Route-to-human** for the **entire sheet** |

### 3.2 Permission matrix

| Capability | Employee | Manager | Finance | Admin | LLM Approver |
|---|:--:|:--:|:--:|:--:|:--:|
| Submit / resubmit own sheet | ✅ | ✅ | ✅ | ✅ | ❌ |
| View own sheets | ✅ | ✅ | ✅ | ✅ | — |
| View sheets | ❌ | ✅ (own agency only) | ✅ (all) | ✅ (all) | (agency-scoped at decision time) |
| Per-line-item approve / reject / request-info | ❌ | ✅ | ❌ | ❌ | ❌ |
| Finance decision (approve / reject / route) | ❌ | ❌ | ✅ (manual + handles routed) | ✅ | ✅ (automated) |
| Override an LLM decision (with reason) | ❌ | ❌ | ✅ | ✅ | ❌ |
| Update agency policy **document** | ❌ | ❌ | ✅ | ✅ | ❌ |
| Create policy / onboard / delete **agency** | ❌ | ❌ | ❌ | ✅ | ❌ |
| Manage users & roles | ❌ | ❌ | ❌ | ✅ | ❌ |
| View audit log | ❌ | ❌ | ✅ | ✅ | ❌ |
| RAG document query | own | all | all | all | policy-retrieval only |

✅ allowed · ❌ denied · **Manager is agency-scoped** — sees & actions only sheets in their own agency

### 3.3 RBAC enforcement & SoD
- Enforced at **API route** + **data-query** + **RAG retrieval** layers; UI renders only permitted actions (defense-in-depth).
- **Manager scope:** a manager sees and actions only sheets in **their own agency**; cross-agency access is denied server-side.
- **Segregation of duties:** a manager cannot approve **their own** line items; a finance user cannot override a decision on **their own** sheet; the LLM approver never acts on a sheet whose policy is missing.
- Tokens carry **role + agency**; agency-scoped retrieval is enforced server-side, never trusted from the client.
- 🗒 **Audit:** every authorization decision, access to another user's sheet, and permission-relevant action is recorded (actor, role, agency, target, timestamp).

---

## 4. The five MCP tools + the Finance Approver agent

| Tool | Type | In → Out |
|---|---|---|
| **Policy Checker** | Pure rules (no LLM) | line item + baseline ruleset → `{status, violations[], recommended_action}` (intake-level deterministic checks) |
| **Receipt Parser** | LLM extract + deterministic math | receipt text → `{merchant, receipt_datetime, total, tax, line_items[], payment_method, reconciles, delta}` |
| **Category Classifier** | LLM + keyword fallback | `{description, merchant}` → `{category (1 of 8), confidence, rationale}` |
| **Duplicate Detector** | Pure rules (no LLM) | new line item + history → `{risk_score, matches[]}`. **Unique key = (employee, receipt_datetime, final total)** — §6.1 |
| **Report Summariser** | Aggregation + LLM narrative | sheet/period → `{total_by_category, violation_count, total_at_risk, compliance_rate_pct, narrative}` |

**LLM Finance Approver Agent** (not an MCP tool — a backend LangGraph worker that *uses* these tools + RAG): for a manager-approved sheet, it retrieves the agency policy, iterates each line item, applies policy rules (e.g., *"Wi-Fi reimbursement max $100; above → reject"*), and emits a **sheet-level decision**: **Approved** (all items pass) · **Rejected with comments** (≥1 item fails) · **Routed to human** (uncertain/ambiguous/missing policy). Each line-item verdict cites the governing policy clause.

> **Two-tier policy model:** (1) **Baseline ruleset (structured JSON)** — deterministic intake checks (format, receipt threshold, prohibited categories, duplicates). (2) **Agency finance policy (documents in RAG)** — interpreted by the LLM approver at the finance gate, per agency.

🗒 **Audit:** every tool invocation and every approver-agent run is logged — inputs (hashed where sensitive), outputs, confidence, **model version + policy version + cited clauses** — so any decision is replayable.

---

## 5. Domain model — expense sheets, line items, agencies

```
Agency 1──* Employee 1──* ExpenseSheet 1──* LineItem 1──* Attachment
   │                                              │
   └──* AgencyPolicyDocument (RAG-indexed)        └── manager verdict + LLM verdict (per item)
```

- An **ExpenseSheet** is the unit submitted, reviewed, and paid. It belongs to one employee → one agency.
- A **LineItem** is one expense (category, amount, currency, merchant, date) with **its own attachments** and **its own manager verdict**.
- A sheet's **finance decision is all-or-nothing**: if the LLM rejects any line item, the **entire sheet is rejected**.

### 5.1 Sheet & line-item state machine
```
DRAFT → SUBMITTED → IN_MANAGER_REVIEW
   ├─ any item rejected / info-requested → RETURNED_TO_EMPLOYEE → (resubmit) → SUBMITTED
   └─ all items manager-approved → IN_FINANCE_REVIEW (LLM)
        ├─ all items pass policy            → FINANCE_APPROVED → PAID
        ├─ any item fails policy            → FINANCE_REJECTED (with comments) → (resubmit) → SUBMITTED
        └─ uncertain / ambiguous / no policy→ FINANCE_MANUAL_REVIEW → (human) → APPROVED | REJECTED
```
- **Line-item status:** `PENDING_MANAGER → MANAGER_APPROVED | MANAGER_REJECTED | INFO_REQUESTED`, then `POLICY_PASS | POLICY_FAIL | POLICY_UNCERTAIN` at the finance stage.
- **Resubmission keeps the same expense sheet ID** and **increments a version number** (full history retained per version). It **restarts the workflow fresh** from `SUBMITTED → IN_MANAGER_REVIEW` — all prior manager and finance verdicts are reset, since the data may have changed. Anti-gaming: an unchanged resubmit of a policy-rejected sheet will deterministically reject again.
- 🗒 **Audit:** every state transition (submit, return, approve, reject, route, override, resubmit) is appended to the immutable audit log with actor, role, agency, reason, version, before/after, and timestamp.

---

## 6. Claim lifecycle — three lines of defense & edge cases

```
   Employee submits sheet (N line items, attachments per item)
        │
        ▼
┌───────────────────────────┐  invalid data/format → RETURN TO EMPLOYEE
│ LINE 1 — Intake gate       │
│ (system, deterministic)    │  parse + classify + duplicate + baseline policy + file checks
└───────────┬───────────────┘
            ▼  (valid)
┌───────────────────────────┐  any item rejected / info-requested → RETURN TO EMPLOYEE
│ LINE 2 — Manager           │
│ per-line-item approval     │
└───────────┬───────────────┘
            ▼  (all items approved)
┌───────────────────────────┐  Approved  → PAID
│ LINE 3 — LLM Finance        │  Rejected  → RETURN TO EMPLOYEE (resubmit)
│ Approver (agency policy)   │  Routed    → Finance human review → Approve/Reject
└────────────────────────────┘
```

### 6.1 Line 1 — Intake (system, deterministic)
Validates and enriches every line item before a human sees it. Duplicate **unique key = (employee, `receipt_datetime`, final total)**; enforced by a DB unique index *and* the detector tool. Edge cases:
- **File:** disallowed/spoofed extension (allow-list `.pdf .jpeg .jpg .heic .png .docx .doc`); >25 MB; 0-byte/corrupt; password-protected PDF; HEIC needing conversion; multi-receipt-in-one-file; blurry/rotated low-res; malware (virus scan); re-uploaded file.
- **Data:** missing required field; amount ≤ 0 / implausible; unsupported/foreign currency; future date, or **submitted after the month-end cutoff** (an expense must be submitted **before the end of the calendar month in which it was incurred** — configurable); entered amount ≠ parsed total; reconciliation failure (Σ items + tax ≠ total); tax > total / negative tax; gibberish/injection in text; category disagrees with classifier; missing receipt over threshold.
- **Duplicate:** exact `(receipt_datetime + total)` match → block; resubmission of rejected line; split-claim evasion.
- 🗒 **Audit:** every intake outcome (accepted / returned, with the specific failed checks) is logged against the line item and sheet version.

### 6.2 Line 2 — Manager (per-line-item approval)
**Every** submitted sheet in the manager's **own agency** passes here; the manager actions **each line item** (approve / reject / request-info), checking business justification, that attachments support the claimed item, and reasonableness. A sheet advances to Finance **only when all line items are approved**; any rejection / info-request returns the **whole sheet** to the employee. Manager cannot action their own line items (SoD). **No delegation/backup approver in v1 — the assigned agency manager always approves** (aging/escalation alerts cover absence).

🗒 **Audit:** each per-line-item verdict (approve/reject/request-info) is logged with the manager's identity, reason, and timestamp.

### 6.3 Line 3 — LLM Finance Approver (agency-policy-driven)
For a fully manager-approved sheet, the agent retrieves the **employee's agency policy** from RAG and iterates each line item against it (e.g., Wi-Fi ≤ $100). Sheet-level outcome:
- **Approved** — all line items pass. There is **no high-value ceiling** — the LLM may approve any amount when the policy passes.
- **Rejected with comments** — any line item fails; the comment cites the violated policy clause and the offending item; **whole sheet rejected** (no partial reimbursement).
- **Routed to human** — low confidence, ambiguous/conflicting clause, missing policy, or deterministic cross-check disagreement → Finance human review.

**Cap boundary is inclusive:** an amount **equal to** the cap is allowed; only amounts **above** it fail (Wi-Fi $100 passes, $100.01 fails). Finance can **override** any LLM decision with a logged reason.

🗒 **Audit:** the sheet-level decision, every per-line-item verdict, the cited policy clause, model version, policy version, confidence, and any human override are all logged for replay.

### 6.4 Cross-cutting (all lines)
Idempotency on submit/resubmit; immutable audit on every transition (with actor, role, reason, before/after, **and for LLM: model+policy version + cited clauses**); notifications on each state change; configurable thresholds (`receipt_required_threshold`, `submission_cutoff` = **month-end of the incurred month**, `max_file_mb=25`, `allowed_extensions`, duplicate window, LLM confidence-routing threshold) — baseline thresholds owned by Admin, agency policy content owned by Finance.

---

## 7. Agency-specific policy & RAG

- Each **agency** has one or more **policy documents** (finance rules: per-category caps, reimbursement limits, prohibited items, approval thresholds), stored in **Blob Storage**, tagged with `agency_id` + version, and **indexed per-agency in Azure AI Search**.
- **Employee → agency** binding means the approver agent **retrieves only the employee's agency policy** (security/agency trimming) — never another agency's rules.
- **Version pinning:** a sheet is evaluated against the policy version **effective at submission time**; updating a policy mid-flight does not retroactively change in-flight decisions (auditable, reproducible).
- **Ownership:** **Finance** updates/uploads agency policy **document content** (maker-checker, re-index on publish); **Admin** **creates policies, onboards and deletes agencies**, and manages the agency lifecycle.
- **Ingestion:** upload → virus scan → Document Intelligence (extract) → chunk → embed (Foundry) → upsert to AI Search with `agency_id` filter field.
- **Query at decision time:** hybrid (keyword+vector) + semantic ranker, **filtered to the sheet's agency**, with **Prompt Shields** on retrieved content (policy docs and attachments are an injection surface).
- 🗒 **Audit:** every agency lifecycle action (onboard/delete by Admin) and every policy-document change (upload/publish/version by Finance, with before/after + maker-checker approver) is logged; each approver run records which **policy version** it retrieved.

---

## 8. Enterprise edge cases (including ones not yet covered)

Items marked **⊕** are gaps beyond what's been specified so far — flagged because they bite at enterprise scale.

**Expense sheet / line item**
- ⊕ Empty sheet (zero line items) or a line item with **no attachment** where one is required.
- ⊕ **Mixed-currency** line items within one sheet (display + reimbursement currency, FX at decision time).
- ⊕ **Very large sheets** (100s of line items) → LLM context limits → must **chunk/iterate per item**, not whole-sheet-in-one-prompt; cost ceiling per sheet.
- ⊕ **Duplicate line items within the same sheet** (not just across sheets).
- ⊕ Line item **edited after manager approval** → must invalidate approval and re-review (tamper protection).
- ⊕ Attachment ↔ line item **mismatch** (receipt total/merchant ≠ claimed item).
- ✅ **Resolved** — Partial reimbursement vs full reject: a line item exceeding a cap is **rejected outright → whole sheet rejected**. No partial reimbursement.

**Agency / policy**
- ⊕ Employee with **no agency** assigned, or **moved between agencies** mid-cycle (which policy applies — submission-time binding).
- ⊕ **Policy updated while a sheet is in-flight** → version pinning (§7) resolves this; must be enforced.
- ⊕ **Agency deleted** while sheets/employees still reference it → soft-delete + referential integrity; block delete with open sheets.
- ⊕ **Missing/empty/garbled policy** for an agency → approver **must route to human**, never auto-approve.
- ⊕ **Conflicting or ambiguous clauses**, or **non-English** policy → route to human.
- ✅ **Resolved** — Cap boundary is **inclusive**: an amount equal to the cap is allowed; only amounts above it fail.

**LLM finance approver**
- ⊕ **Hallucinated rule** not in the policy → require citation; if uncitable, treat as uncertain → route.
- ⊕ **Poor retrieval** (wrong/low-relevance chunks) → confidence threshold → route.
- ⊕ **LLM/service timeout or outage** → keep on queue + retry; **never silent-approve**; dead-letter after N retries.
- ⊕ **Prompt injection** inside an uploaded receipt/policy influencing the verdict → Prompt Shields + instruction neutralization.
- ⊕ **Non-determinism** → pinned model + policy version + low temperature + decision cache for reproducibility/audit.
- ⊕ **Cost runaway** on huge sheets → per-sheet token budget + batching.

**Workflow / state**
- ⊕ **Resubmission loop** (employee resubmits repeatedly) → version cap / aging / escalation.
- ⊕ **Stale manager approval** after an employee edit → reset on change.
- ⊕ **Manager out-of-office** → **no delegation in v1** — the assigned agency manager always approves; sheets wait with **aging/escalation alerts** (and notifications) rather than rerouting.
- ⊕ **Sheet stuck** in manual-intervention queue → **SLA + aging + escalation** alerts.
- ⊕ **Withdraw/cancel** a sheet mid-flow; **reopen/correct** an already-paid sheet (post-payment adjustment).
- ⊕ **Concurrent edits** (employee edits while manager reviews) → optimistic locking / version conflict.
- ⊕ **Timezone** of `receipt_datetime` across agencies/regions.

**Enterprise / compliance**
- ⊕ **Delegation-of-authority / approval limits** matrix (who may approve up to what value).
- ⊕ **Data retention & residency** per agency/jurisdiction; **PII redaction** in receipts.
- ⊕ **Tax/VAT/GST** handling differing per agency jurisdiction.
- ⊕ **Bulk operations** (manager bulk-approve; finance bulk-export).
- ⊕ **Explainability for audit** — every LLM decision reproducible with cited clauses + inputs.
- ⊕ **Accessibility & i18n** of the portal.
- ⊕ **Notifications/escalations** across email/Teams; **reminders** for aging items.

---

## 9. Governance, validation & guardrails

### 9.1 Application plane (client + server)
- Defense-in-depth validation: Zod (client) + Pydantic (server, authoritative).
- AuthZ on every route + data query + RAG retrieval; clients cannot widen role/agency scope.
- **SoD:** no self-approval (manager/finance/LLM); **maker-checker** on policy edits and agency lifecycle.
- **Immutable audit trail** on every transition (incl. LLM model+policy version + cited clauses); viewable by Finance & Admin.
- Edge controls: APIM rate limits, request-size caps, schema validation, idempotency keys.
- Data protection: TLS, TDE at rest, PII tagging, retention/residency per agency.

### 9.2 LLM plane (guardrails) — applies especially to the Finance Approver
- **Bounded authority** with mandatory **route-to-human** escape hatch (low confidence / missing / ambiguous policy / numeric disagreement).
- **Grounding & citations:** every line-item verdict cites the agency policy clause; uncitable claim → uncertain → route.
- **Deterministic cross-checks alongside the LLM:** numeric caps re-verified by math; reconciliation re-verified; the LLM never overrides a hard numeric fail.
- **Input guardrails:** Prompt Shields on attachments + policy docs (injection/poisoning surface).
- **Reproducibility:** pinned model + pinned policy version + low temperature + decision cache + full prompt/response logging (PII-handled).
- **Evaluation:** golden-set regression evals per agency in CI; a model or policy change can't silently regress decisions.
- **Privacy:** Foundry configured so financial data is not used for training.

---

## 10. Tech stack — Frontend

| Concern | Technology |
|---|---|
| Framework | **Next.js 15 (App Router) + React 19 + TypeScript** |
| Styling / components | **Tailwind CSS + shadcn/ui** |
| Data grids (sheet/line-item queues) | **AG Grid Enterprise** (grouping, master-detail for line items, server-side rows, Excel export) |
| Charts / analytics | **Apache ECharts** + **Tremor** (KPI tiles) |
| Server-state | **TanStack Query** |
| Forms & validation | **React Hook Form + Zod** (mirrors server Pydantic) |
| Auth | **NextAuth / Auth.js** → Entra External ID |

## 11. Tech stack — Backend

| Concern | Technology |
|---|---|
| Runtime | **Python 3.12** |
| Core engine | **Pure Python + Pydantic v2** (framework-free, testable) |
| MCP server | **Official Python MCP SDK** (`mcp`) — PyPI deliverable |
| Web API | **FastAPI + Uvicorn/Gunicorn** |
| AuthN/Z | **Entra External ID JWT** (`msal`/`python-jose`); role + agency dependencies |
| ORM / migrations | **SQLModel** + **Alembic** |
| LLM access | **LLM Gateway → Azure AI Foundry** via **Azure AI Inference SDK**; model-agnostic |
| **Finance Approver + RAG** | **LangGraph** worker (iterate line items, route-to-human interrupts, checkpointing); **Azure AI Search SDK** for agency-scoped retrieval |
| Async workers | **Service Bus consumers** (ingestion, finance-approval queue, batch) |
| Testing / eval | **pytest + httpx**; per-agency golden-set decision evals in CI |

> **LangChain/LangGraph:** no LangChain foundation (deterministic pipeline stays explicit); **LangGraph for the Finance Approver + document Q&A** (stateful, route-to-human interrupts, durable checkpoints). Retrieval via Azure AI Search SDK for agency trimming.

## 12. Tech stack — Data

| Concern | Technology |
|---|---|
| Primary DB | **Azure PostgreSQL — Flexible Server** (zone-redundant HA, PITR, read replicas) |
| Vectors | **Azure AI Search** (per-agency RAG index); `pgvector` optional |
| Cache / broker | **Azure Cache for Redis** |
| Async messaging | **Azure Service Bus** (queues + dead-letter) |
| Object storage | **Azure Blob Storage** (attachments + agency policy docs, ACL + agency-tagged) |
| Local dev | PostgreSQL in Docker |

### 12.1 Data model (first cut)
- **agencies** (id, name, status[active/soft-deleted], created_by)
- **users** (id, name, email, role, **agency_id**)
- **agency_policies** (id, agency_id, version, doc_blob_uri, effective_date, indexed_at, created_by, published_by) — RAG-indexed, version-pinned
- **expense_sheets** (id, employee_id, agency_id, version, status, period, submitted_at, finance_decision, finance_decided_by, policy_version_used) — **`id` is stable across resubmissions; `version` increments each resubmission** and a full per-version history is retained
- **line_items** (id, sheet_id, category, amount, currency, expense_date, merchant, description, receipt_datetime, receipt_total, manager_status, manager_actor_id, manager_reason, policy_status, policy_clause_ref)
- **attachments** (id, line_item_id, blob_uri, file_type, size, scan_status, ocr_status)
- **claim_checks** (id, line_item_id, policy_result, category_result, duplicate_result, receipt_result)
- **decisions** (id, sheet_id, actor_id, actor_role, action, reason, llm_model_version, policy_version, timestamp)
- **audit_log** (id, actor_id, action, entity, before, after, timestamp) — append-only

> **DB constraints:** unique index on **(employee_id, receipt_datetime, receipt_total)**; FK guards preventing **agency delete** while sheets reference it (soft-delete instead).

## 13. Tech stack — Azure components

| Component | Role |
|---|---|
| **Microsoft Entra External ID** | Identity broker (Google/Microsoft/SSO); role + agency claims |
| **Azure AI Foundry** | Custom-deployed LLM(s) + embeddings; via model-agnostic gateway |
| **Azure AI Search** | Per-agency hybrid + semantic RAG index with agency trimming |
| **Azure AI Document Intelligence** | OCR/layout extraction (prebuilt receipt model + policy docs) |
| **Azure AI Content Safety (Prompt Shields)** | Injection/jailbreak detection on attachments & policy docs |
| **Azure Container Apps** | FastAPI + MCP server + LangGraph approver workers; autoscale on queue depth |
| **Azure Static Web Apps / App Service** | Next.js portal |
| **Azure PostgreSQL (Flexible Server)** | Primary datastore (HA, PITR) |
| **Azure Blob Storage** | Attachments + agency policy documents |
| **Azure Cache for Redis** | Caching, sessions, broker |
| **Azure Service Bus** | Async ingestion + finance-approval queue + dead-letter |
| **Azure Key Vault** | Secrets via Managed Identity |
| **API Management + Front Door + WAF** | Edge gateway, rate limit, schema validation, firewall |
| **Application Insights + Azure Monitor** | Tracing, LLM cost/token metrics, queue-aging alerts |
| **Microsoft Defender for Cloud** | Security posture |
| **Azure Container Registry** | Image storage |

---

## 14. Security & scalability (non-functional)

- **Compute:** containerized on Container Apps; horizontal autoscale on HTTP + **finance-queue depth**; scale-to-zero non-prod.
- **Async:** ingestion + LLM finance approval run as Service Bus workers — request threads never block; **retry-with-backoff**, **dead-letter** (no silent approvals).
- **Reliability:** zone-redundant Postgres + Container Apps; idempotent processing; checkpointed LangGraph runs (resumable).
- **Network:** VNet + Private Endpoints for Postgres/Storage/Search/Foundry; Managed Identities (no keys in code).
- **Observability:** per-sheet distributed tracing; LLM cost/token dashboards; **SLA/aging alerts** for manual-intervention queue.
- **Posture:** Defender for Cloud; least-privilege Azure RBAC.

---

## 15. Technical challenges & mitigations

| Challenge | Risk | Mitigation |
|---|---|---|
| LLM as approver — wrong/over-confident decisions | High | Bounded authority + mandatory route-to-human + cited clauses + deterministic numeric cross-checks + human override |
| Prompt injection via attachments/policy docs | High | Prompt Shields + neutralization + agency-trimmed retrieval |
| Large sheets exceed LLM context / cost | High | Iterate per line item; per-sheet token budget; batching |
| Policy versioning vs in-flight sheets | High | Pin policy version at submission; reproducible decisions |
| RBAC + agency-scope correctness (incl. RAG) | High | Enforce at route + query + retrieval; explicit matrix + agency-isolation tests |
| Duplicate edge cases (split, cross-employee, intra-sheet) | Med | DB unique key + detector; cross-employee → human |
| File handling (HEIC, encrypted PDF, spoofed type) | Med | Magic-byte check, conversion, reject encrypted, virus scan |
| Model variability (Foundry deployments change) | Med | Model-agnostic gateway + per-agency eval gate on swap |
| Resubmission loops / stale approvals | Med | Versioning, reset-on-edit, resubmit cap, aging alerts |

---

## 16. Delivery roadmap (enterprise)

| Stage | Deliverable |
|---|---|
| **S0 — Foundation** | Core engine (5 tools) + schemas + baseline policy JSON + Postgres + Alembic + LLM gateway + synthetic agencies/sheets + eval harness |
| **S1 — MCP server** | 5 tools via MCP SDK; demo harness; published `auxilab-mcp-expense-mgmt` |
| **S2 — Workflow + RBAC** | FastAPI; Entra auth (role+agency); expense-sheet/line-item model + state machine; manager per-line-item approval; audit log; Service Bus |
| **S3 — LLM Finance Approver** | LangGraph approver worker; agency policy RAG (Blob → Document Intelligence → AI Search); Approve/Reject/Route + citations + guardrails |
| **S4 — Portal** | Next.js role UIs (employee/manager/finance/admin) with AG Grid master-detail + ECharts; agency policy management UI |
| **S5 — Hardening** | Content Safety, VNet/Private Endpoints, WAF/APIM, observability, SLA/aging, load/security testing, DR |

---

## 17. Demo flow

1. Seed agencies (Crispin, SKDK, JetFuel) each with a policy doc (e.g., Wi-Fi ≤ $100); employees bound to agencies.
2. Employee submits a multi-line-item sheet with attachments per item.
3. **Intake** validates/parses/classifies/dedupes each line item.
4. **Manager** approves/rejects per line item; fully-approved sheet → finance queue.
5. **LLM Finance Approver** pulls the employee's agency policy, iterates line items → **Approved / Rejected-with-comments / Routed**.
6. Rejected → employee resubmits (new version). Routed → Finance human decides.
7. **Portal** views per role; **Summariser** report; agency policy update by Finance; agency onboarding by Admin.

---

## 18. Stack summary (one-glance)

- **Frontend:** Next.js 15 · React 19 · TS · Tailwind + shadcn/ui · AG Grid Enterprise · ECharts + Tremor · TanStack Query · RHF + Zod · NextAuth
- **Backend:** Python 3.12 · Pydantic v2 · MCP SDK · FastAPI · SQLModel · Alembic · LangGraph (approver + RAG) · Azure AI Inference SDK
- **Data:** Azure PostgreSQL Flexible Server · Azure AI Search (per-agency) · Redis · Service Bus · Blob Storage
- **AI/LLM:** Azure AI Foundry (model-agnostic) · Document Intelligence · AI Content Safety (Prompt Shields)
- **Identity:** Microsoft Entra External ID (Google/Microsoft/SSO; role + agency claims)
- **Platform:** Container Apps · Static Web Apps/App Service · Key Vault · APIM + Front Door + WAF · App Insights + Monitor · Defender for Cloud · ACR
- **Principles:** role-based RBAC (no teams) + agency isolation · bounded LLM authority with route-to-human · all-or-nothing sheet approval · two-tier policy (baseline JSON + agency RAG) · audit everything

---

## 19. Resolved decisions (locked)

| # | Decision | Resolution |
|---|---|---|
| 1 | Manager scope | **Agency-scoped** — manager sees/actions only their own agency's sheets |
| 2 | Cap exceeded | **Reject the line item → whole sheet rejected** (no partial reimbursement) |
| 3 | Cap boundary | **Inclusive** — exactly at the cap is allowed; only above the cap fails ($100 ✅, $100.01 ❌) |
| 4 | Resubmission | **Same expense sheet ID**, version increments; **restarts fresh from Manager review** |
| 5 | High-value threshold | **None** — the LLM may approve any amount when the policy passes |
| 6 | Submission window | Must be submitted **before the end of the month the expense was incurred** (month-end cutoff, configurable) |
| 7 | Duplicate rule item (iv) | Nothing to add |
| 8 | Manager delegation | **No delegation** — the assigned agency manager always approves (aging alerts cover absence) |

> One item left to confirm: the **cap boundary** (#3) is set **inclusive** by your earlier "above that" wording — flag if you want it exclusive instead.

---

## 20. Appendix — concrete reference details

### A. Standard expense categories (classifier output enum)
The Category Classifier returns exactly one of these 8 categories + a confidence score:
1. **Meals & Entertainment**
2. **Travel - Air**
3. **Travel - Hotel**
4. **Travel - Ground**
5. **Office Supplies**
6. **Software / Subscriptions**
7. **Client Entertainment**
8. **Other**

### B. Baseline policy ruleset (structured JSON — deterministic intake tier)
Owned by **Admin**; checked deterministically at Line 1. Illustrative shape:
```json
{
  "per_meal_limit": 75,
  "per_hotel_night_limit": 250,
  "prohibited_categories": ["Other"],
  "receipt_required_threshold": 25,
  "submission_cutoff": "month_end_of_incurred_month",
  "max_file_mb": 25,
  "allowed_extensions": [".pdf", ".jpeg", ".jpg", ".heic", ".png", ".docx", ".doc"],
  "duplicate_near_match_days": 3,
  "cap_boundary": "inclusive",
  "llm_confidence_routing_threshold": 0.7,
  "currency": "USD"
}
```

### C. Agency finance policy (document tier — RAG, per agency)
Owned by **Finance** (content) / **Admin** (lifecycle). Natural-language policy documents the LLM approver reasons over, e.g.:
- *"Wi-Fi / internet reimbursement is capped at **$100**; any amount above is rejected."* (inclusive cap → $100 allowed)
- *"Client entertainment requires an itemised receipt and attendee list."*
- *"Air travel must be economy class for flights under 6 hours."*
Each agency (Crispin, SKDK, JetFuel, …) has its own document set, version-pinned and indexed under its `agency_id`.

### D. Synthetic demo dataset (per the brief)
A 15-line-item expense sheet (or set) with a realistic mix:
- **8 compliant** line items (auto-pass intake, manager-approve, LLM-approve).
- **4 policy violations** — e.g., over-limit meals, prohibited category, over agency cap (Wi-Fi > $100).
- **2 near-duplicates** — same `(receipt_datetime, total)` or within the ±3-day window.
- **1 missing receipt** — amount over the receipt-required threshold.
Receipt text samples (hotel/restaurant) generated for the Receipt Parser; policy docs per agency seeded for RAG.

### E. Worked examples (acceptance checks)
| Input | Expected output |
|---|---|
| Meal claim $187, policy per-meal limit $75 | Non-compliant → exceeds meal cap → flag/reject |
| Receipt `"Marriott Hotels, 2 nights @ $210, Tax $42, Total $462"` | merchant=Marriott, nights=2, tax=$42, total=$462; reconciliation **passes** (2×210+42=462) |
| Merchant `"Uber"`, description `"Airport transfer"` | category **Travel - Ground**, confidence ≈ 0.94 |
| Wi-Fi bill $100 vs agency cap $100 | **Pass** (inclusive boundary) |
| Wi-Fi bill $100.01 vs agency cap $100 | **Fail** → line item rejected → whole sheet rejected |

### F. Status glossary
**Sheet status:** `DRAFT · SUBMITTED · IN_MANAGER_REVIEW · RETURNED_TO_EMPLOYEE · IN_FINANCE_REVIEW · FINANCE_APPROVED · FINANCE_REJECTED · FINANCE_MANUAL_REVIEW · APPROVED · REJECTED · PAID`
**Line-item status:** `PENDING_MANAGER · MANAGER_APPROVED · MANAGER_REJECTED · INFO_REQUESTED · POLICY_PASS · POLICY_FAIL · POLICY_UNCERTAIN`
**Finance decision (LLM):** `APPROVED · REJECTED_WITH_COMMENTS · ROUTED_TO_HUMAN`

### G. Notes carried over from the origin brief
- Suggested original parsing libs (pdfplumber / pytesseract) are **superseded** by **Azure AI Document Intelligence** for enterprise OCR/layout.
- The MCP server core remains independently publishable as **`auxilab-mcp-expense-mgmt`** (PyPI + GitHub).
- Prospect/business context: Expense Management is an Auxiliobits Finance-automation pillar; the platform targets mid-market CFOs and multi-agency groups.
