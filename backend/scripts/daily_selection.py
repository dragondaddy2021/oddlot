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
import random
import re
import sys
import time
from datetime import date, timedelta, timezone, datetime
from pathlib import Path

import anthropic
import httpx
from supabase import create_client

# ── Constants ──────────────────────────────────────────────────────────────────
TWSE_BWIBBU    = "https://www.twse.com.tw/exchangeReport/BWIBBU_d"
TWSE_T49U      = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
TWSE_STOCK_DAY = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"  # exchangeReport 路徑不擋雲端 IP（同 BWIBBU_d）

# TWSE 部分端點（STOCK_DAY）會擋無 UA 或 python-httpx 的請求，改用瀏覽器 UA 繞過
TWSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.twse.com.tw/",
}

AI_MODEL = "claude-haiku-4-5-20251001"
MAX_CANDIDATES = 50
FILL_CHECK_POOL = 80   # 計算填息前先取的候選數（預留過濾 0 填息股的 buffer）
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

# Sanity bound: 台股殖利率 > 30% 幾乎必為解析錯誤（欄位錯位 / 股利年度被讀成殖利率）
YIELD_SANITY_MAX = 30.0

# 用 BWIBBU_d 回傳的 fields 標籤動態定位欄位，避免 schema 變動時靜默對錯欄
BWIBBU_FIELD_KEYS = {
    "price": "收盤價",
    "yield": "殖利率",
    "pe":    "本益比",
}


def _resolve_bwibbu_columns(fields: list[str]) -> dict[str, int]:
    """Map logical name → column index by substring-matching the field label.

    Falls back to the legacy COL_* constants if a label can't be located, so
    cached/older response shapes still work.
    """
    fallback = {"price": COL_PRICE, "yield": COL_YIELD, "pe": COL_PE}
    resolved: dict[str, int] = {}
    for key, label in BWIBBU_FIELD_KEYS.items():
        idx = next((i for i, f in enumerate(fields) if label in str(f)), None)
        if idx is None:
            print(f"[TWSE] field '{label}' missing in response — falling back to index {fallback[key]}", file=sys.stderr)
            idx = fallback[key]
        resolved[key] = idx
    return resolved

# TWT49U 欄位：[資料日期, 股票代號, 股票名稱, 除權息前收盤價, 除權息參考價, 權值+息值, ...]
T49_COL_DATE      = 0
T49_COL_SYMBOL    = 1
T49_COL_BASELINE  = 3   # 除權息前收盤價（填息基準價）
T49_COL_DIV_VALUE = 5   # 權值+息值（每股配發價值）

# STOCK_DAY 欄位：[日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, ...]
SD_COL_DATE  = 0
SD_COL_CLOSE = 6

# ── 產業分類（TWSE OpenAPI t187ap03_L 回傳的「產業別」是代碼，需自行對照） ──
TWSE_OPENAPI_BASIC = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

SECTOR_CODE_MAP = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙工業",
    "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業", "14": "建材營造",
    "15": "航運業",   "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨",
    "20": "其他",     "21": "化學工業", "22": "生技醫療", "23": "油電燃氣",
    "24": "半導體",   "25": "電腦及週邊設備", "26": "光電",
    "27": "通信網路", "28": "電子零組件", "29": "電子通路",
    "30": "資訊服務", "31": "其他電子", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活", "91": "存託憑證",
}

CACHE_DIR         = Path(__file__).parent / "cache"
SECTOR_CACHE      = CACHE_DIR / "sectors.json"
SECTOR_CACHE_DAYS = 7

# ── 自組 ETF 篩選參數 ──
DIVIDEND_CV_MAX     = 0.4    # 近 N 年配息金額變異係數上限（剔除一次性高配發 / 景氣循環）
SECTOR_CAP          = 3      # 每個產業最多送進 AI 的檔數
PRICE_CAGR_MIN      = -0.05  # 近 N 年股價 CAGR 下限（擋價值陷阱：年年配息但股價長期下跌）
CAGR_LOOKBACK_YEARS = 3

# Momentum factor：CV filter 後、sector cap 前用「近 3 個月漲跌幅」boost 排序
# 動機：3 年回測顯示原版（純殖利率排序）系統性錯過 AI/半導體強勢股 → 19% 勝率
# Momentum 是金融文獻最確認有效的單一 factor
MOMENTUM_LOOKBACK_MONTHS = 3
MOMENTUM_POOL_SIZE       = 200  # 對 yield 前 N 名計算 momentum（控制 API 成本）

SYSTEM_PROMPT = (
    "你是台股零股投資分析助理，協助小資族挑選適合長期持有、自組 ETF 的個股。"
    "以下資料僅供參考，不構成投資建議，投資人須自行評估風險。"
    "請從候選清單中選出 10 檔組成一個產業分散、配息穩定、長期向上的投資組合。"
    "考量因素（按重要性排序）："
    "(1) 配息穩定度 dividend_cv（越低越好，<0.2 為非常穩定）；"
    "(2) 產業分散度 industry（避免同產業集中，盡量涵蓋 6 個以上不同產業）；"
    "(3) 股價長期趨勢 price_cagr_3y（>0 為佳；負值代表填息也賠錢的價值陷阱風險）；"
    "(4) 近期動能 momentum_3m（近 3 個月漲跌幅；>0.05 表示強勢，<-0.10 應警惕）；"
    "(5) 填息速度與填息率（avg_fill_days 越小、fill_rate 越高越佳）；"
    "(6) 殖利率與本益比合理性（高殖利率不是首要目標，>8% 通常隱含風險）；"
    "(7) 股價親民度。"
    "注意：fill_samples < 2 時該指標參考性降低；price_cagr_3y / momentum_3m 為 null "
    "代表資料缺漏，不影響評分但應於理由中註明。"
    "\n\n"
    "推薦理由 `reason` 必須是 4 段結構，段落間用空行（\\n\\n）分隔，每段以「【標籤】」開頭："
    "\n"
    "【持有邏輯】30-60 字 — 為什麼這檔適合 5 年以上長期持有，要連結到公司商業模式或現金流特性，"
    "不要只重複數字。例：「電信龍頭，現金流穩定、寡占性高，景氣循環影響小」。"
    "\n\n"
    "【組合角色】20-40 字 — 在 10 檔組合裡扮演什麼角色。"
    "常見角色：高股息穩定軸 / 防禦型現金流 / 成長補位 / 景氣循環平衡 / 產業分散覆蓋。"
    "\n\n"
    "【風險】30-50 字 — 一個具體風險（不要泛談「市場波動」）。"
    "例：「景氣循環股，營收與全球半導體景氣高度連動」「PE 偏高，建議分批進場」。"
    "\n\n"
    "【近況脈絡】30-60 字 — 用你的訓練知識說明公司或產業近期狀況。"
    "**避免捏造具體數字**（如 Q1 EPS、接單量等你不確定的數值），不確定時用「市場一般認為」"
    "「過去幾年趨勢顯示」等語氣帶過。若資訊不足可說「公司基本面穩定但缺乏近期催化劑」。"
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


def _extract_json(text: str) -> str:
    """Extract JSON object from Claude response. Handles:
    - bare JSON: `{...}`
    - fenced JSON: ```json\n{...}\n```
    - prose preamble: `好的，以下是結果：\n{...}`
    - prose trailing: `{...}\n以上為...`
    """
    text = text.strip()

    # Try fenced first (anywhere in response, not just whole-message)
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        return m.group(1).strip()

    # Find first '{', then walk to its matching close brace
    start = text.find("{")
    if start == -1:
        return text  # let json.loads raise

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return text[start:]  # unbalanced — let json.loads raise


def _escape_unescaped_lf(raw: str) -> str:
    """Escape raw LF/CR inside JSON string literals to \\n / \\r.

    Claude 偶爾在 string value 內塞真實換行字元（特別是被要求輸出多段文字時），
    違反 JSON spec 導致 json.loads 抛 'Unterminated string'。這個函式用狀態機
    走過 raw text，只在 string literal 內把 LF/CR 替成 escape 序列，不影響其他
    結構字元。
    """
    out: list[str] = []
    in_string = False
    escape = False
    for ch in raw:
        if escape:
            escape = False
            out.append(ch)
            continue
        if ch == "\\":
            escape = True
            out.append(ch)
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch == "\n":
            out.append("\\n")
            continue
        if in_string and ch == "\r":
            out.append("\\r")
            continue
        out.append(ch)
    return "".join(out)


# ── Stage 1: TWSE BWIBBU_d ─────────────────────────────────────────────────────

def fetch_candidates(as_of_date: date | None = None) -> list[dict]:
    """Return all valid BWIBBU_d candidates sorted by yield (no top slicing).

    `as_of_date` lets backtest replay the algorithm at past dates; defaults to today.
    """
    base = as_of_date or date.today()
    with httpx.Client(timeout=20, follow_redirects=True, headers=TWSE_HEADERS) as client:
        for days_back in range(7):
            d = (base - timedelta(days=days_back)).strftime("%Y%m%d")
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
                fields = body.get("fields", [])
                print(f"[TWSE] loaded {len(rows)} rows for {d}")
                break
        else:
            raise RuntimeError("TWSE returned no data for the last 7 days")

    cols = _resolve_bwibbu_columns(fields)
    print(f"[TWSE] resolved columns: {cols} from fields {fields}")
    px_i, yd_i, pe_i = cols["price"], cols["yield"], cols["pe"]
    expected_len = max(COL_SYMBOL, COL_NAME, px_i, yd_i, pe_i) + 1

    candidates = []
    bad_shape = bad_yield = 0
    for row in rows:
        if len(row) < expected_len:
            bad_shape += 1
            continue

        symbol = str(row[COL_SYMBOL]).strip()
        name   = str(row[COL_NAME]).strip()

        if not (symbol.isdigit() and len(symbol) == 4 and not symbol.startswith("0")):
            continue

        price      = _parse_float(row[px_i])
        yield_rate = _parse_float(row[yd_i])
        pe         = _parse_float(row[pe_i])

        if price is None or yield_rate is None or pe is None:
            continue
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        if pe <= 0 or yield_rate <= 0:
            continue
        if yield_rate > YIELD_SANITY_MAX:
            bad_yield += 1
            continue

        candidates.append({
            "symbol":     symbol,
            "name":       name,
            "price":      round(price, 2),
            "yield_rate": round(yield_rate, 2),
            "pe_ratio":   round(pe, 2),
        })

    candidates.sort(key=lambda x: x["yield_rate"], reverse=True)
    print(
        f"[TWSE] {len(rows)} rows → {len(candidates)} candidates after basic filter "
        f"(dropped: bad_shape={bad_shape}, yield>{YIELD_SANITY_MAX:g}%={bad_yield})"
    )
    return candidates


# ── Stage 2: TWT49U + STOCK_DAY → dividend filter & fill-days stats ───────────

def _fetch_dividend_events(
    client: httpx.Client,
    years: int,
    as_of_date: date | None = None,
) -> dict[str, list[dict]]:
    """Fetch ex-dividend events for past `years` calendar years via TWT49U.

    Returns {symbol: [{ex_date, baseline, year}, ...]}.
    `as_of_date` defaults to today; backtest passes a past date to replay history.
    """
    base = as_of_date or date.today()
    target_years = list(range(base.year - years, base.year))
    events: dict[str, list[dict]] = {}

    for y in target_years:
        start = f"{y}0101"
        end   = f"{y}1231"
        body = None
        for attempt in range(3):
            try:
                resp = client.get(
                    TWSE_T49U,
                    params={"startDate": start, "endDate": end, "response": "json"},
                )
                resp.raise_for_status()
                body = resp.json()
                break
            except Exception as exc:
                wait = TWSE_DELAY * (attempt + 2)
                print(
                    f"[TWT49U] year {y} attempt {attempt+1}/3 failed: {exc}; retry in {wait:.1f}s",
                    file=sys.stderr,
                )
                time.sleep(wait)
                body = None

        if not body or body.get("stat") != "OK":
            raise RuntimeError(
                f"TWT49U year {y} unavailable after retries "
                f"(stat={body.get('stat') if body else 'no-response'})"
            )

        rows = body.get("data", [])
        count = 0
        for row in rows:
            symbol = str(row[T49_COL_SYMBOL]).strip()
            # 僅收四碼一般股（排除 ETF / 權證 / 債券）
            if not (symbol.isdigit() and len(symbol) == 4 and not symbol.startswith("0")):
                continue
            ex_date   = _minguo_to_date(row[T49_COL_DATE])
            baseline  = _parse_float(row[T49_COL_BASELINE])
            div_value = _parse_float(row[T49_COL_DIV_VALUE]) if len(row) > T49_COL_DIV_VALUE else None
            if ex_date is None or baseline is None or baseline <= 0:
                continue
            events.setdefault(symbol, []).append({
                "ex_date": ex_date,
                "baseline": baseline,
                "dividend_value": div_value or 0.0,
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


def _load_sectors() -> dict[str, str]:
    """Return {symbol: industry_name}. Cached on disk for SECTOR_CACHE_DAYS days."""
    if SECTOR_CACHE.exists():
        age_sec = time.time() - SECTOR_CACHE.stat().st_mtime
        if age_sec < SECTOR_CACHE_DAYS * 86400:
            try:
                cached = json.loads(SECTOR_CACHE.read_text(encoding="utf-8"))
                print(f"[Sector] cache hit ({len(cached)} symbols, age {age_sec/3600:.1f}h)")
                return cached
            except Exception as exc:
                print(f"[Sector] cache load failed: {exc}; refetching", file=sys.stderr)

    print("[Sector] fetching TWSE OpenAPI t187ap03_L...")
    resp = httpx.get(TWSE_OPENAPI_BASIC, timeout=30, headers=TWSE_HEADERS)
    resp.raise_for_status()
    rows = resp.json()
    sectors: dict[str, str] = {}
    for row in rows:
        sym  = str(row.get("公司代號", "")).strip()
        code = str(row.get("產業別", "")).strip()
        if sym and code:
            sectors[sym] = SECTOR_CODE_MAP.get(code, f"其他({code})")

    CACHE_DIR.mkdir(exist_ok=True)
    SECTOR_CACHE.write_text(json.dumps(sectors, ensure_ascii=False), encoding="utf-8")
    print(f"[Sector] cached {len(sectors)} symbol→industry mappings")
    return sectors


def _annual_dividend_cv(events: list[dict], target_years: set[int]) -> float | None:
    """Sum dividend value per year, then return CV (stddev/mean) across target_years.

    Returns None when any target year has zero distributed value or annual mean ≤ 0
    (cannot judge stability — caller should treat as unstable / exclude).
    """
    by_year: dict[int, float] = {y: 0.0 for y in target_years}
    for ev in events:
        if ev["year"] in target_years:
            by_year[ev["year"]] += ev.get("dividend_value", 0.0)

    values = list(by_year.values())
    if any(v <= 0 for v in values):
        return None
    mean = sum(values) / len(values)
    if mean <= 0:
        return None
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return (var ** 0.5) / mean


def _apply_sector_cap(
    candidates: list[dict],
    sectors: dict[str, str],
    cap: int,
) -> list[dict]:
    """Keep ≤ `cap` stocks per industry, preserving input order.

    Mutates each kept candidate to include `industry`.
    """
    counts: dict[str, int] = {}
    out: list[dict] = []
    for c in candidates:
        industry = sectors.get(c["symbol"], "未分類")
        if counts.get(industry, 0) >= cap:
            continue
        c["industry"] = industry
        counts[industry] = counts.get(industry, 0) + 1
        out.append(c)
    return out


def _historical_close(
    client: httpx.Client,
    symbol: str,
    months_back: int,
    cache: dict,
    as_of_date: date | None = None,
) -> float | None:
    """Return earliest available close price from `months_back` months ago,
    or None if STOCK_DAY has no data for that month."""
    target = (as_of_date or date.today()).replace(day=1)
    for _ in range(months_back):
        target = (
            date(target.year - 1, 12, 1)
            if target.month == 1
            else date(target.year, target.month - 1, 1)
        )
    yyyymm = f"{target.year}{target.month:02d}"
    daily = _fetch_stock_month(client, symbol, yyyymm, cache)
    return daily[0][1] if daily else None


def _compute_price_cagr(
    client: httpx.Client,
    symbol: str,
    current_price: float,
    cache: dict,
    years: int,
    as_of_date: date | None = None,
) -> float | None:
    """N 年股價 CAGR = (現價 / N 年前同月收盤) ^ (1/N) - 1。

    回傳 None 代表資料缺漏（例如新上市或 TWSE 暫無回應）— 上層應保留該股，
    避免因資料異常誤殺。`as_of_date` 讓回測能用過去某天作為「現價」基準。
    """
    if current_price <= 0:
        return None
    past_close = _historical_close(client, symbol, years * 12, cache, as_of_date)
    if past_close is None or past_close <= 0:
        return None
    return (current_price / past_close) ** (1 / years) - 1


def _compute_momentum(
    client: httpx.Client,
    symbol: str,
    current_price: float,
    cache: dict,
    months: int,
    as_of_date: date | None = None,
) -> float | None:
    """近 N 個月股價漲跌幅（不年化）= 現價 / N 月前收盤 - 1。

    用於排序 boost：強勢股優先進入 sector cap。回傳 None 代表資料缺漏。
    """
    if current_price <= 0:
        return None
    past_close = _historical_close(client, symbol, months, cache, as_of_date)
    if past_close is None or past_close <= 0:
        return None
    return current_price / past_close - 1


def enrich_with_dividend_stats(
    raw: list[dict],
    as_of_date: date | None = None,
) -> list[dict]:
    """Filter & enrich candidates for the self-assembled-ETF use case.

    Pipeline:
      1. 年年配息（近 N 年每年至少 1 次除息）
      2. 配息穩定度 CV ≤ DIVIDEND_CV_MAX（剔除一次性高配發 / 景氣循環）
      3. Momentum boost：對 yield 前 MOMENTUM_POOL_SIZE 名計算 3 月漲跌幅，
         re-sort by 「yield + momentum*100」 → 強勢股優先進入 sector cap
      4. 產業分散：每個 industry 最多 SECTOR_CAP 檔
      5. 股價 N 年 CAGR ≥ PRICE_CAGR_MIN（擋價值陷阱）
      6. 至少成功填息 1 次（近 N 年內）

    Adds fields: dividend_cv, momentum_3m, industry, price_cagr_3y,
                 avg_fill_days, fill_rate, fill_samples, last_ex_date.
    `as_of_date` defaults to today; backtest passes a past date.
    """
    base = as_of_date or date.today()
    target_years = set(range(base.year - DIVIDEND_YEARS, base.year))

    sectors = _load_sectors()

    with httpx.Client(timeout=TWSE_TIMEOUT, follow_redirects=True, headers=TWSE_HEADERS) as client:
        print(f"[Dividend] fetching TWT49U for years {sorted(target_years)}...")
        events_map = _fetch_dividend_events(client, DIVIDEND_YEARS, as_of_date=base)
        print(f"[Dividend] {len(events_map)} stocks have ex-dividend records in that window")

        # ── Stage A: 年年配息 + CV 穩定度 ─────────────────────────────────────
        eligible: list[dict] = []
        cv_dropped = year_dropped = 0
        for c in raw:
            events = events_map.get(c["symbol"], [])
            years_seen = {e["year"] for e in events}
            if not target_years.issubset(years_seen):
                year_dropped += 1
                continue
            cv = _annual_dividend_cv(events, target_years)
            if cv is None or cv > DIVIDEND_CV_MAX:
                cv_dropped += 1
                continue
            c["dividend_cv"] = round(cv, 3)
            eligible.append(c)
        print(
            f"[Dividend] {len(eligible)}/{len(raw)} pass annual×{DIVIDEND_YEARS}y + CV≤{DIVIDEND_CV_MAX} "
            f"(dropped: missing_year={year_dropped}, unstable={cv_dropped})"
        )

        # ── Stage A.5: Momentum factor — boost 強勢股排序 ───────────────────
        cache: dict = {}
        momentum_pool = eligible[:MOMENTUM_POOL_SIZE]
        print(f"[Momentum] computing {MOMENTUM_LOOKBACK_MONTHS}m momentum for top {len(momentum_pool)} by yield...")
        for c in momentum_pool:
            mom = _compute_momentum(
                client, c["symbol"], c["price"], cache,
                MOMENTUM_LOOKBACK_MONTHS, as_of_date=base,
            )
            c["momentum_3m"] = round(mom, 3) if mom is not None else None
        # 池外的候選不算 momentum；後面排序時當 0 處理（純 yield 排序）
        for c in eligible[MOMENTUM_POOL_SIZE:]:
            c["momentum_3m"] = None

        # Re-sort：combined score = yield_rate + momentum_3m * 100
        # （momentum 是 fraction，乘 100 換成跟 yield 同單位的百分比）
        def _combined_score(c: dict) -> float:
            mom = c.get("momentum_3m") or 0.0
            return c["yield_rate"] + mom * 100

        eligible.sort(key=_combined_score, reverse=True)
        avg_mom = (
            sum(c["momentum_3m"] for c in momentum_pool if c["momentum_3m"] is not None)
            / max(1, sum(1 for c in momentum_pool if c["momentum_3m"] is not None))
        )
        print(f"[Momentum] avg momentum in pool: {avg_mom*100:+.1f}%; re-sorted by combined score")

        # ── Stage B: 產業分散 ────────────────────────────────────────────────
        diversified = _apply_sector_cap(eligible, sectors, SECTOR_CAP)
        industry_breakdown = {}
        for c in diversified:
            industry_breakdown[c["industry"]] = industry_breakdown.get(c["industry"], 0) + 1
        print(
            f"[Sector] {len(diversified)} after cap (≤{SECTOR_CAP}/industry, "
            f"{len(industry_breakdown)} industries)"
        )

        # ── Stage C: 股價 3 年 CAGR 過濾（擋價值陷阱） ──────────────────────
        # （cache 在 Stage A.5 已宣告並開始累積）
        print(f"[CAGR] computing {CAGR_LOOKBACK_YEARS}y price CAGR for {len(diversified)} stocks...")
        healthy: list[dict] = []
        cagr_dropped = cagr_missing = 0
        for c in diversified:
            cagr = _compute_price_cagr(
                client, c["symbol"], c["price"], cache, CAGR_LOOKBACK_YEARS,
                as_of_date=base,
            )
            if cagr is None:
                cagr_missing += 1
                c["price_cagr_3y"] = None
                healthy.append(c)  # 資料缺漏時保留，避免誤殺
                continue
            if cagr < PRICE_CAGR_MIN:
                cagr_dropped += 1
                continue
            c["price_cagr_3y"] = round(cagr, 3)
            healthy.append(c)
        print(
            f"[CAGR] {len(healthy)}/{len(diversified)} pass CAGR ≥ {PRICE_CAGR_MIN:+.0%}/yr "
            f"(dropped: trap={cagr_dropped}, missing_data={cagr_missing} kept)"
        )

        # ── Stage D: fill 計算（限制 FILL_CHECK_POOL 避免 TWSE 請求爆量） ────
        pool = healthy[:FILL_CHECK_POOL]
        print(f"[Dividend] computing fill-days for {len(pool)} stocks (pool={FILL_CHECK_POOL})...")

        for idx, c in enumerate(pool, 1):
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
            c["last_ex_date"]  = max(e["ex_date"] for e in events).isoformat() if events else None
            if idx % 10 == 0:
                print(f"[Dividend] progress {idx}/{len(pool)}")

        # ── Stage E: 至少成功填息 1 次 ──────────────────────────────────────
        filled = [c for c in pool if c["fill_samples"] > 0]
        print(f"[Dividend] {len(filled)}/{len(pool)} have ≥1 successful fill")

        top = filled[:MAX_CANDIDATES]
        print(f"[Dividend] final candidates for AI: {len(top)}")

    return top


# ── Stage 3: Claude Haiku ──────────────────────────────────────────────────────

# Anthropic 偶爾會在尖峰時段回傳 529 overloaded — 用指數退避重試蓋過短暫過載
CLAUDE_OVERLOAD_RETRIES = 5
CLAUDE_BACKOFF_BASE = 8.0   # 8s, 16s, 32s, 64s, 128s（含 jitter，最長約 2 分鐘）


def _claude_create_with_retry(client: anthropic.Anthropic, user_msg: str):
    """Call messages.create, retrying on 529/429/5xx with exponential backoff."""
    for attempt in range(CLAUDE_OVERLOAD_RETRIES):
        try:
            return client.messages.create(
                model=AI_MODEL,
                # 4 段 reason × 10 picks 在 4000 tokens 內會被截斷導致 unterminated string
                # JSON parse fail。8000 給足夠 headroom，Haiku 成本影響 < $0.01/call
                max_tokens=8000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
        except anthropic.APIStatusError as exc:
            status = getattr(exc, "status_code", None)
            retryable = status in (429, 529) or (status is not None and 500 <= status < 600)
            if not retryable or attempt == CLAUDE_OVERLOAD_RETRIES - 1:
                raise
            delay = CLAUDE_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 2)
            print(
                f"[Claude] status {status} (attempt {attempt+1}/{CLAUDE_OVERLOAD_RETRIES}) — "
                f"retrying in {delay:.1f}s",
                file=sys.stderr,
            )
            time.sleep(delay)
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
            if attempt == CLAUDE_OVERLOAD_RETRIES - 1:
                raise
            delay = CLAUDE_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 2)
            print(
                f"[Claude] {type(exc).__name__} (attempt {attempt+1}/{CLAUDE_OVERLOAD_RETRIES}) — "
                f"retrying in {delay:.1f}s",
                file=sys.stderr,
            )
            time.sleep(delay)


def call_claude(candidates: list[dict]) -> list[dict]:
    user_msg = (
        "候選股票清單（含過去 3 年填息資料、配息穩定度、產業別、股價 CAGR、近 3 月動能）：\n"
        + json.dumps(candidates, ensure_ascii=False, indent=2)
        + "\n\n"
        "請回傳純 JSON（不含 markdown code block），格式如下。"
        "注意 reason 是 4 段結構字串，用 \\n\\n 分隔段落：\n"
        '{"picks": [{"symbol": "2330", "name": "台積電",'
        ' "reason": "【持有邏輯】全球晶圓代工龍頭，技術領先 + 客戶綁定深，現金流可長期預測。\\n\\n'
        '【組合角色】成長補位 — 提供半導體景氣紅利，平衡高股息部位的低成長性。\\n\\n'
        '【風險】景氣循環股，營收與全球半導體 capex 高度連動，下行週期可能短期回檔 20%+。\\n\\n'
        '【近況脈絡】市場一般認為 AI 算力需求支撐先進製程訂單，但客戶端集中度高仍是長期觀察點。",'
        ' "yield_rate": 2.5, "pe_ratio": 18.2, "price": 850.0,'
        ' "industry": "半導體", "dividend_cv": 0.15, "price_cagr_3y": 0.12,'
        ' "momentum_3m": 0.08,'
        ' "avg_fill_days": 30.5, "fill_rate": 1.0, "fill_samples": 3,'
        ' "last_ex_date": "2025-07-15"}]}'
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    for attempt in range(2):
        msg = _claude_create_with_retry(client, user_msg)
        original = msg.content[0].text if msg.content else ""
        raw = _escape_unescaped_lf(_extract_json(original))
        try:
            result = json.loads(raw)
            picks = result.get("picks", [])
            print(f"[Claude] {len(picks)} picks returned")
            return picks
        except json.JSONDecodeError as exc:
            stop = getattr(msg, "stop_reason", "?")
            usage = getattr(msg, "usage", None)
            out_tok = getattr(usage, "output_tokens", "?") if usage else "?"
            print(
                f"[Claude] JSON parse error (attempt {attempt+1}/2): {exc} "
                f"[stop_reason={stop} output_tokens={out_tok}]",
                file=sys.stderr,
            )
            print(f"[Claude] raw response (first 300 chars): {original[:300]!r}", file=sys.stderr)
            print(f"[Claude] extracted (first 300 chars): {raw[:300]!r}", file=sys.stderr)
            print(f"[Claude] raw response (last 300 chars): {original[-300:]!r}", file=sys.stderr)

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
        cv = p.get("dividend_cv")
        cv_info = f"cv={cv}" if cv is not None else "cv=N/A"
        cagr = p.get("price_cagr_3y")
        cagr_info = f"cagr={cagr*100:+.1f}%/y" if cagr is not None else "cagr=N/A"
        mom = p.get("momentum_3m")
        mom_info = f"mom={mom*100:+.1f}%" if mom is not None else "mom=N/A"
        industry = p.get("industry", "?")
        print(
            f"  {p['symbol']} {p['name']} [{industry}]  yield={p['yield_rate']}%  "
            f"PE={p['pe_ratio']}  ${p['price']}  {cv_info}  {cagr_info}  {mom_info}  {fill_info}"
        )


if __name__ == "__main__":
    main()
