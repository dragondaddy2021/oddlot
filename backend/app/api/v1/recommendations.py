from fastapi import APIRouter, HTTPException, Request

from app.core.limiter import LIMIT_GENERAL, limiter
from app.services.stock_service import get_today_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/today")
@limiter.limit(LIMIT_GENERAL)
async def today_recommendations(request: Request) -> dict:
    """Return today's AI stock picks from cache/DB.

    Returns 404 if no recommendations have been generated yet today.
    AI generation is triggered only by the internal cron endpoint.
    """
    result = get_today_recommendations()
    if result is None:
        raise HTTPException(status_code=404, detail="今日選股尚未產生")
    return result
