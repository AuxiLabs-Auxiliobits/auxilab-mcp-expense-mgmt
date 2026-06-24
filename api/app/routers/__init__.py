from app.routers import (
    admin,
    attachments,
    audit,
    auth,
    finance,
    health,
    manager,
    meta,
    notifications,
    policy,
    reports,
    sheets,
)

ALL_ROUTERS = [
    health.router,
    auth.router,
    sheets.router,
    manager.router,
    finance.router,
    policy.router,
    admin.router,
    meta.router,
    reports.router,
    audit.router,
    notifications.router,
    attachments.router,
]
