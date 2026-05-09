"""Unified adapter that orchestrates multiple data sources by priority."""

from __future__ import annotations

from src.cache.sqlite_cache import SQLiteCache
from src.data_sources.akshare import AkshareSource
from src.data_sources.baostock import BaostockSource
from src.data_sources.base import DataSource
from src.data_sources.sina import SinaSource
from src.data_sources.tushare import TushareSource
from src.models.financial import (
    FinancialData,
    StockInfo,
)


class DataSourceAdapter:
    """Tries sources in priority order: Tushare -> Baostock.

    Falls back to the next source when the primary returns empty or fails.
    """

    def __init__(self, cache: SQLiteCache | None = None) -> None:
        self._cache = cache or SQLiteCache()
        self._sources: list[DataSource] = []
        self._init_sources()

    def _init_sources(self) -> None:
        tushare = TushareSource(cache=self._cache)
        if tushare.connect():
            self._sources.append(tushare)

        sina = SinaSource(cache=self._cache)
        if sina.connect():
            self._sources.append(sina)

        baostock = BaostockSource(cache=self._cache)
        if baostock.connect():
            self._sources.append(baostock)

        akshare = AkshareSource(cache=self._cache)
        if akshare.connect():
            self._sources.append(akshare)

    def fetch_full(self, ts_code: str, years: int = 10) -> FinancialData:
        """Fetch complete financial data for a stock from the best available source."""
        info = self._first("get_stock_info", ts_code)
        if info is None:
            info = StockInfo(ts_code=ts_code, name="", industry="", list_date="")

        income = self._first("get_income_statements", ts_code, years=years)
        balance = self._first("get_balance_sheets", ts_code, years=years)
        cashflow = self._first("get_cash_flows", ts_code, years=years)

        return FinancialData(
            stock_info=info,
            income_statements=income or [],
            balance_sheets=balance or [],
            cash_flows=cashflow or [],
        )

    def _first(self, method: str, ts_code: str, **kwargs):
        """Try each source in order until one returns truthy data."""
        for src in self._sources:
            try:
                result = getattr(src, method)(ts_code, **kwargs)
                if result:
                    return result
            except Exception:
                continue
        return None
