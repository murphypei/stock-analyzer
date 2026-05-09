"""Data models for standardized financial data."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IncomeStatement:
    """Standardized income statement (annual or quarterly)."""

    report_date: str
    total_revenue: float
    operating_cost: float
    gross_profit: float
    operating_profit: float
    net_income: float
    net_income_parent: float  # 归母净利润
    basic_eps: float
    rd_expense: float = 0.0
    sales_expense: float = 0.0
    admin_expense: float = 0.0
    financial_expense: float = 0.0
    asset_impairment: float = 0.0


@dataclass
class BalanceSheet:
    """Standardized balance sheet."""

    report_date: str
    total_assets: float
    total_liabilities: float
    total_equity: float
    total_equity_parent: float  # 归母权益
    inventory: float
    accounts_receivable: float
    accounts_payable: float
    short_term_loans: float
    long_term_loans: float
    bonds_payable: float
    long_term_payables: float
    cash_and_equivalents: float
    goodwill: float = 0.0
    fixed_assets: float = 0.0
    construction_in_progress: float = 0.0
    intangible_assets: float = 0.0


@dataclass
class CashFlowStatement:
    """Standardized cash flow statement."""

    report_date: str
    operating_cash_flow: float
    investing_cash_flow: float
    financing_cash_flow: float
    capex: float  # 购建固定资产等支付的现金
    free_cash_flow: float | None = None  # 计算得出
    dividend_paid: float = 0.0


@dataclass
class StockInfo:
    """Basic stock metadata."""

    ts_code: str  # Tushare code, e.g. 600519.SH
    name: str
    industry: str
    list_date: str
    total_mv: float | None = None  # 总市值
    circ_mv: float | None = None  # 流通市值


@dataclass
class FinancialIndicators:
    """Calculated financial indicators aligned with the strategy guide."""

    report_date: str

    # Profitability
    roe: float | None = None
    roa: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None

    # Cashflow quality
    ocf_to_netincome: float | None = None
    fcf: float | None = None
    dividend_to_fcf: float | None = None

    # Leverage & safety
    debt_ratio: float | None = None
    interest_bearing_debt_ratio: float | None = None
    current_ratio: float | None = None
    interest_coverage: float | None = None

    # Operational efficiency
    inventory_turnover: float | None = None
    receivable_turnover_days: float | None = None
    inventory_to_revenue: float | None = None

    # Valuation (requires market data)
    pe_ttm: float | None = None
    pb: float | None = None


@dataclass
class FinancialData:
    """Complete financial dataset for a single stock."""

    stock_info: StockInfo
    income_statements: list[IncomeStatement] = field(default_factory=list)
    balance_sheets: list[BalanceSheet] = field(default_factory=list)
    cash_flows: list[CashFlowStatement] = field(default_factory=list)
    indicators: list[FinancialIndicators] = field(default_factory=list)
