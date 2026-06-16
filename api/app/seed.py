"""Idempotent demo seed (SCOPING §17). Creates agencies Crispin/SKDK/JetFuel and one user
per role, so the API is explorable immediately in dev. Never runs in prod by default."""

from __future__ import annotations

from argon2 import PasswordHasher
from sqlmodel import Session, select

from app.models.agency import Agency
from app.models.user import User
from app.principal import Role

_ph = PasswordHasher()
_DEMO_PASSWORD = "demo"  # noqa: S105 — dev-only seed


def seed_demo(session: Session) -> None:
    if session.exec(select(Agency)).first():
        return  # already seeded

    agencies = {name: Agency(name=name) for name in ("Crispin", "SKDK", "JetFuel")}
    for a in agencies.values():
        session.add(a)
    session.flush()

    crispin = agencies["Crispin"].id
    users = [
        ("Eve Employee", "employee@demo.local", Role.EMPLOYEE, crispin),
        ("Mona Manager", "manager@demo.local", Role.MANAGER, crispin),
        ("Fin Finance", "finance@demo.local", Role.FINANCE, crispin),
        ("Ada Admin", "admin@demo.local", Role.ADMIN, crispin),
        # AGENT (LLM approver) — a dev login so the worker-only webhooks
        # (POST /finance/sheets/{id}/llm-decision, POST /finance/policies/{id}/indexed)
        # are exercisable from Swagger; in prod this is a real service principal.
        ("Auto Approver", "agent@demo.local", Role.AGENT, crispin),
    ]
    for name, email, role, agency_id in users:
        session.add(
            User(name=name, email=email, role=role, agency_id=agency_id,
                 password_hash=_ph.hash(_DEMO_PASSWORD))
        )
    session.commit()
