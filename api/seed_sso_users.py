"""Provision the Auxilabs/Auxicore/Auxiflow agencies and their 10 SSO users in the DB.

Roles live in OUR database (Microsoft only authenticates). This mirrors the Entra users
created in the tenant: each DB row is keyed on the user's UPN (which is what the token's
email/preferred_username claim carries for these managed cloud accounts).

Run from the repo root so it uses the seeded ./expense.db:
    PYTHONPATH=api .venv/Scripts/python.exe api/seed_sso_users.py
Idempotent — re-running updates existing agencies/users instead of duplicating.
"""

from __future__ import annotations

from sqlmodel import Session, create_engine, select

from app.config import settings
from app.models.agency import Agency
from app.models.user import User
from app.principal import Role

DOMAIN = "parteekkumaraigmail.onmicrosoft.com"
AGENCIES = ["Auxilabs", "Auxicore", "Auxiflow"]

# (display name, local part, role, agency). Local part is name.role on the verified
# tenant domain (custom agency domains aren't owned/verifiable — see Option B).
ROSTER = [
    ("Ankit",  "ankit.employee",  Role.EMPLOYEE, "Auxilabs"),
    ("Riya",   "riya.employee",   Role.EMPLOYEE, "Auxicore"),
    ("Sahil",  "sahil.employee",  Role.EMPLOYEE, "Auxiflow"),
    ("Manish", "manish.manager",  Role.MANAGER,  "Auxilabs"),
    ("Pooja",  "pooja.manager",   Role.MANAGER,  "Auxicore"),
    ("Vikram", "vikram.manager",  Role.MANAGER,  "Auxiflow"),
    ("Neha",   "neha.finance",    Role.FINANCE,  "Auxilabs"),
    ("Arjun",  "arjun.finance",   Role.FINANCE,  "Auxicore"),
    ("Sonia",  "sonia.finance",   Role.FINANCE,  "Auxiflow"),
    ("Aditya", "aditya.admin",    Role.ADMIN,    "Auxilabs"),
]


def main() -> None:
    engine = create_engine(settings.database_url)
    with Session(engine) as s:
        # 1) Agencies
        agency_ids: dict[str, str] = {}
        for name in AGENCIES:
            a = s.exec(select(Agency).where(Agency.name == name)).first()
            if a is None:
                a = Agency(name=name)
                s.add(a)
                s.commit()
                s.refresh(a)
                print(f"Agency CREATED: {name} ({a.id})")
            else:
                print(f"Agency exists:  {name} ({a.id})")
            agency_ids[name] = a.id

        # 2) Users (keyed on UPN/email). Admins span all agencies → no single agency.
        for display, local, role, agency in ROSTER:
            email = f"{local}@{DOMAIN}".lower()
            agency_id = None if role == Role.ADMIN else agency_ids[agency]
            u = s.exec(select(User).where(User.email == email)).first()
            action = "UPDATED" if u else "CREATED"
            if u is None:
                u = User(
                    name=display, email=email, role=role, agency_id=agency_id,
                    is_active=True, source="azure",  # SSO accounts → hybrid routes to Microsoft
                )
                s.add(u)
            else:
                u.name, u.role, u.agency_id, u.is_active = display, role, agency_id, True
                u.source = "azure"
            s.commit()
            print(f"User {action}: {email:<52} {role.value:<9} {agency if agency_id else 'ALL'}")


if __name__ == "__main__":
    main()
