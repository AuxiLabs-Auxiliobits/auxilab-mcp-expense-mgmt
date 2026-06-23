from app.routers import (
    admin,
    auth,
    finance,
    health,
    intake,
    manager,
    meta,
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
    intake.router,
]
