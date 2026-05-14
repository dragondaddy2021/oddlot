"""Backtest oddlot 選股演算法 vs 被動式 ETF（0056 主要、0050 次要）。

兩階段設計：
  Phase 1 (collect): 在過去 N 個月日期跑 pipeline，把每次的 10 檔 picks
    存到 backtest_picks.json。這是慢的部分（每次 ~15 分，含 Claude 呼叫）。
  Phase 2 (analyze): 讀取 picks JSON，抓 STOCK_DAY 算每檔報酬、benchmark
    報酬，輸出 markdown 報告。可獨立重跑（換基準、加 split fix 等）。

執行：
  python backtest.py                  # 完整跑（collect + analyze）
  python backtest.py --recompute      # 只跑 analyze（用現有 picks JSON）
  python backtest.py --collect-only   # 只跑 collect，跳過 analyze

輸出：
  backend/scripts/backtest_picks.json   — 各 snapshot 的 10 檔
  backend/scripts/backtest_results.md   — 績效報告
"""
import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

from daily_selection import (
    TWSE_HEADERS,
    TWSE_TIMEOUT,
    _fetch_stock_month,
    call_claude,
    enrich_with_dividend_stats,
    fetch_candidates,
)

# ── 回測參數 ──
BENCHMARK_PRIMARY   = "0056"   # 元大高股息 — 風格貼近 oddlot 演算法
BENCHMARK_SECONDARY = "0050"   # 元大台灣50 — 大盤代表（含 split adjustment）
SNAPSHOT_COUNT      = 36       # 過去 36 個月（3 年），跨多個市況
SNAPSHOT_STRIDE     = 30       # 兩個 snapshot 之間相隔 N 天

# 多時間窗口報酬：(label, days)。None = 持有至 HOLD_END（最長持有）
RETURN_WINDOWS = [
    ("3M",     90),
    ("6M",     180),
    ("12M",    365),
    ("to_end", None),
]

# 跨 run 續跑（GitHub Actions 6 小時硬上限）：保留 ~20 分鐘給 commit/upload 步驟
COLLECT_BUDGET_SEC  = 5 * 3600 + 40 * 60   # 5h 40min

PICKS_JSON          = Path(__file__).parent / "backtest_picks.json"
RESULTS_MD          = Path(__file__).parent / "backtest_results.md"


def _resolve_hold_end() -> date:
    """HOLD_END 自動推斷：若已有 picks JSON，取最新 snapshot + STRIDE 為錨點，
    保證跨 run 報酬計算終點一致；若無，預設為今天。
    """
    if PICKS_JSON.exists():
        try:
            data = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
            keys = sorted(data.keys())
            if keys:
                latest = date.fromisoformat(keys[-1])
                inferred = latest + timedelta(days=SNAPSHOT_STRIDE)
                return min(inferred, date.today())
        except Exception:
            pass
    return date.today()


HOLD_END = _resolve_hold_end()

# 已知 ETF / 股票拆股事件：raw STOCK_DAY 不調整歷史價，需手動補
# 格式：{symbol: [(split_date, ratio), ...]}
# 1:N split → 拆股當天 N 股取代 1 股，每股價變為原 1/N
SPLIT_EVENTS: dict[str, list[tuple[date, int]]] = {
    # 元大台灣50 在 2025-06-11~6/17 停牌進行 1:4 分割，6/18 首日復牌
    # split_date 設為首日復牌日 → 邏輯：「start_date < split_date <= end_date」時應用 factor
    "0050": [(date(2025, 6, 18), 4)],
}


# ── Price helpers ──────────────────────────────────────────────────────────────

def _close_on_or_after(
    client: httpx.Client,
    symbol: str,
    target: date,
    cache: dict,
    max_months: int = 2,
) -> tuple[date, float] | None:
    cur = target.replace(day=1)
    for _ in range(max_months):
        yyyymm = f"{cur.year}{cur.month:02d}"
        daily = _fetch_stock_month(client, symbol, yyyymm, cache)
        for d, close in daily:
            if d >= target:
                return (d, close)
        cur = (
            date(cur.year + 1, 1, 1)
            if cur.month == 12
            else date(cur.year, cur.month + 1, 1)
        )
    return None


def _close_on_or_before(
    client: httpx.Client,
    symbol: str,
    target: date,
    cache: dict,
    max_months: int = 2,
) -> tuple[date, float] | None:
    cur = target.replace(day=1)
    for _ in range(max_months):
        yyyymm = f"{cur.year}{cur.month:02d}"
        daily = _fetch_stock_month(client, symbol, yyyymm, cache)
        valid = [(d, c) for d, c in daily if d <= target]
        if valid:
            return max(valid, key=lambda x: x[0])
        cur = (
            date(cur.year - 1, 12, 1)
            if cur.month == 1
            else date(cur.year, cur.month - 1, 1)
        )
    return None


def _split_factor(symbol: str, start: date, end: date) -> float:
    """Cumulative split factor for splits in (start, end]. 1.0 if no splits."""
    factor = 1.0
    for split_date, ratio in SPLIT_EVENTS.get(symbol, []):
        if start < split_date <= end:
            factor *= ratio
    return factor


def _holding_return(
    client: httpx.Client,
    symbol: str,
    start: date,
    end: date,
    cache: dict,
) -> float | None:
    """Total price return (split-adjusted) from start → end. None on missing data.

    Formula:  return = (factor * end_price - start_price) / start_price
    where `factor` accounts for splits between start and end.
    """
    s = _close_on_or_after(client, symbol, start, cache)
    e = _close_on_or_before(client, symbol, end, cache)
    if s is None or e is None or s[1] <= 0:
        return None
    factor = _split_factor(symbol, s[0], e[0])
    return (factor * e[1] - s[1]) / s[1]


# ── Phase 1: Collect picks ─────────────────────────────────────────────────────

def run_snapshot(snapshot_date: date) -> list[dict]:
    """Replay pipeline as of `snapshot_date`, return 10 picks (or [])."""
    print(f"\n========== Snapshot: {snapshot_date} ==========", flush=True)
    try:
        raw = fetch_candidates(as_of_date=snapshot_date)
    except Exception as exc:
        print(f"[Backtest] fetch_candidates failed for {snapshot_date}: {exc}", file=sys.stderr)
        return []
    if not raw:
        return []

    try:
        candidates = enrich_with_dividend_stats(raw, as_of_date=snapshot_date)
    except Exception as exc:
        print(f"[Backtest] enrich failed for {snapshot_date}: {exc}", file=sys.stderr)
        return []
    if not candidates:
        return []

    try:
        picks = call_claude(candidates)
    except Exception as exc:
        print(f"[Backtest] Claude failed for {snapshot_date}: {exc}", file=sys.stderr)
        return []

    return picks


def collect_picks() -> dict[str, list[dict]]:
    """Run pipeline for each snapshot and persist to PICKS_JSON.

    Bails gracefully when COLLECT_BUDGET_SEC is reached so the workflow can
    commit progress and re-run later (續跑機制依賴 PICKS_JSON 內已有的 keys）.
    """
    snapshots = [
        HOLD_END - timedelta(days=SNAPSHOT_STRIDE * i)
        for i in range(SNAPSHOT_COUNT, 0, -1)
    ]

    # If picks JSON already exists, preserve completed snapshots (resume support)
    existing: dict[str, list[dict]] = {}
    if PICKS_JSON.exists():
        try:
            existing = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
            print(f"[Backtest] resuming — found {len(existing)} existing snapshots in picks.json")
        except Exception:
            existing = {}

    start_ts = time.time()
    for snap in snapshots:
        key = snap.isoformat()
        if key in existing and existing[key]:
            print(f"[Backtest] skipping {key} (already collected)")
            continue

        elapsed = time.time() - start_ts
        if elapsed > COLLECT_BUDGET_SEC:
            print(
                f"[Backtest] time budget reached ({elapsed/60:.1f} min) — "
                f"stopping collect; trigger workflow again to resume",
                file=sys.stderr,
            )
            break

        picks = run_snapshot(snap)
        existing[key] = picks
        # Save after each snapshot for resume safety
        PICKS_JSON.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"\n[Backtest] picks saved to {PICKS_JSON} ({len(existing)} snapshots total)")
    return existing


# ── Phase 2: Analyze returns + write report ────────────────────────────────────

def _window_end(snap: date, window_days: int | None) -> date:
    """Determine end date for a given holding window. None = HOLD_END."""
    if window_days is None:
        return HOLD_END
    return min(snap + timedelta(days=window_days), HOLD_END)


def _avg_return(client, picks, snap, end, cache):
    """Mean of pick returns over [snap, end]; None if no valid picks."""
    rs = []
    for p in picks:
        r = _holding_return(client, p["symbol"], snap, end, cache)
        if r is not None:
            rs.append(r)
    return sum(rs) / len(rs) if rs else None


def analyze() -> None:
    if not PICKS_JSON.exists():
        print(f"[Backtest] {PICKS_JSON} not found — run collect first", file=sys.stderr)
        sys.exit(1)

    all_picks = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
    snapshots = sorted(date.fromisoformat(k) for k in all_picks.keys())

    cache: dict = {}
    results: list[dict] = []

    with httpx.Client(timeout=TWSE_TIMEOUT, follow_redirects=True, headers=TWSE_HEADERS) as client:
        for snap in snapshots:
            picks = all_picks.get(snap.isoformat()) or []
            row: dict = {"date": snap, "picks": picks, "windows": {}, "to_end_returns": []}

            # 計算每個時間窗口
            for label, days in RETURN_WINDOWS:
                end = _window_end(snap, days)
                # snapshot 太新 → 該窗口尚未滿，標記 N/A
                if end <= snap:
                    row["windows"][label] = {"oddlot": None, "primary": None, "secondary": None, "end": end}
                    continue
                oddlot_avg = _avg_return(client, picks, snap, end, cache)
                bp = _holding_return(client, BENCHMARK_PRIMARY, snap, end, cache)
                bs = _holding_return(client, BENCHMARK_SECONDARY, snap, end, cache)
                row["windows"][label] = {
                    "oddlot": oddlot_avg, "primary": bp, "secondary": bs, "end": end,
                }

                # to_end window: also save per-pick returns for detailed table
                if days is None:
                    pick_returns = []
                    for p in picks:
                        r = _holding_return(client, p["symbol"], snap, end, cache)
                        pick_returns.append((p["symbol"], p.get("name", "?"), r))
                    row["to_end_returns"] = pick_returns

            results.append(row)

            def fmt(x):
                return f"{x*100:+.2f}%" if x is not None else "N/A"
            w6 = row["windows"]["6M"]
            w_end = row["windows"]["to_end"]
            print(
                f"[Backtest] {snap}: 6M oddlot={fmt(w6['oddlot'])} {BENCHMARK_PRIMARY}={fmt(w6['primary'])}; "
                f"to_end oddlot={fmt(w_end['oddlot'])} {BENCHMARK_PRIMARY}={fmt(w_end['primary'])}",
                flush=True,
            )

    write_report(results)


def write_report(results: list[dict]) -> None:
    lines = [
        "# oddlot Backtest Report",
        "",
        f"- 產生時間：{date.today()}",
        f"- 持有結束日：{HOLD_END}",
        f"- 主要基準：**{BENCHMARK_PRIMARY}**（元大高股息，風格貼近 oddlot 演算法）",
        f"- 次要基準：{BENCHMARK_SECONDARY}（元大台灣50，大盤代表）",
        f"- Snapshot 間隔：{SNAPSHOT_STRIDE} 天 × {SNAPSHOT_COUNT} 次",
        f"- 報酬窗口：{', '.join(label for label, _ in RETURN_WINDOWS)}",
        "",
        "> 注意：本回測**只計算價格報酬**，不含現金股利再投入。實際長期持有總報酬會略高於本表，",
        "> 但相對比較（vs 0056 / 0050）仍公平 — 三者皆用相同方式計算。",
        "> 已處理 0050 在 2025-06-18 的 1:4 拆股。",
        "",
    ]

    def fmt_pct(x):
        return f"{x*100:+.2f}%" if x is not None else "—"

    def diff_flag(a, b):
        if a is None or b is None:
            return "—"
        d = a - b
        flag = "🟢" if d > 0 else "🔴" if d < 0 else "⚪"
        return f"{flag} {d*100:+.2f}%"

    # ── Aggregate by window ───────────────────────────────────────────────────
    lines += ["## Aggregate（按時間窗口分）", ""]
    lines += [
        f"| 窗口 | 有效 snaps | oddlot 平均 | {BENCHMARK_PRIMARY} 平均 | 超額 | 勝率 vs {BENCHMARK_PRIMARY} | {BENCHMARK_SECONDARY} 平均 | 勝率 vs {BENCHMARK_SECONDARY} |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, _ in RETURN_WINDOWS:
        valid_p = [
            r for r in results
            if r["windows"][label]["oddlot"] is not None
            and r["windows"][label]["primary"] is not None
        ]
        valid_s = [
            r for r in results
            if r["windows"][label]["oddlot"] is not None
            and r["windows"][label]["secondary"] is not None
        ]
        if not valid_p:
            lines.append(f"| {label} | 0 | — | — | — | — | — | — |")
            continue
        avg_o  = sum(r["windows"][label]["oddlot"] for r in valid_p) / len(valid_p)
        avg_bp = sum(r["windows"][label]["primary"] for r in valid_p) / len(valid_p)
        wins_p = sum(1 for r in valid_p if r["windows"][label]["oddlot"] > r["windows"][label]["primary"])
        if valid_s:
            avg_bs = sum(r["windows"][label]["secondary"] for r in valid_s) / len(valid_s)
            wins_s = sum(1 for r in valid_s if r["windows"][label]["oddlot"] > r["windows"][label]["secondary"])
            bs_str = fmt_pct(avg_bs)
            wins_s_str = f"{wins_s}/{len(valid_s)} ({wins_s/len(valid_s)*100:.0f}%)"
        else:
            bs_str = "—"
            wins_s_str = "—"
        lines.append(
            f"| **{label}** | {len(valid_p)} | {fmt_pct(avg_o)} | {fmt_pct(avg_bp)} | "
            f"{(avg_o - avg_bp)*100:+.2f}% | {wins_p}/{len(valid_p)} ({wins_p/len(valid_p)*100:.0f}%) | "
            f"{bs_str} | {wins_s_str} |"
        )

    # ── Per-snapshot table per window ─────────────────────────────────────────
    for label, days in RETURN_WINDOWS:
        lines += ["", f"## Per-Snapshot：{label} 報酬窗口", ""]
        lines += [
            f"| Snapshot | oddlot | {BENCHMARK_PRIMARY} | vs | {BENCHMARK_SECONDARY} | vs | 窗口結束 |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in results:
            w = r["windows"][label]
            lines.append(
                f"| {r['date']} | {fmt_pct(w['oddlot'])} | "
                f"{fmt_pct(w['primary'])} | {diff_flag(w['oddlot'], w['primary'])} | "
                f"{fmt_pct(w['secondary'])} | {diff_flag(w['oddlot'], w['secondary'])} | "
                f"{w['end']} |"
            )

    # ── Per-snapshot pick details (using to_end window) ───────────────────────
    lines += ["", "## 各 snapshot 詳細選股（to_end 窗口報酬）"]
    for r in results:
        days = (HOLD_END - r["date"]).days
        lines += ["", f"### {r['date']} (持有 {days} 天)"]
        if not r["picks"]:
            lines.append("（pipeline 失敗或無資料）")
            continue
        lines += [
            "",
            "| 代號 | 名稱 | 產業 | 殖利率 | CAGR/yr | 動能 3M | 報酬 |",
            "|---|---|---|---|---|---|---|",
        ]
        ret_map = {sym: ret for sym, _, ret in r.get("to_end_returns", [])}
        for p in r["picks"]:
            ret = ret_map.get(p["symbol"])
            cagr = p.get("price_cagr_3y")
            cagr_str = f"{cagr*100:+.1f}%" if cagr is not None else "—"
            mom = p.get("momentum_3m")
            mom_str = f"{mom*100:+.1f}%" if mom is not None else "—"
            lines.append(
                f"| {p['symbol']} | {p.get('name','?')} | {p.get('industry','?')} | "
                f"{p.get('yield_rate','?')}% | {cagr_str} | {mom_str} | {fmt_pct(ret)} |"
            )

    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[Backtest] Report written to {RESULTS_MD}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="oddlot backtest")
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="跳過 collect，只用現有 backtest_picks.json 重算 returns 與報告",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="只跑 collect 階段（不算 returns、不寫報告）",
    )
    args = parser.parse_args()

    print(f"=== oddlot backtest ===")
    print(f"Snapshots: {SNAPSHOT_COUNT} (every {SNAPSHOT_STRIDE} days)")
    print(f"Hold end:  {HOLD_END}")
    print(f"Benchmarks: {BENCHMARK_PRIMARY} (primary), {BENCHMARK_SECONDARY} (secondary)")

    if not args.recompute:
        collect_picks()

    if not args.collect_only:
        analyze()


if __name__ == "__main__":
    main()
