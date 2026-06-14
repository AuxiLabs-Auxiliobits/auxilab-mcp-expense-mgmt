# ADR-001: Identity & Authentication Strategy

**Status:** Accepted (interim) · **Date:** 2026-06-14

## Context

SCOPING §9 specifies **Microsoft Entra External ID** as the identity broker (Google /
Microsoft / SSO federation, role claims). For early build we want to move fast without
standing up the External ID tenant, social IdP registrations, and token plumbing — and we
need a `users` table with roles, departments, and other profile columns regardless.

## Decision

**Defer Entra External ID. Use DB-backed identity now, behind a pluggable auth provider, so
migrating to Entra later is a config flip — not a rewrite.**

Key insight: Entra is only the **authenticator** (verifies login, issues the token). The
database is the **system of record** for user profile/role/department either way — even with
Entra we mirror users locally (SCOPING §8.1 already has a `users` table). So this is not
DB-vs-Entra; it's only *who verifies the password and mints the JWT*.

## The contract that makes migration trivial

All app code depends on a normalized principal, never on the issuer:

```python
class Principal(BaseModel):
    subject_id: str        # users.id (now) → maps to Entra `oid` later
    email: str
    role: Role             # employee | manager | finance | auditor | agent
    department: str | None # profile metadata (see RBAC note below)
    scope: Scope           # self | all   (derived from role)
```

JWT claims are shaped to mirror what Entra emits — `sub`, `email`, `roles`, plus a custom
`department` claim — so the resource-server side is identical regardless of issuer.

### Pluggable provider

```
AuthProvider (interface)
├── DbAuthProvider     # NOW: verify password (argon2) vs users table, issue our own JWT
└── EntraAuthProvider  # LATER: validate Entra JWT via JWKS, map roles/groups → Role enum
```

The FastAPI auth dependency resolves whichever provider `AUTH_PROVIDER` env var selects.
Routes, data-query filtering, and RAG security trimming consume `Principal` only.

## Migration path to Entra (when ready)

1. Stand up the External ID tenant; register Google/Microsoft IdPs; define app roles.
2. Backfill `users.entra_object_id` by matching on `email`.
3. Map Entra app-role/group claims → our `Role` enum in `EntraAuthProvider`.
4. Flip `AUTH_PROVIDER=entra`. Token validation now uses Entra JWKS.
5. Retire local password columns once all users are federated.

No schema change to the rest of the app; no business-logic change.

## Trade-offs accepted while on DbAuthProvider

- We hand-roll password hashing (argon2id), reset, and lockout — real security surface.
- No SSO / social login / MFA until Entra is in.
- **Therefore:** DB-backed for dev/early build only; **Entra before real users onboard.**

## ⚠️ Open question for requirements owner

SCOPING §3 is **role-based, no team/department hierarchy** (scope = self | all). Adding
`department` as *profile metadata* is harmless. But if `department` is meant to **restrict
visibility** (e.g. a manager sees only their department's claims), that changes the self/all
scope model and must be confirmed before it's baked into RBAC + RAG security trimming.
