"""Add or update an application user (role + agency) for Entra SSO login.

Roles are stored in OUR database; Microsoft only authenticates. When a person
signs in with Microsoft, the backend matches their email to a row here and
applies that role — the DB role always wins (ADR-001, DB-by-email).

Usage (run from the repo root so it uses ./expense.db):
    .venv/Scripts/python.exe api/add_user.py "Parteek" parteek@yourtenant.com employee Crispin
    .venv/Scripts/python.exe api/add_user.py "Ankit"   ankit@yourtenant.com   manager  Crispin

Args: <full name> <email> <role: employee|manager|finance|admin> [agency name=Crispin]
Re-running with the same email updates the existing user (idempotent).
"""

from __future__ import annotations

import sys

from sqlmodel import Session, create_engine, select

from app.config import settings
from app.models.agency import Agency
from app.models.user import User
from app.principal import Role

ROLE_MAP = {
    "employee": Role.EMPLOYEE,
    "manager": Role.MANAGER,
    "finance": Role.FINANCE,
    "admin": Role.ADMIN,
}


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    name = sys.argv[1]
    email = sys.argv[2].strip().lower()
    role_key = sys.argv[3].strip().lower()
    agency_name = sys.argv[4] if len(sys.argv) > 4 else "Crispin"

    if role_key not in ROLE_MAP:
        print(f"Invalid role '{role_key}'. Use one of: {', '.join(ROLE_MAP)}")
        sys.exit(1)
    role = ROLE_MAP[role_key]

    engine = create_engine(settings.database_url)
    with Session(engine) as s:
        agency = s.exec(select(Agency).where(Agency.name == agency_name)).first()
        if not agency:
            names = [a.name for a in s.exec(select(Agency)).all()]
            print(f"Agency '{agency_name}' not found. Available: {', '.join(names)}")
            sys.exit(1)

        user = s.exec(select(User).where(User.email == email)).first()
        action = "Updated" if user else "Created"
        if user:
            user.name = name
            user.role = role
            user.agency_id = agency.id
            user.is_active = True
        else:
            user = User(name=name, email=email, role=role, agency_id=agency.id, is_active=True)
            s.add(user)
        s.commit()
        s.refresh(user)
        print(f"{action}: {user.email}  role={user.role}  agency={agency.name} ({agency.id})")


if __name__ == "__main__":
    main()
