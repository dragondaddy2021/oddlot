"""Daily AI stock selection script — runs as a GitHub Actions job.

Stages:
  1. Fetch candidate stocks from TWSE BWIBBU_d
  2. Call Claude Haiku to pick 10 recommendations
  3. Upsert result to Supabase ai_recommendations table (service_role_key)

Required environment variables:
  ANTHROPIC_API_KEY
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""
import json
import os
import sys
from datetime import date, timedelta, timezone, datetime

import anthropic
import httpx
from supabase import create_client

# ── Constants ──────────────────────────────────────────────────────────────────
TWSE_BWIBBU = "https://www.twse.com.tw/exchangeReport/BWIBBU_d"
AI_MODEL = "claude-haiku-4-5-20251001"
MAX_CANDIDATES = 50
PRICE_MIN = 10.0
PRICE_MAX = 500.0

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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_float(val: object) -> float | None:
    if val in ("-", "", None):
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _strip_code_fence(text: str) -> str:
    import re
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    return m.group(1).strip() if m else text


# ── Stage 1: TWSE ─────────────────────────────────────────────────────────────

def fetch_candidates() -> list[dict]:
    with httpx.Client(timeout=20) as client:
        for days_back in range(7):
            d = (date.today() - timedelta(days=days_back)).strftime("%Y%m%d")
            try:
                resp = client.get(
                    TWSE_BWIBBU,
                    params={"response": "json", "date": d, "selectType": "ALL"},
                )
                resp.raise_for_status()
                body = resp.json()
            except Exception as exc:
                print(f"[TWSE] attempt {d} failed: {exc}", file=sys.stderr)
                continue

            if body.get("stat") == "OK" and body.get("data"):
                rows = body["data"]
                print(f"[TWSE] loaded {len(rows)} rows for {d}")
                break
        else:
            raise RuntimeError("TWSE returned no data for the last 7 days")

    candidates = []
    for row in rows:
        symbol = str(row[COL_SYMBOL]).strip()
        name   = str(row[COL_NAME]).strip()

        if not (symbol.isdigit() and len(symbol) == 4 and not symbol.startswith("0")):
            continue

        price      = _parse_float(row[COL_PRICE])
        yield_rate = _parse_float(row[COL_YIELD])
        pe         = _parse_float(row[COL_PE])

        if price is None or yield_rate is None or pe is None:
            continue
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        if pe <= 0 or yield_rate <= 0:
            continue

        candidates.append({
            "symbol":     symbol,
            "name":       name,
            "price":      round(price, 2),
            "yield_rate": round(yield_rate, 2),
            "pe_ratio":   round(pe, 2),
        })

    candidates.sort(key=lambda x: x["yield_rate"], reverse=True)
    print(f"[TWSE] {len(rows)} rows → {len(candidates)} candidates → top {MAX_CANDIDATES}")
    return candidates[:MAX_CANDIDATES]


# ── Stage 2: Claude Haiku ──────────────────────────────────────────────────────

def call_claude(candidates: list[dict]) -> list[dict]:
    user_msg = (
        "候選股票清單：\n"
        + json.dumps(candidates, ensure_ascii=False, indent=2)
        + "\n\n"
        "請回傳純 JSON（不含 markdown code block），格式如下：\n"
        '{"picks": [{"symbol": "2330", "name": "台積電", "reason": "50字以內繁中推薦理由",'
        ' "yield_rate": 2.5, "pe_ratio": 18.2, "price": 850.0}]}'
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    for attempt in range(2):
        msg = client.messages.create(
            model=AI_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = _strip_code_fence(msg.content[0].text)
        try:
            result = json.loads(raw)
            picks = result.get("picks", [])
            print(f"[Claude] {len(picks)} picks returned")
            return picks
        except json.JSONDecodeError as exc:
            print(f"[Claude] JSON parse error (attempt {attempt+1}/2): {exc}", file=sys.stderr)

    raise RuntimeError("Claude returned invalid JSON after 2 attempts")


# ── Stage 3: Supabase upsert ───────────────────────────────────────────────────

def save_to_supabase(today: date, picks: list[dict]) -> None:
    url   = os.environ["SUPABASE_URL"]
    key   = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb    = create_client(url, key)

    sb.table("ai_recommendations").upsert(
        {"date": today.isoformat(), "stocks": picks, "reasoning": ""},
        on_conflict="date",
    ).execute()
    print(f"[Supabase] upserted {len(picks)} picks for {today}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    # Use Taiwan time (UTC+8) to match the date queried by the frontend
    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz=tz_tw).date()
    print(f"=== Daily selection for {today} (Taiwan time) ===")

    try:
        candidates = fetch_candidates()
    except Exception as exc:
        print(f"[ERROR] TWSE fetch failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if not candidates:
        print("[ERROR] No candidates after filtering", file=sys.stderr)
        sys.exit(1)

    try:
        picks = call_claude(candidates)
    except Exception as exc:
        print(f"[ERROR] Claude failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        save_to_supabase(today, picks)
    except Exception as exc:
        print(f"[ERROR] Supabase save failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print("=== Done ===")
    for p in picks:
        print(f"  {p['symbol']} {p['name']}  yield={p['yield_rate']}%  PE={p['pe_ratio']}  ${p['price']}")


if __name__ == "__main__":
    main()
