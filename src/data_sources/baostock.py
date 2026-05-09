"""Baostock data source adapter (fallback)."""

import baostock as bs
import pandas as pd

from src.cache.sqlite_cache import SQLiteCache
from src.config import Config
from src.data_sources.base import DataSource
from src.models.financial import (
    BalanceSheet,
    CashFlowStatement,
    FinancialIndicators,
    IncomeStatement,
    StockInfo,
)


class BaostockSource(DataSource):
    """Baostock adapter. Note: Baostock uses code format like sh.600519."""

    name = "baostock"

    def __init__(
        self,
        user: str | None = None,
        password: str | None = None,
        cache: SQLiteCache | None = None,
    ) -> None:
        self.user = user or Config.BAOSTOCK_USER
        self.password = password or Config.BAOSTOCK_PASSWORD
        self._cache = cache
        self._logged_in = False

    def _to_bs_code(self, ts_code: str) -> str:
        """Convert 600519.SH -> sh.600519."""
        code, exch = ts_code.split(".")
        return f"{exch.lower()}.{code}"

    def connect(self) -> bool:
        # Baostock default login does not require credentials.
        try:
            rs = bs.login()
            self._logged_in = rs.error_code == "0"
            return self._logged_in
        except Exception:
            return False

    def _cached(self, method: str, ts_code: str, **kwargs):
        if self._cache is None:
            return None
        period = kwargs.get("period", "")
        return self._cache.get(self.name, ts_code, method, period)

    def _store(self, method: str, ts_code: str, data, **kwargs):
        if self._cache is None:
            return
        period = kwargs.get("period", "")
        self._cache.set(self.name, ts_code, method, period, data)

    def get_stock_info(self, ts_code: str) -> StockInfo | None:
        cached = self._cached("get_stock_info", ts_code)
        if cached is not None:
            return StockInfo(**cached)

        bs_code = self._to_bs_code(ts_code)
        try:
            rs = bs.query_stock_basic(code=bs_code)
            if rs.error_code != "0" or rs.next() is None:
                return None
            row = rs.get_row_data()
            info = StockInfo(
                ts_code=ts_code,
                name=row[1] if len(row) > 1 else "",
                industry="",
                list_date=row[2] if len(row) > 2 else "",
            )
            self._store("get_stock_info", ts_code, info.__dict__)
            return info
        except Exception:
            return None

    def get_income_statements(self, ts_code: str, years: int = 10) -> list[IncomeStatement]:
        cached = self._cached("get_income_statements", ts_code)
        if cached is not None:
            return [IncomeStatement(**c) for c in cached]

        bs_code = self._to_bs_code(ts_code)
        try:
            rs = bs.query_profit_data(code=bs_code, year="", quarter="")
            data_list = []
            while (rs.error_code == "0") and rs.next():
                data_list.append(rs.get_row_data())
            if not data_list:
                return []
            df = pd.DataFrame(data_list, columns=rs.fields)
            # Baostock returns string values; coerce to numeric
            numeric_cols = [
                "total_profit",
                "net_profit",
                "operating_revenue",
                "operating_cost",
                "gross_profit",
                "operating_profit",
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.sort_values("statDate", ascending=False).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    IncomeStatement(
                        report_date=str(row["statDate"]),
                        total_revenue=self._f(row, "operating_revenue"),
                        operating_cost=self._f(row, "operating_cost"),
                        gross_profit=self._f(row, "gross_profit"),
                        operating_profit=self._f(row, "operating_profit"),
                        net_income=self._f(row, "total_profit"),
                        net_income_parent=self._f(row, "net_profit"),
                        basic_eps=0.0,
                    )
                )
            self._store("get_income_statements", ts_code, [r.__dict__ for r in results])
            return results
        except Exception:
            return []

    def get_balance_sheets(self, ts_code: str, years: int = 10) -> list[BalanceSheet]:
        cached = self._cached("get_balance_sheets", ts_code)
        if cached is not None:
            return [BalanceSheet(**c) for c in cached]

        bs_code = self._to_bs_code(ts_code)
        try:
            rs = bs.query_balance_data(code=bs_code, year="", quarter="")
            data_list = []
            while (rs.error_code == "0") and rs.next():
                data_list.append(rs.get_row_data())
            if not data_list:
                return []
            df = pd.DataFrame(data_list, columns=rs.fields)
            numeric_cols = [
                "total_assets",
                "total_liabilities",
                "total_equity",
                "inventory",
                "accounts_receivable",
                "cash",
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.sort_values("statDate", ascending=False).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    BalanceSheet(
                        report_date=str(row["statDate"]),
                        total_assets=self._f(row, "total_assets"),
                        total_liabilities=self._f(row, "total_liabilities"),
                        total_equity=self._f(row, "total_equity"),
                        total_equity_parent=self._f(row, "total_equity"),
                        inventory=self._f(row, "inventory"),
                        accounts_receivable=self._f(row, "accounts_receivable"),
                        accounts_payable=0.0,
                        short_term_loans=0.0,
                        long_term_loans=0.0,
                        bonds_payable=0.0,
                        long_term_payables=0.0,
                        cash_and_equivalents=self._f(row, "cash"),
                    )
                )
            self._store("get_balance_sheets", ts_code, [r.__dict__ for r in results])
            return results
        except Exception:
            return []

    def get_cash_flows(self, ts_code: str, years: int = 10) -> list[CashFlowStatement]:
        cached = self._cached("get_cash_flows", ts_code)
        if cached is not None:
            return [CashFlowStatement(**c) for c in cached]

        bs_code = self._to_bs_code(ts_code)
        try:
            rs = bs.query_cash_flow_data(code=bs_code, year="", quarter="")
            data_list = []
            while (rs.error_code == "0") and rs.next():
                data_list.append(rs.get_row_data())
            if not data_list:
                return []
            df = pd.DataFrame(data_list, columns=rs.fields)
            numeric_cols = [
                "net_operate_cash_flow",
                "net_invest_cash_flow",
                "net_finance_cash_flow",
                "capex",
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.sort_values("statDate", ascending=False).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    CashFlowStatement(
                        report_date=str(row["statDate"]),
                        operating_cash_flow=self._f(row, "net_operate_cash_flow"),
                        investing_cash_flow=self._f(row, "net_invest_cash_flow"),
                        financing_cash_flow=self._f(row, "net_finance_cash_flow"),
                        capex=self._f(row, "capex"),
                    )
                )
            self._store("get_cash_flows", ts_code, [r.__dict__ for r in results])
            return results
        except Exception:
            return []

    def get_daily_basic(self, ts_code: str, trade_date: str) -> FinancialIndicators | None:
        # Baostock does not offer daily valuation metrics in the free tier reliably.
        return None

    @staticmethod
    def _f(row: pd.Series, col: str, default: float = 0.0) -> float:
        v = row.get(col)
        if pd.isna(v):
            return default
        return float(v)
