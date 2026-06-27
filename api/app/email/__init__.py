"""Email delivery package."""

from app.email.sender import (
    ConsoleEmailSender,
    EmailSender,
    SmtpEmailSender,
    get_email_sender,
)

__all__ = ["EmailSender", "ConsoleEmailSender", "SmtpEmailSender", "get_email_sender"]
