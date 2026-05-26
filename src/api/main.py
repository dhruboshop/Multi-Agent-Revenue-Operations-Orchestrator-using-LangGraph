"""
FastAPI application for Multi-Agent RevOps Orchestrator.

Exposes:
- POST /run          → Trigger a full graph execution (manual or scheduled)
- GET  /status/{id}  → Retrieve result + audit trail for a specific run
- GET  /status/latest → Most recent successful run
- GET  /health       → Liveness + dependency checks
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.api.routes import trigger, status
from src.config.settings import get_settings
from src.database.connection import check_connection, init_db
from src.graph.orchestrator import invoke_graph
from src.scheduler.weekly_job import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting RevOps Orchestrator API...")
    init_db(create_tables=True)

    if settings.scheduler_enabled:
        start_scheduler()

    yield

    logger.info("Shutting down RevOps Orchestrator API...")
    if settings.scheduler_enabled:
        stop_scheduler()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(trigger.router, tags=["execution"])
app.include_router(status.router, tags=["status"])


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, Any]:
    """Liveness probe + dependency status."""
    db_ok = check_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.api_version,
        "database": "connected" if db_ok else "disconnected",
        "scheduler_enabled": settings.scheduler_enabled,
        "demo_mode": settings.demo_mode,
    }


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "message": "Multi-Agent RevOps Orchestrator",
        "docs": "/docs",
        "health": "/health",
        "trigger": "POST /run",
    }
