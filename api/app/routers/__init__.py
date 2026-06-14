from app.routers import admin, auth, finance, health, manager, policy, sheets

ALL_ROUTERS = [
    health.router,
    auth.router,
    sheets.router,
    manager.router,
    finance.router,
    policy.router,
    admin.router,
]
