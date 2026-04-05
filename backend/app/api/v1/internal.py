import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.core.config import settings
from app.core.limiter import LIMIT_AI, limiter
from app.services.ai_selector import run_ai_selection

logger = logging.getLogger(__name__)

# Note: prefix is /internal, NOT /api/v1 — mounted directly on app in main.py
router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/run-daily-recommendation", status_code=202)
@limiter.limit(LIMIT_AI)
async def run_daily_recommendation(
    request: Request,
    background_tasks: BackgroundTasks,
    x_cron_secret: str | None = Header(default=None),
) -> dict:
    """Trigger the daily AI stock-selection pipeline.

    Protected by X-Cron-Secret header — only the scheduler should call this.
    Returns 202 immediately; the AI pipeline runs in the background.
    """
    if not x_cron_secret or x_cron_secret != settings.internal_cron_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    background_tasks.add_task(_run_selection_task)
    return {"status": "accepted", "message": "Daily recommendation job queued"}


async def _run_selection_task() -> None:
    """Background wrapper — logs errors so they don't silently disappear."""
    try:
        result = await run_ai_selection()
        picks = result.get("picks", [])
        logger.info("Daily recommendation job complete: %d picks", len(picks))
    except Exception as exc:  # noqa: BLE001
        logger.error("Daily recommendation job failed: %s", exc, exc_info=True)
