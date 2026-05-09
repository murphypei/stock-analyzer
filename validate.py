"""Validation script: fetch sample stocks and print key indicators."""

from __future__ import annotations

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


def fmt(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


if __name__ == "__main__":
    main()
