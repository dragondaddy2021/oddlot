"""Read-side service for stock data.

Functions here never call FinMind or AI — they only read from
Upstash Redis and Supabase (via service_role client).
"""
import json
import logging
from datetime import date

from app.db.redis import get_redis
from app.db.supabase import get_supabase

logger = logging.getLogger(__name__)


def _redis_key(d: date) -> str:
    return f"recommendations:{d.isoformat()}"


def get_today_recommendations() -> dict | None:
    """Return today's AI recommendations.

    Lookup order:
      1. Upstash Redis  (fast, TTL-based cache)
      2. Supabase       (persistent store)
      3. None           (not yet generated for today)
    """
    today = date.today()

    # ── 1. Redis ───────────────────────────────────────────────────────────────
    try:
        raw = get_redis().get(_redis_key(today))
        if raw:
            logger.debug("Recommendations cache hit for %s", today)
            return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis read failed, falling back to Supabase: %s", exc)

    # ── 2. Supabase ────────────────────────────────────────────────────────────
    try:
        resp = (
            get_supabase()
            .table("ai_recommendations")
            .select("*")
            .eq("date", today.isoformat())
            .limit(1)
            .execute()
        )
        if resp.data:
            logger.debug("Recommendations loaded from Supabase for %s", today)
            return resp.data[0]
    except Exception as exc:  # noqa: BLE001
        logger.error("Supabase read failed: %s", exc, exc_info=True)

    return None


def get_stock_info(symbol: str) -> dict | None:
    """Return cached stock data for *symbol* from stock_cache table.

    Returns None if the symbol is not in the cache.
    """
    if not symbol:
        return None
    try:
        resp = (
            get_supabase()
            .table("stock_cache")
            .select("*")
            .eq("symbol", symbol.upper())
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:  # noqa: BLE001
        logger.error("stock_cache query failed for %s: %s", symbol, exc, exc_info=True)
        return None
