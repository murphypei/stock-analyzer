"""Validation script: fetch sample stocks and run full Phase 1+2 pipeline."""

from __future__ import annotations

from src.analysis.mine_sweeper import sweep
from src.analysis.scoring import score
from src.analysis.screening import red_line_check, veto_check
from src.analysis.warnings import analyze
from src.data_sources.adapter import DataSourceAdapter
from src.indicators.calculator import calc_indicators

SAMPLE_STOCKS = [
    ("600519.SH", "贵州茅台"),
    ("601318.SH", "中国平安"),
    ("000001.SZ", "平安银行"),
]


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

        print(f"  Name: {data.stock_info.name}")
        print(f"  Industry: {data.stock_info.industry}")
        print(f"  Periods fetched: {len(data.income_statements)}")

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


def fmt(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


if __name__ == "__main__":
    main()
