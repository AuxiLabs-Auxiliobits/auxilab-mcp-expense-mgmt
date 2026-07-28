"""Idempotent demo seed (SCOPING §17). Creates agencies Crispin/SKDK/JetFuel and one user
per role, so the API is explorable immediately in dev. Never runs in prod by default."""

from __future__ import annotations

from argon2 import PasswordHasher
from sqlmodel import Session, select

from app.models.agency import Agency
from app.models.user import User
from app.principal import Role

_ph = PasswordHasher(memory_cost=16384, time_cost=2, parallelism=1)
_DEMO_PASSWORD = "demo"  # noqa: S105 — dev-only seed


def seed_demo(session: Session) -> None:
    if session.exec(select(Agency)).first():
        return  # already seeded

    agencies = {name: Agency(name=name) for name in ("Crispin", "SKDK", "JetFuel")}
    for a in agencies.values():
        session.add(a)
    session.flush()

    crispin = agencies["Crispin"].id
    skdk = agencies["SKDK"].id
    users = [
        ("Eve Employee", "employee@demo.local", Role.EMPLOYEE, crispin),
        ("Mona Manager", "manager@demo.local", Role.MANAGER, crispin),
        ("Fin Finance", "finance@demo.local", Role.FINANCE, crispin),
        ("Ada Admin", "admin@demo.local", Role.ADMIN, crispin),
        # AGENT (LLM approver) — a dev login so the worker-only webhooks
        # (POST /finance/sheets/{id}/llm-decision, POST /finance/policies/{id}/indexed)
        # are exercisable from Swagger; in prod this is a real service principal.
        ("Auto Approver", "agent@demo.local", Role.AGENT, crispin),
        # A second agency (SKDK) so cross-agency scoping is demonstrable: an SKDK employee's
        # submissions reach the SKDK manager only, never Crispin's (SCOPING §3.3, §19.1).
        ("Sam Employee", "employee.skdk@demo.local", Role.EMPLOYEE, skdk),
        ("Maya Manager", "manager.skdk@demo.local", Role.MANAGER, skdk),
    ]
    # Per-agency roster so every agency (not just Crispin) has its own manager, finance, and
    # employees — lets you demo agency-scoped routing end to end: an agency's employee submits,
    # only that agency's manager(s) see it (SCOPING §3.3, §19.1). Emails are slug-prefixed
    # (e.g. jetfuel.manager@demo.local) so they never collide with the named logins above.
    for ag_name, ag in agencies.items():
        slug = "".join(ch for ch in ag_name.lower() if ch.isalnum())
        users += [
            (f"{ag_name} Manager", f"{slug}.manager@demo.local", Role.MANAGER, ag.id),
            (f"{ag_name} Finance", f"{slug}.finance@demo.local", Role.FINANCE, ag.id),
            (f"{ag_name} Employee One", f"{slug}.emp1@demo.local", Role.EMPLOYEE, ag.id),
            (f"{ag_name} Employee Two", f"{slug}.emp2@demo.local", Role.EMPLOYEE, ag.id),
        ]

    for name, email, role, agency_id in users:
        session.add(
            User(name=name, email=email, role=role, agency_id=agency_id,
                 password_hash=_ph.hash(_DEMO_PASSWORD))
        )
    session.commit()
