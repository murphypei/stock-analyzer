"""Tests for Phase 2 analysis modules."""

from src.analysis.mine_sweeper import sweep
from src.analysis.screening import red_line_check, veto_check
from src.analysis.warnings import analyze
from src.models.financial import (
    BalanceSheet,
    CashFlowStatement,
    FinancialData,
    FinancialIndicators,
    IncomeStatement,
    StockInfo,
)


def _make_data(
    roe: float = 0.15,
    debt_ratio: float = 0.40,
    ocf_neg: bool = False,
    profit_history: list[float] | None = None,
) -> FinancialData:
    """Build minimal FinancialData for testing."""
    profit_history = profit_history or [100, 110, 120, 130, 140, 150]
    incomes = []
    balances = []
    cashflows = []
    for i, p in enumerate(profit_history):
        date = f"202{i + 1}1231"
        eq = p / roe if roe else 1000
        incomes.append(
            IncomeStatement(
                report_date=date,
                total_revenue=p * 2,
                operating_cost=p,
                gross_profit=p,
                operating_profit=p * 0.8,
                net_income=p,
                net_income_parent=p,
                basic_eps=1.0,
            )
        )
        assets = eq / (1 - debt_ratio) if debt_ratio < 1 else 2000
        # Ensure interest-bearing debt ratio is proportional to total debt ratio
        # so that high total debt also means high interest-bearing debt.
        ib_debt = assets * debt_ratio * 0.9  # 90% of total debt is interest-bearing
        st_loan = ib_debt * 0.3
        lt_loan = ib_debt * 0.6
        bonds = ib_debt * 0.1
        balances.append(
            BalanceSheet(
                report_date=date,
                total_assets=assets,
                total_liabilities=assets * debt_ratio,
                total_equity=eq,
                total_equity_parent=eq,
                inventory=50,
                accounts_receivable=30,
                accounts_payable=20,
                short_term_loans=st_loan,
                long_term_loans=lt_loan,
                bonds_payable=bonds,
                long_term_payables=0,
                cash_and_equivalents=500,
            )
        )
        cashflows.append(
            CashFlowStatement(
                report_date=date,
                operating_cash_flow=-50 if ocf_neg else p * 0.9,
                investing_cash_flow=-20,
                financing_cash_flow=-10,
                capex=20,
            )
        )

    return FinancialData(
        stock_info=StockInfo(ts_code="000001.SZ", name="Test", industry="", list_date=""),
        income_statements=incomes,
        balance_sheets=balances,
        cash_flows=cashflows,
    )


def test_mine_sweeper_passes():
    data = _make_data(roe=0.15, debt_ratio=0.40)
    result = sweep(data, latest_pe=20)
    assert result.passed
    assert not result.pure_pb_trap
    assert not result.double_low_trap


def test_mine_sweeper_pb_trap():
    data = _make_data(roe=0.05, debt_ratio=0.40)
    result = sweep(data, latest_pe=5)
    assert not result.passed
    assert result.pure_pb_trap
    assert result.double_low_trap


def test_mine_sweeper_high_leverage():
    data = _make_data(roe=0.15, debt_ratio=0.70)
    result = sweep(data, latest_pe=20)
    assert not result.passed
    assert result.step4_high_leverage


def test_veto_passes():
    data = _make_data(roe=0.15, debt_ratio=0.40)
    indicators = [
        FinancialIndicators(
            report_date="20231231", roe=0.15, gross_margin=0.30, ocf_to_netincome=0.90
        )
    ]
    result = veto_check(data, indicators)
    assert result.passed


def test_veto_high_leverage():
    data = _make_data(roe=0.15, debt_ratio=0.70)
    indicators = [FinancialIndicators(report_date="20231231")]
    result = veto_check(data, indicators)
    assert not result.passed
    assert any("有息负债率" in v for v in result.vetoes)


def test_red_line_roe():
    indicators = [
        FinancialIndicators(
            report_date="20231231", roe=0.08, gross_margin=0.20, ocf_to_netincome=0.80
        )
    ]
    result = red_line_check(indicators)
    assert not result.passed
    assert any("ROE" in b for b in result.breaches)


def test_red_line_gm():
    indicators = [
        FinancialIndicators(
            report_date="20231231", roe=0.15, gross_margin=0.10, ocf_to_netincome=0.80
        )
    ]
    result = red_line_check(indicators)
    assert not result.passed
    assert any("毛利率" in b for b in result.breaches)


def test_warnings_neutral():
    data = _make_data(profit_history=[100, 120, 140])
    result = analyze(data)
    assert result.cycle_phase == "中性" or result.cycle_phase == "复苏上行"


def test_warnings_peak():
    data = _make_data(profit_history=[100, 120, 150])
    # Manually boost capex to trigger peak signal
    data.cash_flows[-1].capex = 100
    data.cash_flows[-2].capex = 20
    result = analyze(data)
    assert result.cycle_phase == "繁荣/顶峰"
    assert "卖出" in result.action
