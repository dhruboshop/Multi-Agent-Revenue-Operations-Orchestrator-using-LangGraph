"""
POST /run endpoint — manually trigger a full RevOps graph execution.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from src.graph.orchestrator import invoke_graph
from src.graph.state import create_initial_state

router = APIRouter()
logger = logging.getLogger(__name__)


class TriggerResponse(BaseModel):
    run_id: str
    status: str
    message: str


@router.post("/run", response_model=TriggerResponse)
async def trigger_run(background_tasks: BackgroundTasks) -> TriggerResponse:
    """
    Trigger a complete end-to-end RevOps intelligence cycle.

    The graph runs asynchronously in a background task so the HTTP request
    returns immediately with the run_id.
    """
    run_id = str(uuid.uuid4())
    logger.info(f"Manual trigger received — run_id={run_id}")

    def _run_graph() -> None:
        try:
            state = create_initial_state(run_id=run_id)
            final = invoke_graph(initial_state=state, thread_id=f"manual-{run_id}")
            logger.info(f"Manual run {run_id} completed successfully")
        except Exception as e:
            logger.exception(f"Manual run {run_id} failed: {e}")

    background_tasks.add_task(_run_graph)

    return TriggerResponse(
        run_id=run_id,
        status="accepted",
        message="Graph execution started in background. Use GET /status/{run_id} to poll.",
    )
