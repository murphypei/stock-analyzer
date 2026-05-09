"""Abstract base class for data source adapters."""

from abc import ABC, abstractmethod

from src.models.financial import (
    BalanceSheet,
    CashFlowStatement,
    FinancialIndicators,
    IncomeStatement,
    StockInfo,
)


class DataSource(ABC):
    """Unified interface for all financial data sources."""

    name: str = ""

    @abstractmethod
    def connect(self) -> bool:
        """Initialize connection. Return True if successful."""
        ...

    @abstractmethod
    def get_stock_info(self, ts_code: str) -> StockInfo | None: ...

    @abstractmethod
    def get_income_statements(self, ts_code: str, years: int = 10) -> list[IncomeStatement]: ...

    @abstractmethod
    def get_balance_sheets(self, ts_code: str, years: int = 10) -> list[BalanceSheet]: ...

    @abstractmethod
    def get_cash_flows(self, ts_code: str, years: int = 10) -> list[CashFlowStatement]: ...

    @abstractmethod
    def get_daily_basic(self, ts_code: str, trade_date: str) -> FinancialIndicators | None:
        """Fetch valuation indicators (PE, PB, etc.) for a given trade date."""
        ...
