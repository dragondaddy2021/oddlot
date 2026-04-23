"""Daily AI stock selection script — runs as a GitHub Actions job.

Stages:
  1. Fetch candidate stocks from TWSE BWIBBU_d
  2. Fetch past-3y dividend events from TWSE TWT49U，過濾「每年至少配息一次」，
     並用 STOCK_DAY 計算平均填息天數 / 填息率
  3. Call Claude Haiku to pick 10 recommendations
  4. Upsert result to Supabase ai_recommendations table (service_role_key)

Required environment variables:
  ANTHROPIC_API_KEY
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""
import json
import os
import re
import sys
import time
from datetime import date, timedelta, timezone, datetime

import anthropic
import httpx
from supabase import create_client

# ── Constants ──────────────────────────────────────────────────────────────────
TWSE_BWIBBU    = "https://www.twse.com.tw/exchangeReport/BWIBBU_d"
TWSE_T49U      = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
TWSE_STOCK_DAY = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"

AI_MODEL = "claude-haiku-4-5-20251001"
MAX_CANDIDATES = 50
PRICE_MIN = 10.0
PRICE_MAX = 500.0

DIVIDEND_YEARS   = 3      # 檢視過去 N 個完整日曆年
FILL_MAX_MONTHS  = 3      # 除權息後最多往後看 N 個月找填息日
TWSE_DELAY       = 0.7    # TWSE 兩次呼叫之間的延遲（秒），避免被擋
TWSE_TIMEOUT     = 25

COL_SYMBOL = 0
COL_NAME   = 1
COL_PRICE  = 2
COL_YIELD  = 3
COL_PE     = 5

# TWT49U 欄位：[資料日期, 股票代號, 股票名稱, 除權息前收盤價, 除權息參考價, ...]
T49_COL_DATE     = 0
T49_COL_SYMBOL   = 1
T49_COL_BASELINE = 3

# STOCK_DAY 欄位：[日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, ...]
SD_COL_DATE  = 0
SD_COL_CLOSE = 6

SYSTEM_PROMPT = (
    "你是台股零股投資分析助理。以下資料僅供參考，不構成投資建議，"
    "投資人須自行評估風險。請從候選清單中選出最適合零股長期投資的 10 檔，"
    "考量因素：殖利率穩定性、本益比合理性、產業分散度、股價親民度、"
    "填息速度與填息率（avg_fill_days 越小越佳、fill_rate 越高代表填息機率越高）。"
    "注意：fill_samples 偏低（< 2）時該指標參考性降低，勿過度依賴。"
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_float(val: object) -> float | None:
    if val in ("-", "", None):
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _minguo_to_date(s: str) -> date | None:
    """Parse TWSE 民國 date like '114年01月02日' or '114/01/02'."""
    if not s:
        return None
    m = re.match(r"\s*(\d{2,3})[年/](\d{1,2})[月/](\d{1,2})日?\s*$", str(s))
    if not m:
        return None
    try:
        y = int(m.group(1)) + 1911
        return date(y, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    return m.group(1).strip() if m else text


# ── Stage 1: TWSE BWIBBU_d ─────────────────────────────────────────────────────

def fetch_candidates() -> list[dict]:
    """Return all valid BWIBBU_d candidates sorted by yield (no top slicing)."""
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
    print(f"[TWSE] {len(rows)} rows → {len(candidates)} candidates after basic filter")
    return candidates


# ── Stage 2: TWT49U + STOCK_DAY → dividend filter & fill-days stats ───────────

def _fetch_dividend_events(client: httpx.Client, years: int) -> dict[str, list[dict]]:
    """Fetch ex-dividend events for past `years` calendar years via TWT49U.

    Returns {symbol: [{ex_date, baseline, year}, ...]}.
    """
    today = date.today()
    target_years = list(range(today.year - years, today.year))
    events: dict[str, list[dict]] = {}

    for y in target_years:
        start = f"{y}0101"
        end   = f"{y}1231"
        try:
            resp = client.get(
                TWSE_T49U,
                params={"startDate": start, "endDate": end, "response": "json"},
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            print(f"[TWT49U] year {y} failed: {exc}", file=sys.stderr)
            time.sleep(TWSE_DELAY)
            continue

        if body.get("stat") != "OK":
            print(f"[TWT49U] year {y} stat={body.get('stat')}", file=sys.stderr)
            time.sleep(TWSE_DELAY)
            continue

        rows = body.get("data", [])
        count = 0
        for row in rows:
            symbol = str(row[T49_COL_SYMBOL]).strip()
            # 僅收四碼一般股（排除 ETF / 權證 / 債券）
            if not (symbol.isdigit() and len(symbol) == 4 and not symbol.startswith("0")):
                continue
            ex_date  = _minguo_to_date(row[T49_COL_DATE])
            baseline = _parse_float(row[T49_COL_BASELINE])
            if ex_date is None or baseline is None or baseline <= 0:
                continue
            events.setdefault(symbol, []).append({
                "ex_date": ex_date,
                "baseline": baseline,
                "year": ex_date.year,
            })
            count += 1
        print(f"[TWT49U] year {y}: {count} events over {len({e['year']: 1 for e in sum(events.values(), [])})} tracked years")
        time.sleep(TWSE_DELAY)

    return events


def _fetch_stock_month(
    client: httpx.Client,
    symbol: str,
    yyyymm: str,
    cache: dict,
) -> list[tuple[date, float]]:
    """Fetch one month of STOCK_DAY close prices. Cached by (symbol, yyyymm)."""
    key = (symbol, yyyymm)
    if key in cache:
        return cache[key]

    result: list[tuple[date, float]] = []
    try:
        resp = client.get(
            TWSE_STOCK_DAY,
            params={"response": "json", "date": f"{yyyymm}01", "stockNo": symbol},
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:
        print(f"[STOCK_DAY] {symbol} {yyyymm} failed: {exc}", file=sys.stderr)
        cache[key] = result
        time.sleep(TWSE_DELAY)
        return result

    time.sleep(TWSE_DELAY)

    if body.get("stat") != "OK":
        cache[key] = result
        return result

    for row in body.get("data", []):
        d     = _minguo_to_date(row[SD_COL_DATE])
        close = _parse_float(row[SD_COL_CLOSE])
        if d is not None and close is not None:
            result.append((d, close))

    cache[key] = result
    return result


def _compute_fill_days(
    client: httpx.Client,
    symbol: str,
    event: dict,
    cache: dict,
) -> int | None:
    """Return days until close ≥ baseline after ex-date, or None if unfilled
    within FILL_MAX_MONTHS."""
    ex_date  = event["ex_date"]
    baseline = event["baseline"]
    cursor   = date(ex_date.year, ex_date.month, 1)

    for _ in range(FILL_MAX_MONTHS):
        yyyymm = f"{cursor.year}{cursor.month:02d}"
        daily  = _fetch_stock_month(client, symbol, yyyymm, cache)
        for d, close in daily:
            if d <= ex_date:
                continue
            if close >= baseline:
                return (d - ex_date).days
        # advance one month
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)

    return None


def enrich_with_dividend_stats(raw: list[dict]) -> list[dict]:
    """Filter candidates by 近 N 年每年至少配息一次 and compute fill-days stats.

    Adds fields: avg_fill_days, fill_rate, fill_samples.
    Slices to MAX_CANDIDATES (by yield) before running the expensive STOCK_DAY
    lookups.
    """
    current_year = date.today().year
    target_years = set(range(current_year - DIVIDEND_YEARS, current_year))

    with httpx.Client(timeout=TWSE_TIMEOUT) as client:
        print(f"[Dividend] fetching TWT49U for years {sorted(target_years)}...")
        events_map = _fetch_dividend_events(client, DIVIDEND_YEARS)
        print(f"[Dividend] {len(events_map)} stocks have ex-dividend records in that window")

        # Filter: 每個目標年度都至少有 1 次除息
        eligible = []
        for c in raw:
            events = events_map.get(c["symbol"], [])
            years_seen = {e["year"] for e in events}
            if target_years.issubset(years_seen):
                eligible.append(c)
        print(f"[Dividend] {len(eligible)}/{len(raw)} candidates satisfy 'annual dividend × {DIVIDEND_YEARS}y'")

        # Slice to top MAX_CANDIDATES by yield before expensive fill-days lookup
        top = eligible[:MAX_CANDIDATES]
        print(f"[Dividend] computing fill-days for top {len(top)}...")

        cache: dict = {}
        for idx, c in enumerate(top, 1):
            events = [e for e in events_map.get(c["symbol"], []) if e["year"] in target_years]
            fill_list: list[int] = []
            for ev in events:
                days = _compute_fill_days(client, c["symbol"], ev, cache)
                if days is not None:
                    fill_list.append(days)

            total = len(events)
            c["avg_fill_days"] = round(sum(fill_list) / len(fill_list), 1) if fill_list else None
            c["fill_rate"]     = round(len(fill_list) / total, 2) if total else 0.0
            c["fill_samples"]  = len(fill_list)
            if idx % 10 == 0:
                print(f"[Dividend] progress {idx}/{len(top)}")

    return top


# ── Stage 3: Claude Haiku ──────────────────────────────────────────────────────

def call_claude(candidates: list[dict]) -> list[dict]:
    user_msg = (
        "候選股票清單（含過去 3 年填息資料）：\n"
        + json.dumps(candidates, ensure_ascii=False, indent=2)
        + "\n\n"
        "請回傳純 JSON（不含 markdown code block），格式如下：\n"
        '{"picks": [{"symbol": "2330", "name": "台積電", "reason": "50字以內繁中推薦理由",'
        ' "yield_rate": 2.5, "pe_ratio": 18.2, "price": 850.0,'
        ' "avg_fill_days": 30.5, "fill_rate": 1.0, "fill_samples": 3}]}'
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


# ── Stage 4: Supabase upsert ───────────────────────────────────────────────────

def already_exists(today: date) -> bool:
    """Return True if today's recommendations are already in Supabase."""
    url   = os.environ["SUPABASE_URL"]
    key   = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb    = create_client(url, key)

    result = (
        sb.table("ai_recommendations")
        .select("date")
        .eq("date", today.isoformat())
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


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

    # Skip if today's data already exists (backup cron guard)
    try:
        if already_exists(today):
            print(f"[SKIP] Data for {today} already exists, nothing to do.")
            sys.exit(0)
    except Exception as exc:
        print(f"[WARN] Could not check existing data: {exc}", file=sys.stderr)
        # Proceed anyway — upsert will handle duplicates safely

    try:
        raw = fetch_candidates()
    except Exception as exc:
        print(f"[ERROR] TWSE fetch failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if not raw:
        print("[ERROR] No candidates after BWIBBU filtering", file=sys.stderr)
        sys.exit(1)

    try:
        candidates = enrich_with_dividend_stats(raw)
    except Exception as exc:
        print(f"[ERROR] Dividend enrichment failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if not candidates:
        print("[ERROR] No candidates survived dividend filter", file=sys.stderr)
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
        fill_info = (
            f"fill={p.get('avg_fill_days')}d/{int((p.get('fill_rate') or 0) * 100)}%"
            if p.get("fill_samples")
            else "fill=N/A"
        )
        print(
            f"  {p['symbol']} {p['name']}  yield={p['yield_rate']}%  "
            f"PE={p['pe_ratio']}  ${p['price']}  {fill_info}"
        )


if __name__ == "__main__":
    main()
