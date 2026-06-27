"""Pluggable email delivery (SCOPING §3 — local password reset).

`EmailSender` is the seam; two backends implement it:
  • ConsoleEmailSender — logs the message (dev/offline; zero infra, fully testable).
  • SmtpEmailSender    — sends via a configured SMTP server (staging/prod).

`get_email_sender(settings)` picks the backend from APP_EMAIL_BACKEND so the rest of the app
never imports smtplib or knows which transport is in use.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.config import Settings

logger = logging.getLogger("app.email")


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Writes the email to the logs instead of sending it. The reset link is visible in
    the server console — perfect for local development and automated tests."""

    def __init__(self, sender: str) -> None:
        self._from = sender

    def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info(
            "\n----- EMAIL (console backend) -----\nFrom: %s\nTo: %s\nSubject: %s\n\n%s\n"
            "-----------------------------------",
            self._from, to, subject, body,
        )


class SmtpEmailSender:
    def __init__(self, *, host: str, port: int, user: str, password: str, sender: str, use_tls: bool) -> None:
        self._host, self._port = host, port
        self._user, self._password = user, password
        self._from, self._use_tls = sender, use_tls

    def send(self, *, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(msg)
        logger.info("Sent email to %s via SMTP", to)


def get_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password,
            sender=settings.email_from,
            use_tls=settings.smtp_use_tls,
        )
    return ConsoleEmailSender(settings.email_from)
