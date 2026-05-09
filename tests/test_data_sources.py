"""Simple tests for data sources and indicators."""

from src.cache.sqlite_cache import SQLiteCache
from src.indicators.calculator import calc_indicators
from src.models.financial import (
    BalanceSheet,
    CashFlowStatement,
    FinancialData,
    IncomeStatement,
    StockInfo,
)


def test_cache_roundtrip():
    cache = SQLiteCache()
    cache.set("test", "000001.SZ", "income", "2023", {"revenue": 100})
    assert cache.get("test", "000001.SZ", "income", "2023") == {"revenue": 100}


def test_calculator_basic():
    data = FinancialData(
        stock_info=StockInfo(ts_code="000001.SZ", name="Test", industry="", list_date=""),
        income_statements=[
            IncomeStatement(
                report_date="20231231",
                total_revenue=1000,
                operating_cost=600,
                gross_profit=400,
                operating_profit=200,
                net_income=150,
                net_income_parent=150,
                basic_eps=1.0,
            ),
        ],
        balance_sheets=[
            BalanceSheet(
                report_date="20231231",
                total_assets=2000,
                total_liabilities=800,
                total_equity=1200,
                total_equity_parent=1200,
                inventory=100,
                accounts_receivable=50,
                accounts_payable=30,
                short_term_loans=100,
                long_term_loans=200,
                bonds_payable=0,
                long_term_payables=0,
                cash_and_equivalents=500,
            ),
        ],
        cash_flows=[
            CashFlowStatement(
                report_date="20231231",
                operating_cash_flow=180,
                investing_cash_flow=-100,
                financing_cash_flow=-50,
                capex=80,
            ),
        ],
    )
    indicators = calc_indicators(data)
    assert len(indicators) == 1
    ind = indicators[0]
    assert ind.roe == 150 / 1200
    assert ind.gross_margin == 400 / 1000
    assert ind.ocf_to_netincome == 180 / 150
    assert ind.fcf == 180 - 80
