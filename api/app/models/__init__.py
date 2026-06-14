"""SQLModel table definitions (SCOPING §12.1). Importing this package registers all
tables on SQLModel.metadata."""

from app.models.agency import Agency
from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.claim_check import ClaimCheck
from app.models.decision import Decision
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.models.policy import AgencyPolicy
from app.models.user import User

__all__ = [
    "Agency",
    "Attachment",
    "AuditLog",
    "ClaimCheck",
    "Decision",
    "ExpenseSheet",
    "LineItem",
    "AgencyPolicy",
    "User",
]
