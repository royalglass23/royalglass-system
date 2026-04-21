"""
main.py
FastAPI application entry point.

This file creates the app, registers all routers, and adds the health check.
Uvicorn runs this file when the Docker container starts.
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import check_db_connection
from app.auth import get_current_user
from app.routers import router_auth as auth, router_dashboard as dashboard, router_items as items


app = FastAPI(
    title="Royal Glass Work Order API",
    description="Backend API for the Royal Glass work order dashboard.",
    version="1.0.0",
    # Disable the interactive docs in production
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# CORS controls which domains can call this API from a browser.
# In development, we allow localhost on the Next.js port (3000).
# In production, this should be locked to royalglass.co.nz.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",       # Next.js dev server
        "https://royalglass.co.nz",   # Production (when deployed)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
# Each router handles a logical group of endpoints.
# Prefix is already set inside each router file.
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(items.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    """
    Confirms the API is running and can reach the database.
    Used by Docker health checks and n8n to verify the API is alive.
    """
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "api": "running",
        "database": "connected" if db_ok else "unreachable",
        "environment": settings.app_env,
    }


# ── Protected test endpoint ───────────────────────────────────────────────────
@app.get("/me", tags=["System"])
def get_me(user: dict = Depends(get_current_user)):
    """
    Returns the current logged-in user details.
    Useful for testing that auth is working correctly.
    """
    return {"name": user["name"], "email": user["email"], "role": user["role"]}
