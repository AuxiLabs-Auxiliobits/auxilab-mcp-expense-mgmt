# Agentic Expense Management Platform

An event-driven layer that turns the app into an intelligent digital coworker: it proactively
analyzes expense sheets, surfaces advisory recommendations and smart notifications, and offers an
AI Workspace — **while never bypassing RBAC, approval workflows, or audit, and never making a
decision itself.** The AI advises; humans decide.

> Honest framing: the "AI" here is the deterministic `expense_core` engine (policy checker,
> duplicate detector) plus transparent risk heuristics — real, offline, and testable. The
> recommendation contract is LLM-ready: swap in Azure Foundry for the narrative without changing
> any guardrail.

## Architecture

```
business event (submit / return / manager-approve / finance-decide / receipt)
        │  router schedules a BackgroundTask (gated by settings.ai_background_events)
        ▼
ai_events.emit(event, sheet_id)         ← own session, post-commit, fully defensive
        ├─ ai_recommendations.generate() → analyze + persist AiRecommendation + AUDIT
        └─ notification_service.notify*() → smart, actionable notifications to the right audience
        ▼
/ai/* API (advisory, RBAC-scoped)   →   AI Workspace (frontend)
  recommendation · workspace · feedback · analytics
```

- **Event framework** (`app/services/ai_events.py`): an in-process event bus. Handlers run after
  the business transaction commits, in their own session, wrapped so an AI failure can **never**
  break or roll back a business operation. Wiring lives in the lifecycle endpoints
  (`sheets.submit`, `manager.action`/`approve`, `finance.decision`) behind a config flag.
- **Recommendation engine** (`app/services/ai_recommendations.py`): pure, testable `analyze()`
  over the line items + the agency baseline policy + duplicate history; persists an
  `AiRecommendation` (superseding the prior one) and writes an `AI_RECOMMENDATION_GENERATED`
  audit row.
- **API** (`app/routers/ai.py`): `GET /ai/sheets/{id}/recommendation`, `GET /ai/workspace`,
  `POST /ai/recommendations/{id}/feedback`, `GET /ai/analytics` — all read-only except feedback.
- **Frontend**: `AI Workspace` page (`/<role>/ai`) with stat cards, recommendation cards,
  expandable explainability, and accept/dismiss/👍/👎 feedback.

## Phase coverage

| Phase | Delivered |
|---|---|
| 1 — Event framework | `ai_events` bus + 5 event types wired into lifecycle endpoints |
| 2 — Autonomous tasks | per-event (re)analysis + role-targeted notifications (employee/manager/finance) |
| 3 — Recommendations | structured per-sheet: summary · risk score/band · policy compliance · missing info · duplicate likelihood · suggested action · confidence |
| 4 — Smart notifications | actionable, deep-linked (`href`), severity-typed; manager "high-priority approval", finance "high-risk reimbursement", employee "receipts still needed" / "tips to fix" |
| 5 — AI Workspace | role-scoped dashboard: pending recs, high-risk, duplicates, missing receipts, policy violations, recent AI actions |
| 6 — Explainability | every rec carries `rationale` = why · data analyzed · policies considered · confidence |
| 7 — Human-in-the-loop | the `/ai` surface exposes **no** approve/reject/submit/decision endpoint; generating a rec never changes sheet state (both asserted in tests) |
| 8 — Feedback | `AiFeedback` (helpful · accepted/ignored/dismissed · reason) via `POST /ai/recommendations/{id}/feedback` |
| 9 — Analytics | `GET /ai/analytics`: recommendations generated, risk-band split, acceptance/helpful rate, violations & duplicates detected, avg approval hours, engagement |
| 10 — Validation | tests below |

## Recommendation model (Phase 3 + 6)

```json
{
  "summary": "1 line item totaling $676.00. 1 policy failure(s) … Suggested: request changes.",
  "risk_score": 40.0, "risk_band": "medium",
  "policy_compliant": false,
  "duplicate_likelihood": 0.0, "duplicate_band": "none",
  "missing_info": ["1 line item(s) fail policy (e.g. over a cap)."],
  "recommended_action": "request_changes", "confidence": "medium",
  "rationale": {
    "why": "There are policy failures or missing receipts that should be fixed before approval.",
    "data_analyzed": ["1 line item ($676.00 total)", "0 missing receipts", "3 prior items checked", "agency baseline policy"],
    "policies_considered": ["OVER_MEAL_LIMIT"], "total_at_risk": "$676.00"
  }
}
```

Risk score is a transparent weighted sum (policy failures, missing receipts, duplicate signal,
large amounts, warnings), clamped 0–100 and banded low/medium/high.

## Security & guardrails (Phase 7 + 10)

- **Advisory only** — structurally guaranteed: no `/ai` endpoint mutates a sheet; the engine has
  no path to approve/reject/modify. Tests assert this (`test_ai_router_exposes_no_mutating_endpoint`,
  `test_recommendation_does_not_change_sheet_state`).
- **RBAC respected** — `/ai/sheets/{id}/recommendation` uses the same `assert_can_view_sheet`; the
  workspace/analytics are scoped (employee → own, manager → agency, finance/admin → all). An
  employee can't read another user's recommendation (`test_employee_cannot_read_another_users_recommendation`).
- **Everything logged** — each generation writes `AI_RECOMMENDATION_GENERATED`; feedback writes
  `AI_FEEDBACK_RECORDED` (`test_every_recommendation_is_audit_logged`).
- **No data leakage** — recommendations use titles/plain language; the token is never involved
  beyond the caller's own request.
- **Resilience** — AI events are defensive (never raise); SQLite runs WAL + a busy timeout so the
  new concurrent writes don't contend; in production (Postgres) this is a non-issue.

## Tests (Phase 9/10)

`api/tests/test_ai_platform.py` (10): recommendation structure + explainability, over-cap →
high-risk + `request_changes`, advisory-only (no mutating endpoint, no state change), RBAC denial,
audit logging, event → recommendation + manager notification, workspace shape/scoping, feedback,
analytics. **Full API suite: 136 passed (stable across repeated runs); MCP: 50.** AI Workspace
verified in the browser (Playwright).

## Known limitations / deferred (honest)

- **Time-based jobs** (submission-deadline reminders, daily finance summaries) need a scheduler;
  the computation exists (`ai_recommendations` / analytics) and a cron/worker can call it — not
  wired here.
- **LLM narrative** — summaries are deterministic today; Azure Foundry plugs in behind the same
  recommendation contract.
- **Admin login-anomaly / integration-failure monitoring** needs auth-event + integration logs
  that aren't modeled yet; `server_health` + activity are exposed as the starting point.
- **In tests**, background event *wiring* is disabled (`APP_AI_BACKGROUND_EVENTS=false`) to avoid
  shared-SQLite contention; the event handler is exercised directly instead. It is on in dev/prod.

## Deployment

The agentic layer ships with the API (no new infra): tables auto-create (`AiRecommendation`,
`AiFeedback`), events run as FastAPI background tasks. Set `APP_AI_BACKGROUND_EVENTS=false` to
disable proactive events (recommendations still generate on-read). The frontend AI Workspace
appears under each role's "Intelligence" nav section.
