"""Federated (OIDC/Entra) auth: token validation + DB-by-email JIT provisioning + role mapping.

The interactive flow lives at the IdP; here we exercise the backend's job — verify a
provider-issued RS256 token against a (mocked) JWKS and resolve it to a Principal via our
users table. Uses a throwaway RSA keypair and a fake JWKS client so no tenant is needed.
"""

from __future__ import annotations

import asyncio
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlmodel import Session, select

import app.auth.oidc_provider as oidc_mod
from app.auth.base import AuthError
from app.auth.oidc_provider import OidcAuthProvider, OidcConfig
from app.auth.provisioning import OidcProvisioner
from app.auth.role_mapping import RoleMapper
from app.config import settings as app_settings
from app.db import engine
from app.models.agency import Agency
from app.models.user import User
from app.principal import Role

ISS = "https://idp.example.com/realms/auxilab"
AUD = "expense-api"


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, key.public_key()


def _token(priv, *, oid, email, name="Test User", roles=None, groups=None, aud=AUD, exp_delta=3600):
    now = int(time.time())
    claims = {"iss": ISS, "aud": aud, "sub": oid, "oid": oid, "email": email,
              "name": name, "iat": now, "exp": now + exp_delta}
    if roles is not None:
        claims["roles"] = roles
    if groups is not None:
        claims["groups"] = groups
    return jwt.encode(claims, priv, algorithm="RS256")


class _FakeJwks:
    def __init__(self, pub):
        self._pub = pub

    def get_signing_key_from_jwt(self, _token):  # mimics PyJWKClient
        return type("K", (), {"key": self._pub})()


def _cfg():
    return OidcConfig(
        issuer=ISS, audience=AUD, jwks_url="https://idp.example.com/jwks", algorithms=["RS256"],
        email_claim="email", subject_claim="oid", name_claim="name",
        roles_claim="roles", groups_claim="groups",
    )


def _provider(monkeypatch, pub, session, settings, role_map="{}"):
    monkeypatch.setattr(oidc_mod, "_jwks_client", lambda url: _FakeJwks(pub))
    return OidcAuthProvider(_cfg(), RoleMapper(role_map), OidcProvisioner(session, settings))


def _verify(provider, token):
    return asyncio.run(provider.verify(token))


# --------------------------------------------------------------------------- #
def test_existing_user_matched_by_email_and_linked(client, monkeypatch):
    """A federated login for a known email resolves to that DB user, links the IdP subject,
    and uses the DB role (NOT any role claim in the token)."""
    priv, pub = _keypair()
    with Session(engine) as s:
        provider = _provider(monkeypatch, pub, s, app_settings)
        # token claims a bogus 'admin' role — DB role must still win.
        tok = _token(priv, oid="oid-emp-001", email="employee@demo.local", roles=["admin"])
        principal = _verify(provider, tok)

        assert principal.role is Role.EMPLOYEE  # DB wins over the token's 'admin' claim
        assert principal.email == "employee@demo.local"
        assert principal.agency_id  # agency came from the DB

        linked = s.exec(select(User).where(User.email == "employee@demo.local")).first()
        assert linked.entra_object_id == "oid-emp-001"  # subject linked for next time


def test_second_login_matches_by_subject_even_if_email_changes(client, monkeypatch):
    priv, pub = _keypair()
    with Session(engine) as s:
        provider = _provider(monkeypatch, pub, s, app_settings)
        _verify(provider, _token(priv, oid="oid-mgr-009", email="manager@demo.local"))
        # Same subject, different email → still the same (linked) user.
        principal = _verify(provider, _token(priv, oid="oid-mgr-009", email="changed@demo.local"))
        assert principal.email == "manager@demo.local"
        assert principal.role is Role.MANAGER


def test_unprovisioned_user_denied_when_auto_provision_off(client, monkeypatch):
    priv, pub = _keypair()
    with Session(engine) as s:
        provider = _provider(monkeypatch, pub, s, app_settings)  # auto_provision defaults off
        with pytest.raises(AuthError, match="administrator"):
            _verify(provider, _token(priv, oid="oid-new-1", email="nobody-new@demo.local"))


def test_jit_autoprovision_with_super_admin_maps_to_admin(client, monkeypatch):
    """With auto-provision on + a default agency, a brand-new user is created, and a
    'Super Admin' app-role maps to the Admin application role."""
    priv, pub = _keypair()
    with Session(engine) as s:
        agency = s.exec(select(Agency)).first()
        settings = app_settings.model_copy(
            update={"oidc_auto_provision": True, "oidc_default_agency_id": agency.id}
        )
        provider = _provider(monkeypatch, pub, s, settings)
        principal = _verify(
            provider,
            _token(priv, oid="oid-sa-1", email="super.new@demo.local", roles=["Super Admin"]),
        )
        assert principal.role is Role.ADMIN
        created = s.exec(select(User).where(User.email == "super.new@demo.local")).first()
        assert created is not None and created.password_hash is None  # federated, no local pw


def test_invalid_audience_rejected(client, monkeypatch):
    priv, pub = _keypair()
    with Session(engine) as s:
        provider = _provider(monkeypatch, pub, s, app_settings)
        with pytest.raises(AuthError, match="invalid token"):
            _verify(provider, _token(priv, oid="x", email="employee@demo.local", aud="wrong-aud"))


def test_expired_token_rejected(client, monkeypatch):
    priv, pub = _keypair()
    with Session(engine) as s:
        provider = _provider(monkeypatch, pub, s, app_settings)
        with pytest.raises(AuthError, match="expired"):
            _verify(provider, _token(priv, oid="x", email="employee@demo.local", exp_delta=-10))


# --- role mapper unit ------------------------------------------------------- #
def test_role_mapper_super_admin_and_precedence():
    mapper = RoleMapper(json.dumps({"Finance Approvers": "finance", "grp-guid-mgr": "manager"}))
    assert mapper.map("Super Admin") is Role.ADMIN          # built-in alias
    assert mapper.map("Finance Approvers") is Role.FINANCE  # configured
    assert mapper.map("grp-guid-mgr") is Role.MANAGER       # group guid
    # Most-privileged wins when several map.
    assert mapper.map("employee", "Finance Approvers") is Role.FINANCE
    assert mapper.map("unknown-thing") is None
