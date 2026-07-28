"""Local forgot/reset-password flow: generic responses (no enumeration), single-use +
time-limited tokens, complexity enforcement, and SSO-user detection."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.config import settings as app_settings
from app.db import engine
from app.models.base import utcnow
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services import password_reset_service as prs
from tests.conftest import auth, login


class CapturingSender:
    """Test EmailSender that records the last message so we can read the reset link."""

    def __init__(self):
        self.last = None

    def send(self, *, to, subject, body):
        self.last = {"to": to, "subject": subject, "body": body}


def _link_token(body: str) -> str:
    # body contains ".../reset-password?token=<raw>"
    marker = "token="
    return body.split(marker, 1)[1].split()[0]


def _make_local_user(client, email="reset.user@demo.local", password="OldPassw0rd"):
    admin = login(client, "admin@demo.local")
    client.post(
        "/admin/users",
        json={"name": "Reset User", "email": email, "role": "employee", "password": password},
        headers=auth(admin),
    )
    return email


# --- routes ----------------------------------------------------------------- #
def test_login_methods_db_mode(client):
    body = client.get("/auth/login-methods").json()
    assert body["password"] is True and body["sso"] is False  # default db mode


def test_forgot_password_is_generic_and_non_enumerating(client):
    msg_known = client.post("/auth/forgot-password", json={"email": "employee@demo.local"})
    msg_unknown = client.post("/auth/forgot-password", json={"email": "ghost@nowhere.local"})
    assert msg_known.status_code == 200 and msg_unknown.status_code == 200
    assert msg_known.json()["message"] == msg_unknown.json()["message"]  # identical → no leak


def test_reset_with_invalid_token_rejected(client):
    r = client.post("/auth/reset-password", json={"token": "not-a-real-token", "new_password": "Abcd12345!"})
    assert r.status_code == 400


# --- end-to-end service + login -------------------------------------------- #
def test_full_reset_flow_then_login(client):
    email = _make_local_user(client)
    sender = CapturingSender()
    with Session(engine) as s:
        prs.request_reset(s, app_settings, sender, email)
    assert sender.last and sender.last["to"] == email
    raw = _link_token(sender.last["body"])

    # New password takes effect; old one stops working.
    new_pw = "BrandNewPass1"
    r = client.post("/auth/reset-password", json={"token": raw, "new_password": new_pw})
    assert r.status_code == 200, r.text
    assert client.post("/auth/login", json={"email": email, "password": new_pw}).status_code == 200
    assert client.post("/auth/login", json={"email": email, "password": "OldPassw0rd"}).status_code == 401

    # Token is single-use — a replay fails.
    assert client.post("/auth/reset-password", json={"token": raw, "new_password": "AnotherPass2"}).status_code == 400


def test_weak_password_rejected(client):
    email = _make_local_user(client, email="reset.weak@demo.local")
    sender = CapturingSender()
    with Session(engine) as s:
        prs.request_reset(s, app_settings, sender, email)
    raw = _link_token(sender.last["body"])
    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "short"})
    assert r.status_code == 422  # complexity failure


def test_expired_token_rejected(client):
    email = _make_local_user(client, email="reset.exp@demo.local")
    sender = CapturingSender()
    with Session(engine) as s:
        prs.request_reset(s, app_settings, sender, email)
        raw = _link_token(sender.last["body"])
        # Force-expire the freshly issued token.
        tok = s.exec(
            select(PasswordResetToken).order_by(PasswordResetToken.created_at.desc())
        ).first()
        tok.expires_at = utcnow() - timedelta(minutes=1)
        s.add(tok)
        s.commit()
    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "ValidPass123"})
    assert r.status_code == 400


def test_sso_only_user_gets_no_reset_link(client):
    """A federated account (no local password) is never issued a reset link."""
    with Session(engine) as s:
        u = User(name="SSO Only", email="sso.only@demo.local", role="employee",
                 agency_id=None, password_hash=None, is_active=True, entra_object_id="oid-sso-1")
        s.add(u)
        s.commit()
    sender = CapturingSender()
    with Session(engine) as s:
        prs.request_reset(s, app_settings, sender, "sso.only@demo.local")
    assert sender.last is None  # no email sent
