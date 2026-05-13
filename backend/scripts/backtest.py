"""Backtest oddlot 選股演算法 vs 0050 基準。

每月一個 snapshot × 12 個月，每次模擬「在那一天執行 daily_selection 會選出哪 10 檔」，
並追蹤從 snapshot 日到今天的價格報酬，最後與 0050 同期間報酬比較。

注意：本回測**只計算價格報酬**，不含現金股利再投入（簡化 MVP）。
實際長期持有的總報酬會略高於報告數字，但相對比較（vs 0050）仍公平。

執行：
    ANTHROPIC_API_KEY=... python backend/scripts/backtest.py

輸出：backend/scripts/backtest_results.md
"""
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
BENCHMARK       = "0050"
SNAPSHOT_COUNT  = 12       # 過去 12 個月，每月 1 個 snapshot
SNAPSHOT_STRIDE = 30       # 兩個 snapshot 之間相隔 N 天
HOLD_END        = date.today()
OUTPUT          = Path(__file__).parent / "backtest_results.md"


# ── Helpers ──

def _close_on_or_after(
    client: httpx.Client,
    symbol: str,
    target: date,
    cache: dict,
    max_months: int = 2,
) -> tuple[date, float] | None:
    """First trading-day close on or after `target`."""
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
    """Last trading-day close on or before `target`."""
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


def _holding_return(
    client: httpx.Client,
    symbol: str,
    start: date,
    end: date,
    cache: dict,
) -> float | None:
    """Price-only return from start to end. Returns None on missing data."""
    s = _close_on_or_after(client, symbol, start, cache)
    e = _close_on_or_before(client, symbol, end, cache)
    if s is None or e is None or s[1] <= 0:
        return None
    return (e[1] - s[1]) / s[1]


# ── 核心 ──

def run_snapshot(snapshot_date: date) -> list[dict]:
    """Replay pipeline as of `snapshot_date`, return 10 picks (or [])."""
    print(f"\n========== Snapshot: {snapshot_date} ==========", flush=True)
    try:
        raw = fetch_candidates(as_of_date=snapshot_date)
    except Exception as exc:
        print(f"[Backtest] fetch_candidates failed for {snapshot_date}: {exc}", file=sys.stderr)
        return []
    if not raw:
        print(f"[Backtest] no raw candidates for {snapshot_date}", file=sys.stderr)
        return []

    try:
        candidates = enrich_with_dividend_stats(raw, as_of_date=snapshot_date)
    except Exception as exc:
        print(f"[Backtest] enrich failed for {snapshot_date}: {exc}", file=sys.stderr)
        return []

    if not candidates:
        print(f"[Backtest] no candidates after enrichment for {snapshot_date}", file=sys.stderr)
        return []

    try:
        picks = call_claude(candidates)
    except Exception as exc:
        print(f"[Backtest] Claude failed for {snapshot_date}: {exc}", file=sys.stderr)
        return []

    return picks


def main() -> None:
    print(f"=== oddlot backtest ===")
    print(f"Snapshots: {SNAPSHOT_COUNT} (every {SNAPSHOT_STRIDE} days)")
    print(f"Hold end:  {HOLD_END}")
    print(f"Benchmark: {BENCHMARK}")

    # 從最舊到最新跑（讓報告時序自然）
    snapshots = [
        HOLD_END - timedelta(days=SNAPSHOT_STRIDE * i)
        for i in range(SNAPSHOT_COUNT, 0, -1)
    ]

    cache: dict = {}
    results: list[dict] = []

    with httpx.Client(timeout=TWSE_TIMEOUT, follow_redirects=True, headers=TWSE_HEADERS) as client:
        for snap in snapshots:
            picks = run_snapshot(snap)
            if not picks:
                results.append({
                    "date": snap, "picks": [], "returns": [],
                    "avg": None, "benchmark": None,
                })
                continue

            # 計算每檔的持有報酬
            print(f"[Backtest] computing holding returns for {len(picks)} picks...")
            returns: list[tuple[str, str, float | None]] = []
            for p in picks:
                r = _holding_return(client, p["symbol"], snap, HOLD_END, cache)
                returns.append((p["symbol"], p.get("name", "?"), r))

            valid = [r for _, _, r in returns if r is not None]
            avg = sum(valid) / len(valid) if valid else None

            bench = _holding_return(client, BENCHMARK, snap, HOLD_END, cache)

            results.append({
                "date": snap,
                "picks": picks,
                "returns": returns,
                "avg": avg,
                "benchmark": bench,
            })

            avg_str = f"{avg*100:+.2f}%" if avg is not None else "N/A"
            bench_str = f"{bench*100:+.2f}%" if bench is not None else "N/A"
            print(f"[Backtest] {snap}: oddlot={avg_str}  0050={bench_str}", flush=True)

    write_report(results)


def write_report(results: list[dict]) -> None:
    lines = [
        "# oddlot Backtest Report",
        "",
        f"- 產生時間：{date.today()}",
        f"- 持有結束日：{HOLD_END}",
        f"- 基準：{BENCHMARK}",
        f"- Snapshot 間隔：{SNAPSHOT_STRIDE} 天 × {SNAPSHOT_COUNT} 次",
        "",
        "> 注意：本回測**只計算價格報酬**，不含現金股利再投入。實際長期持有總報酬會略高於本表，",
        "> 但相對比較（vs 0050）仍公平 — 因為 0050 也用相同方式計算。",
        "",
        "## Per-Snapshot Results",
        "",
        "| Snapshot | oddlot 平均 | 0050 | 差距 | 持有天數 |",
        "|---|---|---|---|---|",
    ]

    for r in results:
        days = (HOLD_END - r["date"]).days
        if r["avg"] is None or r["benchmark"] is None:
            lines.append(f"| {r['date']} | — | — | — | {days} |")
            continue
        diff = r["avg"] - r["benchmark"]
        flag = "🟢" if diff > 0 else "🔴" if diff < 0 else "⚪"
        lines.append(
            f"| {r['date']} | {r['avg']*100:+.2f}% | {r['benchmark']*100:+.2f}% | "
            f"{flag} {diff*100:+.2f}% | {days} |"
        )

    valid = [r for r in results if r["avg"] is not None and r["benchmark"] is not None]
    if valid:
        avg_oddlot = sum(r["avg"] for r in valid) / len(valid)
        avg_bench  = sum(r["benchmark"] for r in valid) / len(valid)
        wins  = sum(1 for r in valid if r["avg"] > r["benchmark"])
        ties  = sum(1 for r in valid if abs(r["avg"] - r["benchmark"]) < 1e-9)
        lines += [
            "",
            f"## Aggregate ({len(valid)} 個有效 snapshot)",
            "",
            f"- **oddlot 平均報酬**：{avg_oddlot*100:+.2f}%",
            f"- **0050 平均報酬**：{avg_bench*100:+.2f}%",
            f"- **平均超額報酬**：{(avg_oddlot - avg_bench)*100:+.2f}%",
            f"- **勝率**：{wins}/{len(valid)} ({wins/len(valid)*100:.0f}%)" + (f"，平手 {ties} 次" if ties else ""),
        ]

    # Per-snapshot pick details
    lines += ["", "## 各 snapshot 詳細選股"]
    for r in results:
        lines += ["", f"### {r['date']} (持有 {(HOLD_END - r['date']).days} 天)"]
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
            ret_str = f"{ret*100:+.2f}%" if ret is not None else "—"
            cagr = p.get("price_cagr_3y")
            cagr_str = f"{cagr*100:+.1f}%" if cagr is not None else "—"
            lines.append(
                f"| {p['symbol']} | {p.get('name','?')} | {p.get('industry','?')} | "
                f"{p.get('yield_rate','?')}% | {cagr_str} | {ret_str} |"
            )

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[Backtest] Report written to {OUTPUT}")


if __name__ == "__main__":
    main()
