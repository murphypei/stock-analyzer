"""Calculate financial indicators from raw statements."""

from __future__ import annotations

from src.models.financial import (
    BalanceSheet,
    CashFlowStatement,
    FinancialData,
    FinancialIndicators,
    IncomeStatement,
)


def calc_indicators(data: FinancialData) -> list[FinancialIndicators]:
    """Compute indicators for each reporting period where all three statements exist."""
    results: list[FinancialIndicators] = []

    # Index by report_date for alignment
    income_map: dict[str, IncomeStatement] = {i.report_date: i for i in data.income_statements}
    balance_map: dict[str, BalanceSheet] = {b.report_date: b for b in data.balance_sheets}
    cash_map: dict[str, CashFlowStatement] = {c.report_date: c for c in data.cash_flows}

    common_dates = sorted(
        set(income_map) & set(balance_map) & set(cash_map),
        reverse=True,
    )

    for date in common_dates:
        inc = income_map[date]
        bal = balance_map[date]
        cf = cash_map[date]
        results.append(_calc_single(inc, bal, cf))

    return results


def _calc_single(
    inc: IncomeStatement, bal: BalanceSheet, cf: CashFlowStatement
) -> FinancialIndicators:
    """Calculate all indicators for a single period."""
    # Profitability
    roe = _safe_div(inc.net_income_parent, bal.total_equity_parent)
    roa = _safe_div(inc.net_income, bal.total_assets)
    gross_margin = _safe_div(inc.gross_profit, inc.total_revenue)
    net_margin = _safe_div(inc.net_income, inc.total_revenue)

    # Cashflow quality
    ocf_to_netincome = _safe_div(cf.operating_cash_flow, inc.net_income)
    fcf = cf.operating_cash_flow - cf.capex
    dividend_to_fcf = _safe_div(cf.dividend_paid, fcf) if fcf and fcf > 0 else None

    # Leverage & safety
    debt_ratio = _safe_div(bal.total_liabilities, bal.total_assets)
    interest_debt = bal.short_term_loans + bal.long_term_loans + bal.bonds_payable
    interest_bearing_debt_ratio = _safe_div(interest_debt, bal.total_assets)

    # Current ratio approximation
    current_assets = bal.cash_and_equivalents + bal.accounts_receivable + bal.inventory
    current_liabilities = bal.accounts_payable + bal.short_term_loans
    current_ratio = _safe_div(current_assets, current_liabilities) if current_liabilities else None

    # Interest coverage (using financial expense as proxy for interest)
    interest_coverage = (
        _safe_div(inc.operating_profit, inc.financial_expense) if inc.financial_expense else None
    )

    # Operational efficiency
    cogs = inc.operating_cost if inc.operating_cost else inc.total_revenue - inc.gross_profit
    inventory_turnover = _safe_div(cogs, bal.inventory)
    receivable_turnover_days = (
        _safe_div(bal.accounts_receivable, inc.total_revenue) * 365 if inc.total_revenue else None
    )
    inventory_to_revenue = _safe_div(bal.inventory, inc.total_revenue)

    return FinancialIndicators(
        report_date=inc.report_date,
        roe=roe,
        roa=roa,
        gross_margin=gross_margin,
        net_margin=net_margin,
        ocf_to_netincome=ocf_to_netincome,
        fcf=fcf,
        dividend_to_fcf=dividend_to_fcf,
        debt_ratio=debt_ratio,
        interest_bearing_debt_ratio=interest_bearing_debt_ratio,
        current_ratio=current_ratio,
        interest_coverage=interest_coverage,
        inventory_turnover=inventory_turnover,
        receivable_turnover_days=receivable_turnover_days,
        inventory_to_revenue=inventory_to_revenue,
    )


def _safe_div(a: float, b: float) -> float | None:
    if b == 0 or a is None or b is None:
        return None
    return a / b
