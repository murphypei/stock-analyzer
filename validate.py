"""Validation script: fetch sample stocks and run full Phase 1+2+3 pipeline."""

from __future__ import annotations

import requests

from src.analysis.elasticity import calculate as calc_elasticity
from src.analysis.mine_sweeper import sweep
from src.analysis.scoring import score
from src.analysis.screening import red_line_check, veto_check
from src.analysis.valuation import evaluate
from src.analysis.warnings import analyze
from src.data_sources.adapter import DataSourceAdapter
from src.indicators.calculator import calc_indicators

SAMPLE_STOCKS = [
    ("600519.SH", "贵州茅台"),
    ("601318.SH", "中国平安"),
    ("000001.SZ", "平安银行"),
]


def _fetch_market_cap(ts_code: str) -> float | None:
    """从腾讯财经获取实时总市值（元）。"""
    symbol = ts_code.split(".")[0]
    prefix = "sh" if ts_code.endswith(".SH") else "sz"
    try:
        r = requests.get(
            f"https://qt.gtimg.cn/q={prefix}{symbol}",
            timeout=10,
        )
        r.raise_for_status()
        # v_sh600519="1~名称~代码~...~总市值~..."
        text = r.text
        start = text.find('"')
        end = text.rfind('"')
        if start == -1 or end == -1 or start == end:
            return None
        fields = text[start + 1 : end].split("~")
        if len(fields) > 44:
            # 字段 44 为总市值，单位亿元
            return float(fields[44]) * 1e8
        return None
    except Exception:
        return None


def main() -> None:
    adapter = DataSourceAdapter()
    for ts_code, name in SAMPLE_STOCKS:
        print(f"\n{'=' * 60}")
        print(f"Stock: {ts_code} ({name})")
        print("=" * 60)

        data = adapter.fetch_full(ts_code, years=5)
        if not data.income_statements:
            print("  No data fetched.")
            continue

        data.indicators = calc_indicators(data)
        mcap = _fetch_market_cap(ts_code)

        print(f"  Name: {data.stock_info.name}")
        print(f"  Industry: {data.stock_info.industry}")
        print(f"  Periods fetched: {len(data.income_statements)}")
        if mcap:
            print(f"  Market Cap:     {mcap:,.0f}")

        print("\n  Key Indicators (latest period):")
        if data.indicators:
            latest = data.indicators[0]
            print(f"    ROE:            {fmt(latest.roe)}")
            print(f"    Gross Margin:   {fmt(latest.gross_margin)}")
            print(f"    OCF/NetIncome:  {fmt(latest.ocf_to_netincome)}")
            print(
                f"    FCF:            {latest.fcf:,.0f}"
                if latest.fcf
                else "    FCF:            N/A"
            )
            print(f"    Debt Ratio:     {fmt(latest.debt_ratio)}")
            print(f"    Current Ratio:  {fmt(latest.current_ratio)}")
        else:
            print("    No indicators calculated (missing statements).")

        # Phase 2: Mine Sweeper
        print("\n  [Phase 2] Mine Sweeper:")
        ms = sweep(data, latest_pe=None)
        print(f"    Passed: {ms.passed}")
        if ms.warnings:
            for w in ms.warnings:
                print(f"    ⚠️  {w}")
        if ms.pure_pb_trap:
            print("    🚨 Pure PB Trap")
        if ms.double_low_trap:
            print("    🚨 Double-Low Trap")
        if ms.cycle_top_low_pe_trap:
            print("    🚨 Cycle-Top Low-PE Trap")

        # Phase 2: Veto & Red Line
        print("\n  [Phase 2] Screening:")
        veto = veto_check(data, data.indicators)
        print(f"    Veto Passed: {veto.passed}")
        if veto.vetoes:
            for v in veto.vetoes:
                print(f"    ❌ {v}")

        red = red_line_check(data.indicators)
        print(f"    Red-Line Passed: {red.passed}")
        if red.breaches:
            for b in red.breaches:
                print(f"    🚫 {b}")

        # Phase 2: Scoring
        print("\n  [Phase 2] Ten-Dimension Scoring:")
        sc = score(data, data.indicators, overrides={})
        print(f"    Total: {sc.total_score:.1f} / {sc.max_possible:.1f}  Grade: {sc.grade}")
        print(f"    Passed (>=70): {sc.passed}")
        for dim in sc.dimensions:
            score_str = f"{dim.score:.1f}" if dim.score is not None else "N/A"
            print(f"    - {dim.name:12s} {score_str:>4s}/10  ({dim.note})")

        # Phase 2: Warning Signals
        print("\n  [Phase 2] Warning Signals:")
        ws = analyze(data)
        print(f"    Cycle Phase: {ws.cycle_phase}")
        print(f"    Action:      {ws.action}")
        for s in ws.signals:
            print(f"    📡 {s}")

        # Phase 3: Valuation
        if mcap:
            print("\n  [Phase 3] Valuation:")
            val = evaluate(data, current_market_cap=mcap, reasonable_pb=1.5)
            if val.current_pb:
                print(f"    Current PB:          {val.current_pb:.2f}")
            if val.pb_percentile is not None:
                print(f"    PB Percentile:       {val.pb_percentile:.1f}%")
            if val.cycle_adjusted_pe:
                print(f"    Cycle-Adjusted PE:   {val.cycle_adjusted_pe:.1f}")
            if val.avg_profit:
                print(f"    Avg Profit:          {val.avg_profit:,.0f}")
            if val.profit_cv is not None:
                print(f"    Profit CV:           {val.profit_cv:.2f}")
            if val.safety_margin is not None:
                direction = "undervalued" if val.safety_margin > 0 else "overvalued"
                print(f"    Safety Margin:       {val.safety_margin:+.1%} ({direction})")
            for n in val.notes:
                print(f"    ℹ️  {n}")

            # Phase 3: Profit Elasticity
            print("\n  [Phase 3] Profit Elasticity:")
            el = calc_elasticity(data, current_market_cap=mcap)
            if el.historical_elasticity:
                print(f"    Historical Elasticity: {el.historical_elasticity:.1f}x")
            for s in el.scenarios:
                print(
                    f"    {s.name:4s}  Profit={s.net_profit:>12,.0f}  "
                    f"PE={s.target_pe:.0f}  ImpliedCap={s.implied_market_cap:>15,.0f}  "
                    f"Upside={s.upside_pct:+.1f}%"
                )
            for n in el.notes:
                print(f"    ℹ️  {n}")


def fmt(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


if __name__ == "__main__":
    main()
