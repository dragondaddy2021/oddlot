"""AI stock selection pipeline.

Data source: TWSE (Taiwan Stock Exchange) official public API — no auth required.

Stages:
  1. Fetch candidate stocks from TWSE BWIBBU_d (price, PE, yield in one call)
  2. Call Claude Haiku to pick 10 recommendations
  3. Persist result to Supabase + Upstash Redis (TTL 24 h)
  4. On subsequent calls today, return the cached result immediately
"""
import json
import logging
from datetime import date, timedelta

import anthropic
import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.db.redis import get_redis
from app.db.supabase import get_supabase

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
# TWSE public API — no token required
TWSE_BWIBBU = "https://www.twse.com.tw/exchangeReport/BWIBBU_d"

AI_MODEL = "claude-haiku-4-5-20251001"
REDIS_TTL = 86400       # 24 hours
MAX_CANDIDATES = 50     # max stocks passed to AI
PRICE_MIN = 10.0
PRICE_MAX = 500.0

# BWIBBU_d column indices
COL_SYMBOL = 0
COL_NAME   = 1
COL_PRICE  = 2
COL_YIELD  = 3
COL_PE     = 5

SYSTEM_PROMPT = (
    "你是台股零股投資分析助理。以下資料僅供參考，不構成投資建議，"
    "投資人須自行評估風險。請從候選清單中選出最適合零股長期投資的 10 檔，"
    "考量因素：殖利率穩定性、本益比合理性、產業分散度、股價親民度。"
)


# ── Redis key ──────────────────────────────────────────────────────────────────
def _redis_key(d: date) -> str:
    return f"recommendations:{d.isoformat()}"


# ── Stage 1: TWSE ─────────────────────────────────────────────────────────────

def _last_trading_date() -> str:
    """Return the most recent weekday as YYYYMMDD (proxy for last trading day)."""
    d = date.today()
    # Walk back until we find a weekday (Mon–Fri)
    for _ in range(7):
        if d.weekday() < 5:  # 0=Mon … 4=Fri
            return d.strftime("%Y%m%d")
        d -= timedelta(days=1)
    return date.today().strftime("%Y%m%d")


async def _fetch_bwibbu(client: httpx.AsyncClient) -> list[dict]:
    """
    Fetch PE ratio, dividend yield, and close price for all TWSE-listed stocks.

    TWSE BWIBBU_d column layout (index → meaning):
      0  證券代號   stock symbol
      1  證券名稱   stock name
      2  收盤價     close price
      3  殖利率(%) dividend yield (%)
      4  股利年度   dividend fiscal year
      5  本益比     PE ratio  ('-' when N/A)
      6  股價淨值比 PBR
      7  財報年/季  fiscal report year/quarter

    Tries up to 7 calendar days back to find a trading day with data.
    """
    for days_back in range(7):
        d = (date.today() - timedelta(days=days_back)).strftime("%Y%m%d")
        try:
            resp = await client.get(
                TWSE_BWIBBU,
                params={"response": "json", "date": d, "selectType": "ALL"},
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            logger.debug("BWIBBU_d attempt %s failed: %s", d, exc)
            continue

        if body.get("stat") == "OK" and body.get("data"):
            logger.info("BWIBBU_d: loaded %d rows for date %s", len(body["data"]), d)
            return body["data"]

    raise RuntimeError("TWSE BWIBBU_d returned no data for the last 7 days")


def _parse_float(val: object) -> float | None:
    """Convert a TWSE value to float; return None on '-' or invalid."""
    if val in ("-", "", None):
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None


async def _build_candidates() -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        rows = await _fetch_bwibbu(client)

    candidates: list[dict] = []
    for row in rows:
        symbol = str(row[COL_SYMBOL]).strip()
        name   = str(row[COL_NAME]).strip()

        # Keep only regular listed stocks: 4-digit numeric, not starting with "0"
        # ETFs (0050, 00878…) and warrants are excluded this way.
        if not (symbol.isdigit() and len(symbol) == 4 and not symbol.startswith("0")):
            continue

        price = _parse_float(row[COL_PRICE])
        yield_rate = _parse_float(row[COL_YIELD])
        pe = _parse_float(row[COL_PE])

        if price is None or yield_rate is None or pe is None:
            continue
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        if pe <= 0 or yield_rate <= 0:
            continue

        candidates.append({
            "symbol": symbol,
            "name": name,
            "price": round(price, 2),
            "yield_rate": round(yield_rate, 2),
            "pe_ratio": round(pe, 2),
        })

    # Sort by yield_rate descending, take top MAX_CANDIDATES
    candidates.sort(key=lambda x: x["yield_rate"], reverse=True)
    logger.info(
        "TWSE filter: %d total rows → %d candidates (price %.0f–%.0f, PE>0, yield>0)",
        len(rows), len(candidates), PRICE_MIN, PRICE_MAX,
    )
    return candidates[:MAX_CANDIDATES]


# ── Stage 2: Claude Haiku ──────────────────────────────────────────────────────

def _build_user_message(candidates: list[dict]) -> str:
    return (
        "候選股票清單：\n"
        + json.dumps(candidates, ensure_ascii=False, indent=2)
        + "\n\n"
        "請回傳純 JSON（不含 markdown code block），格式如下：\n"
        '{"picks": [{"symbol": "2330", "name": "台積電", "reason": "50字以內繁中推薦理由",'
        ' "yield_rate": 2.5, "pe_ratio": 18.2, "price": 850.0}]}'
    )


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers that models sometimes add."""
    import re
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    return m.group(1).strip() if m else text


def _call_claude(candidates: list[dict]) -> dict:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=AI_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(candidates)}],
    )
    raw: str = _strip_code_fence(msg.content[0].text)
    return json.loads(raw)


# ── Stage 3: Persist ───────────────────────────────────────────────────────────

def _save_to_supabase(today: date, picks: list[dict]) -> None:
    sb = get_supabase()
    sb.table("ai_recommendations").upsert(
        {"date": today.isoformat(), "stocks": picks, "reasoning": ""},
        on_conflict="date",
    ).execute()


def _save_to_redis(today: date, result: dict) -> None:
    get_redis().set(
        _redis_key(today),
        json.dumps(result, ensure_ascii=False),
        ex=REDIS_TTL,
    )


def _get_from_redis(today: date) -> dict | None:
    raw = get_redis().get(_redis_key(today))
    if raw:
        return json.loads(raw)
    return None


# ── Public entry point ─────────────────────────────────────────────────────────

async def run_ai_selection() -> dict:
    """Run the full AI selection pipeline and return today's recommendations.

    Returns cached result immediately if Redis already has today's data.
    Raises HTTPException (503/500) on unrecoverable failures.
    """
    today = date.today()

    # Fast path: Redis cache hit
    cached = _get_from_redis(today)
    if cached:
        logger.info("Cache hit — returning stored recommendations for %s", today)
        return cached

    # ── Stage 1: TWSE ──────────────────────────────────────────────────────────
    try:
        candidates = await _build_candidates()
    except Exception as exc:
        logger.error("TWSE pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="股票資料取得失敗，請稍後再試") from exc

    if not candidates:
        raise HTTPException(status_code=503, detail="無符合條件的候選股票")

    # ── Stage 2: Claude (one retry on JSON parse failure) ─────────────────────
    result: dict | None = None
    last_json_exc: Exception | None = None

    for attempt in range(2):
        try:
            result = _call_claude(candidates)
            break
        except json.JSONDecodeError as exc:
            last_json_exc = exc
            logger.warning("Claude JSON parse error (attempt %d/2): %s", attempt + 1, exc)
        except (anthropic.APIError, anthropic.APIStatusError) as exc:
            logger.error("Anthropic API error: %s", exc, exc_info=True)
            raise HTTPException(status_code=503, detail="AI 服務暫時不可用，請稍後再試") from exc

    if result is None:
        logger.error("Claude returned invalid JSON after 2 attempts: %s", last_json_exc)
        raise HTTPException(status_code=500, detail="AI 回傳格式錯誤") from last_json_exc

    # ── Stage 3: Persist ───────────────────────────────────────────────────────
    picks: list[dict] = result.get("picks", [])
    try:
        _save_to_supabase(today, picks)
    except Exception as exc:  # noqa: BLE001
        logger.error("Supabase save failed (non-fatal): %s", exc, exc_info=True)

    try:
        _save_to_redis(today, result)
    except Exception as exc:  # noqa: BLE001
        logger.error("Redis save failed (non-fatal): %s", exc, exc_info=True)

    logger.info("AI selection complete: %d picks for %s", len(picks), today)
    return result
