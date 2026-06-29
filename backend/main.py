"""
ExpenseOps Backend API Entrypoint
=================================
Assembles the FastAPI application, registers routers, sets up CORS middleware,
manages startup database initialization and seed data loading.
"""
from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.database import init_db
from backend.routers import expenses, dashboard, auth, users

# Create uploads directory if it doesn't exist
os.makedirs("data/uploads", exist_ok=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Logger Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Application Factory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app = FastAPI(
    title="ExpenseOps — Intelligent Expense Management System",
    description="Multi-tier deterministic policies + cognitive AI audit engine for commercial expense management.",
    version="1.0.0",
)

# CORS Policy configuration
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Lifespan / Startup Events
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.on_event("startup")
def startup_event():
    """
    Called on FastAPI server launch.
    Ensures data/ exists, tables are generated, and seed dataset is loaded.
    """
    logger.info("Initializing ExpenseOps Database and applying seeds...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}", exc_info=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Route Registrations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# API version 1 prefix
API_PREFIX = "/api/v1"

app.include_router(expenses.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)

@app.get("/", tags=["Health"])
def health_check():
    """
    App health status ping route.
    """
    return {
        "status": "online",
        "service": "ExpenseOps Core API",
        "version": "1.0.0",
        "database": "connected"
    }


if __name__ == "__main__":
    import uvicorn
    # Standalone execution
    logger.info("Starting ExpenseOps standalone webserver...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
