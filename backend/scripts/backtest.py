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
HOLD_END            = date.today()

PICKS_JSON          = Path(__file__).parent / "backtest_picks.json"
RESULTS_MD          = Path(__file__).parent / "backtest_results.md"

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
    """Run pipeline for each snapshot and persist to PICKS_JSON."""
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

    for snap in snapshots:
        key = snap.isoformat()
        if key in existing and existing[key]:
            print(f"[Backtest] skipping {key} (already collected)")
            continue
        picks = run_snapshot(snap)
        existing[key] = picks
        # Save after each snapshot for resume safety
        PICKS_JSON.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"\n[Backtest] picks saved to {PICKS_JSON}")
    return existing


# ── Phase 2: Analyze returns + write report ────────────────────────────────────

def analyze() -> None:
    if not PICKS_JSON.exists():
        print(f"[Backtest] {PICKS_JSON} not found — run collect first", file=sys.stderr)
        sys.exit(1)

    all_picks = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
    snapshots = sorted(date.fromisoformat(k) for k in all_picks.keys())

    cache: dict = {}
    results: list[dict] = []

    with httpx.Client(timeout=TWSE_TIMEOUT, follow_redirects=True, headers=TWSE_HEADERS) as client:
        # Benchmark caches — fetch once
        for snap in snapshots:
            picks = all_picks.get(snap.isoformat()) or []

            # Per-pick returns
            returns: list[tuple[str, str, float | None]] = []
            for p in picks:
                r = _holding_return(client, p["symbol"], snap, HOLD_END, cache)
                returns.append((p["symbol"], p.get("name", "?"), r))
            valid = [r for _, _, r in returns if r is not None]
            avg = sum(valid) / len(valid) if valid else None

            # Benchmarks
            b1 = _holding_return(client, BENCHMARK_PRIMARY, snap, HOLD_END, cache)
            b2 = _holding_return(client, BENCHMARK_SECONDARY, snap, HOLD_END, cache)

            results.append({
                "date": snap,
                "picks": picks,
                "returns": returns,
                "avg": avg,
                "benchmark_primary": b1,
                "benchmark_secondary": b2,
            })

            def fmt(x):
                return f"{x*100:+.2f}%" if x is not None else "N/A"
            print(f"[Backtest] {snap}: oddlot={fmt(avg)}  "
                  f"{BENCHMARK_PRIMARY}={fmt(b1)}  "
                  f"{BENCHMARK_SECONDARY}={fmt(b2)}", flush=True)

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
        "",
        "> 注意：本回測**只計算價格報酬**，不含現金股利再投入。實際長期持有總報酬會略高於本表，",
        "> 但相對比較（vs 0056 / 0050）仍公平 — 三者皆用相同方式計算。",
        "> 已處理 0050 在 2025-06-23 的 1:4 拆股。",
        "",
        "## Per-Snapshot Results",
        "",
        f"| Snapshot | oddlot 平均 | {BENCHMARK_PRIMARY} | vs {BENCHMARK_PRIMARY} | {BENCHMARK_SECONDARY} | vs {BENCHMARK_SECONDARY} | 持有天 |",
        "|---|---|---|---|---|---|---|",
    ]

    def fmt_pct(x):
        return f"{x*100:+.2f}%" if x is not None else "—"

    def diff_flag(a, b):
        if a is None or b is None:
            return "—"
        d = a - b
        flag = "🟢" if d > 0 else "🔴" if d < 0 else "⚪"
        return f"{flag} {d*100:+.2f}%"

    for r in results:
        days = (HOLD_END - r["date"]).days
        lines.append(
            f"| {r['date']} | {fmt_pct(r['avg'])} | "
            f"{fmt_pct(r['benchmark_primary'])} | "
            f"{diff_flag(r['avg'], r['benchmark_primary'])} | "
            f"{fmt_pct(r['benchmark_secondary'])} | "
            f"{diff_flag(r['avg'], r['benchmark_secondary'])} | {days} |"
        )

    # Aggregate
    valid_p = [r for r in results if r["avg"] is not None and r["benchmark_primary"] is not None]
    valid_s = [r for r in results if r["avg"] is not None and r["benchmark_secondary"] is not None]

    lines += ["", "## Aggregate"]
    if valid_p:
        avg_o = sum(r["avg"] for r in valid_p) / len(valid_p)
        avg_b = sum(r["benchmark_primary"] for r in valid_p) / len(valid_p)
        wins  = sum(1 for r in valid_p if r["avg"] > r["benchmark_primary"])
        lines += [
            "",
            f"### vs {BENCHMARK_PRIMARY} (主要基準, {len(valid_p)} 個有效 snapshot)",
            "",
            f"- **oddlot 平均報酬**：{avg_o*100:+.2f}%",
            f"- **{BENCHMARK_PRIMARY} 平均報酬**：{avg_b*100:+.2f}%",
            f"- **平均超額報酬**：{(avg_o - avg_b)*100:+.2f}%",
            f"- **勝率**：{wins}/{len(valid_p)} ({wins/len(valid_p)*100:.0f}%)",
        ]
    if valid_s:
        avg_o = sum(r["avg"] for r in valid_s) / len(valid_s)
        avg_b = sum(r["benchmark_secondary"] for r in valid_s) / len(valid_s)
        wins  = sum(1 for r in valid_s if r["avg"] > r["benchmark_secondary"])
        lines += [
            "",
            f"### vs {BENCHMARK_SECONDARY} (次要基準, {len(valid_s)} 個有效 snapshot)",
            "",
            f"- **oddlot 平均報酬**：{avg_o*100:+.2f}%",
            f"- **{BENCHMARK_SECONDARY} 平均報酬**：{avg_b*100:+.2f}%",
            f"- **平均超額報酬**：{(avg_o - avg_b)*100:+.2f}%",
            f"- **勝率**：{wins}/{len(valid_s)} ({wins/len(valid_s)*100:.0f}%)",
        ]

    # Per-snapshot pick details
    lines += ["", "## 各 snapshot 詳細選股"]
    for r in results:
        days = (HOLD_END - r["date"]).days
        lines += ["", f"### {r['date']} (持有 {days} 天)"]
        if not r["picks"]:
            lines.append("（pipeline 失敗或無資料）")
            continue
        lines += [
            "",
            "| 代號 | 名稱 | 產業 | 殖利率 | CAGR/yr | 報酬 |",
            "|---|---|---|---|---|---|",
        ]
        ret_map = {sym: ret for sym, _, ret in r["returns"]}
        for p in r["picks"]:
            ret = ret_map.get(p["symbol"])
            cagr = p.get("price_cagr_3y")
            cagr_str = f"{cagr*100:+.1f}%" if cagr is not None else "—"
            lines.append(
                f"| {p['symbol']} | {p.get('name','?')} | {p.get('industry','?')} | "
                f"{p.get('yield_rate','?')}% | {cagr_str} | {fmt_pct(ret)} |"
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
