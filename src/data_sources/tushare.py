"""Tushare data source adapter (primary)."""

import pandas as pd
import tushare as ts

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


class TushareSource(DataSource):
    """Tushare Pro API adapter."""

    name = "tushare"

    def __init__(self, token: str | None = None, cache: SQLiteCache | None = None) -> None:
        self.token = token or Config.TUSHARE_TOKEN
        self.pro: ts.pro_api | None = None
        self._cache = cache

    def connect(self) -> bool:
        if not self.token:
            return False
        try:
            self.pro = ts.pro_api(self.token)
            return True
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

        if self.pro is None:
            return None
        try:
            df: pd.DataFrame = self.pro.stock_basic(
                ts_code=ts_code,
                fields="ts_code,name,industry,list_date",
            )
            if df.empty:
                return None
            row = df.iloc[0]
            info = StockInfo(
                ts_code=row["ts_code"],
                name=row["name"],
                industry=row["industry"] or "",
                list_date=row["list_date"] or "",
            )
            self._store("get_stock_info", ts_code, info.__dict__)
            return info
        except Exception:
            return None

    def get_income_statements(self, ts_code: str, years: int = 10) -> list[IncomeStatement]:
        cached = self._cached("get_income_statements", ts_code)
        if cached is not None:
            return [IncomeStatement(**c) for c in cached]

        if self.pro is None:
            return []
        try:
            df: pd.DataFrame = self.pro.income(
                ts_code=ts_code,
                period="",
                fields="end_date,total_revenue,operate_cost,gross_profit,operate_profit,"
                "n_income,n_income_attr_p,eps,basic_eps,rd_expense,sell_exp,"
                "admin_exp,fin_exp_exp,impairment_loss_assets",
            )
            if df.empty:
                return []
            df = df.sort_values("end_date", ascending=False).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    IncomeStatement(
                        report_date=str(row["end_date"]),
                        total_revenue=self._f(row, "total_revenue"),
                        operating_cost=self._f(row, "operate_cost"),
                        gross_profit=self._f(row, "gross_profit"),
                        operating_profit=self._f(row, "operate_profit"),
                        net_income=self._f(row, "n_income"),
                        net_income_parent=self._f(row, "n_income_attr_p"),
                        basic_eps=self._f(row, "basic_eps"),
                        rd_expense=self._f(row, "rd_expense"),
                        sales_expense=self._f(row, "sell_exp"),
                        admin_expense=self._f(row, "admin_exp"),
                        financial_expense=self._f(row, "fin_exp_exp"),
                        asset_impairment=self._f(row, "impairment_loss_assets"),
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

        if self.pro is None:
            return []
        try:
            df: pd.DataFrame = self.pro.balancesheet(
                ts_code=ts_code,
                period="",
                fields="end_date,total_assets,total_liab,total_hldr_eqy_exc_min_int,"
                "total_hldr_eqy,inventories,accounts_receiv,acct_payable,"
                "st_borr,lt_borr,bond_payable,lt_payable,cash_cash_eq_bal,"
                "goodwill,fix_assets,const_in_prog,intan_assets",
            )
            if df.empty:
                return []
            df = df.sort_values("end_date", ascending=False).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    BalanceSheet(
                        report_date=str(row["end_date"]),
                        total_assets=self._f(row, "total_assets"),
                        total_liabilities=self._f(row, "total_liab"),
                        total_equity=self._f(row, "total_hldr_eqy_exc_min_int", 0),
                        total_equity_parent=self._f(row, "total_hldr_eqy"),
                        inventory=self._f(row, "inventories"),
                        accounts_receivable=self._f(row, "accounts_receiv"),
                        accounts_payable=self._f(row, "acct_payable"),
                        short_term_loans=self._f(row, "st_borr"),
                        long_term_loans=self._f(row, "lt_borr"),
                        bonds_payable=self._f(row, "bond_payable"),
                        long_term_payables=self._f(row, "lt_payable"),
                        cash_and_equivalents=self._f(row, "cash_cash_eq_bal"),
                        goodwill=self._f(row, "goodwill"),
                        fixed_assets=self._f(row, "fix_assets"),
                        construction_in_progress=self._f(row, "const_in_prog"),
                        intangible_assets=self._f(row, "intan_assets"),
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

        if self.pro is None:
            return []
        try:
            df: pd.DataFrame = self.pro.cashflow(
                ts_code=ts_code,
                period="",
                fields="end_date,n_cashflow_act,n_cashflow_inv_act,"
                "n_cash_flows_fnc_act,c_pay_acq_const_fiolta,"
                "dividend_cash_paid",
            )
            if df.empty:
                return []
            df = df.sort_values("end_date", ascending=False).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    CashFlowStatement(
                        report_date=str(row["end_date"]),
                        operating_cash_flow=self._f(row, "n_cashflow_act"),
                        investing_cash_flow=self._f(row, "n_cashflow_inv_act"),
                        financing_cash_flow=self._f(row, "n_cash_flows_fnc_act"),
                        capex=self._f(row, "c_pay_acq_const_fiolta"),
                        dividend_paid=self._f(row, "dividend_cash_paid"),
                    )
                )
            self._store("get_cash_flows", ts_code, [r.__dict__ for r in results])
            return results
        except Exception:
            return []

    def get_daily_basic(self, ts_code: str, trade_date: str) -> FinancialIndicators | None:
        cached = self._cached("get_daily_basic", ts_code, period=trade_date)
        if cached is not None:
            return FinancialIndicators(**cached)

        if self.pro is None:
            return None
        try:
            df: pd.DataFrame = self.pro.daily_basic(
                ts_code=ts_code,
                trade_date=trade_date,
                fields="trade_date,pe_ttm,pb",
            )
            if df.empty:
                return None
            row = df.iloc[0]
            indicators = FinancialIndicators(
                report_date=str(row["trade_date"]),
                pe_ttm=self._f(row, "pe_ttm"),
                pb=self._f(row, "pb"),
            )
            self._store("get_daily_basic", ts_code, indicators.__dict__, period=trade_date)
            return indicators
        except Exception:
            return None

    @staticmethod
    def _f(row: pd.Series, col: str, default: float = 0.0) -> float:
        v = row.get(col)
        if pd.isna(v):
            return default
        return float(v)
