"""
Status endpoints for querying past graph runs.

GET /status/{run_id}
GET /status/latest
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.database.models import RunLog

router = APIRouter()


class RunLogEntry(BaseModel):
    node_name: str
    status: str
    started_at: str
    execution_time_ms: int | None = None
    output_summary: str | None = None


class StatusResponse(BaseModel):
    run_id: str
    logs: list[RunLogEntry]
    latest_state: dict[str, Any] | None = None


@router.get("/status/{run_id}", response_model=StatusResponse)
async def get_run_status(run_id: str, db: Session = get_db) -> StatusResponse:
    """Return full audit trail for a specific run."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format")

    logs = (
        db.query(RunLog)
        .filter(RunLog.run_id == rid)
        .order_by(RunLog.started_at.asc())
        .all()
    )

    if not logs:
        raise HTTPException(status_code=404, detail=f"No logs found for run_id {run_id}")

    entries = [
        RunLogEntry(
            node_name=log.node_name,
            status=log.status,
            started_at=log.started_at.isoformat(),
            execution_time_ms=log.execution_time_ms,
            output_summary=log.output_summary,
        )
        for log in logs
    ]

    return StatusResponse(run_id=run_id, logs=entries)


@router.get("/status/latest", response_model=StatusResponse)
async def get_latest_run(db: Session = get_db) -> StatusResponse:
    """Return the most recent run (by started_at)."""
    latest_log = db.query(RunLog).order_by(RunLog.started_at.desc()).first()

    if not latest_log:
        raise HTTPException(status_code=404, detail="No runs found in the system")

    return await get_run_status(str(latest_log.run_id), db)
