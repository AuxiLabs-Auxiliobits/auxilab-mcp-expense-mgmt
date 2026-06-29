"""Idempotent demo seed (SCOPING §17). Creates agencies Auxilabs/Auxicore/Auxiflow and one
user per role, so the API is explorable immediately in dev. Never runs in prod by default.

Agency IDs are deterministic (fixed hex) so the policy_docs/ seed directory can be committed
alongside the code and run without first querying the DB for UUIDs."""

from __future__ import annotations

from argon2 import PasswordHasher
from sqlmodel import Session, select

from app.models.agency import Agency
from app.models.user import User
from app.principal import Role

_ph = PasswordHasher(memory_cost=16384, time_cost=2, parallelism=1)
_DEMO_PASSWORD = "demo"  # noqa: S105 — dev-only seed

# Deterministic IDs — fixed so policy_docs/ subfolders can be committed alongside the code.
# Must be valid 32-char hex strings (only 0-9 a-f). Regenerate with:
#   python -c "import uuid; print(uuid.uuid4().hex)"
AUXILABS_ID = "6edf75fcbdf541f19734a6229a3aeb38"
AUXICORE_ID = "5457afdf9ee846b1afc873ef71ff0c71"
AUXIFLOW_ID = "f7011ac2f6f242529260e410c6355bb1"

_AGENCIES: dict[str, str] = {
    "Auxilabs": AUXILABS_ID,
    "Auxicore": AUXICORE_ID,
    "Auxiflow": AUXIFLOW_ID,
}


def seed_demo(session: Session) -> None:
    if session.exec(select(Agency)).first():
        return  # already seeded

    agencies = {name: Agency(id=aid, name=name) for name, aid in _AGENCIES.items()}
    for a in agencies.values():
        session.add(a)
    session.flush()

    primary = agencies["Auxilabs"].id  # primary demo agency (shared logins below)
    users = [
        ("Eve Employee",  "employee@demo.local", Role.EMPLOYEE, primary),
        ("Mona Manager",  "manager@demo.local",  Role.MANAGER,  primary),
        ("Fin Finance",   "finance@demo.local",  Role.FINANCE,  primary),
        ("Ada Admin",     "admin@demo.local",     Role.ADMIN,    primary),
        # AGENT (LLM approver) — a dev login so the worker-only webhooks
        # (POST /finance/sheets/{id}/llm-decision, POST /finance/policies/{id}/indexed)
        # are exercisable from Swagger; in prod this is a real service principal.
        ("Auto Approver", "agent@demo.local",     Role.AGENT,    primary),
    ]
    # Per-agency roster — lets you demo agency-scoped routing end-to-end:
    # an agency's employee submits, only that agency's manager(s) see it (SCOPING §3.3, §19.1).
    for ag_name, ag in agencies.items():
        slug = "".join(ch for ch in ag_name.lower() if ch.isalnum())
        users += [
            (f"{ag_name} Manager",      f"{slug}.manager@demo.local", Role.MANAGER,  ag.id),
            (f"{ag_name} Finance",      f"{slug}.finance@demo.local", Role.FINANCE,  ag.id),
            (f"{ag_name} Employee One", f"{slug}.emp1@demo.local",    Role.EMPLOYEE, ag.id),
            (f"{ag_name} Employee Two", f"{slug}.emp2@demo.local",    Role.EMPLOYEE, ag.id),
        ]

    for name, email, role, agency_id in users:
        session.add(
            User(name=name, email=email, role=role, agency_id=agency_id,
                 password_hash=_ph.hash(_DEMO_PASSWORD))
        )
    session.commit()
