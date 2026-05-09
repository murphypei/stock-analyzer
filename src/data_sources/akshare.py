"""AKShare data source adapter (fallback)."""

from __future__ import annotations

import akshare as ak
import pandas as pd

from src.cache.sqlite_cache import SQLiteCache
from src.data_sources.base import DataSource
from src.models.financial import (
    BalanceSheet,
    CashFlowStatement,
    FinancialIndicators,
    IncomeStatement,
    StockInfo,
)


class AkshareSource(DataSource):
    """AKShare adapter using Sina financial reports."""

    name = "akshare"

    def __init__(self, cache: SQLiteCache | None = None) -> None:
        self._cache = cache

    def connect(self) -> bool:
        # AKShare is stateless; assume available if import succeeded.
        return True

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

    def _to_symbol(self, ts_code: str) -> str:
        """Convert 600519.SH -> 600519."""
        return ts_code.split(".")[0]

    def get_stock_info(self, ts_code: str) -> StockInfo | None:
        cached = self._cached("get_stock_info", ts_code)
        if cached is not None:
            return StockInfo(**cached)

        symbol = self._to_symbol(ts_code)
        try:
            df = ak.stock_individual_info_em(symbol=symbol)
            if df.empty:
                return None
            info_map = dict(zip(df["item"], df["value"], strict=False))
            info = StockInfo(
                ts_code=ts_code,
                name=str(info_map.get("股票简称", "")),
                industry=str(info_map.get("行业", "")),
                list_date=str(info_map.get("上市时间", "")),
                total_mv=_to_float(info_map.get("总市值")),
                circ_mv=_to_float(info_map.get("流通市值")),
            )
            self._store("get_stock_info", ts_code, info.__dict__)
            return info
        except Exception:
            return None

    def get_income_statements(self, ts_code: str, years: int = 10) -> list[IncomeStatement]:
        cached = self._cached("get_income_statements", ts_code)
        if cached is not None:
            return [IncomeStatement(**c) for c in cached]

        symbol = self._to_symbol(ts_code)
        try:
            df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
            if df.empty:
                return []
            df = self._clean_sina_df(df).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    IncomeStatement(
                        report_date=str(row["报告日"]),
                        total_revenue=self._f_any(row, "营业总收入", "营业收入"),
                        operating_cost=self._f_any(row, "营业成本", "营业支出"),
                        gross_profit=self._f_any(row, "营业总收入", "营业收入")
                        - self._f_any(row, "营业成本", "营业支出"),
                        operating_profit=self._f(row, "营业利润"),
                        net_income=self._f(row, "净利润"),
                        net_income_parent=self._f_any(
                            row, "归属于母公司所有者的净利润", "归属于母公司股东的净利润", "净利润"
                        ),
                        basic_eps=0.0,
                        rd_expense=self._f(row, "研发费用"),
                        sales_expense=self._f(row, "销售费用"),
                        admin_expense=self._f(row, "管理费用"),
                        financial_expense=self._f(row, "财务费用"),
                        asset_impairment=self._f(row, "资产减值损失"),
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

        symbol = self._to_symbol(ts_code)
        try:
            df = ak.stock_financial_report_sina(stock=symbol, symbol="资产负债表")
            if df.empty:
                return []
            df = self._clean_sina_df(df).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    BalanceSheet(
                        report_date=str(row["报告日"]),
                        total_assets=self._f(row, "资产总计"),
                        total_liabilities=self._f(row, "负债合计"),
                        total_equity=self._f_any(
                            row, "所有者权益(或股东权益)合计", "所有者权益合计", default=0.0
                        ),
                        total_equity_parent=self._f_any(
                            row,
                            "归属于母公司股东权益合计",
                            "归属于母公司的股东权益合计",
                            "归属于母公司股东的权益",
                            default=0.0,
                        ),
                        inventory=self._f(row, "存货"),
                        accounts_receivable=self._f(row, "应收账款"),
                        accounts_payable=self._f(row, "应付账款"),
                        short_term_loans=self._f(row, "短期借款"),
                        long_term_loans=self._f(row, "长期借款"),
                        bonds_payable=self._f(row, "应付债券"),
                        long_term_payables=self._f(row, "长期应付款"),
                        cash_and_equivalents=self._f(row, "货币资金"),
                        goodwill=self._f(row, "商誉"),
                        fixed_assets=self._f(row, "固定资产"),
                        construction_in_progress=self._f(row, "在建工程"),
                        intangible_assets=self._f(row, "无形资产"),
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

        symbol = self._to_symbol(ts_code)
        try:
            df = ak.stock_financial_report_sina(stock=symbol, symbol="现金流量表")
            if df.empty:
                return []
            df = self._clean_sina_df(df).head(years)
            results = []
            for _, row in df.iterrows():
                results.append(
                    CashFlowStatement(
                        report_date=str(row["报告日"]),
                        operating_cash_flow=self._f(row, "经营活动产生的现金流量净额"),
                        investing_cash_flow=self._f(row, "投资活动产生的现金流量净额"),
                        financing_cash_flow=self._f(row, "筹资活动产生的现金流量净额"),
                        capex=self._f(row, "购建固定资产、无形资产和其他长期资产支付的现金"),
                        dividend_paid=self._f(row, "分配股利、利润或偿付利息支付的现金"),
                    )
                )
            self._store("get_cash_flows", ts_code, [r.__dict__ for r in results])
            return results
        except Exception:
            return []

    def get_daily_basic(self, ts_code: str, trade_date: str) -> FinancialIndicators | None:
        # AKShare free tier does not reliably expose daily valuation snapshots.
        return None

    @staticmethod
    def _clean_sina_df(df: pd.DataFrame) -> pd.DataFrame:
        """Sina reports come with extra metadata columns; keep numeric rows only."""
        # Drop rows where 报告日 is not a valid date-like string
        df = df[df["报告日"].astype(str).str.match(r"\d{8}")].copy()
        df["报告日"] = df["报告日"].astype(str)
        # Sort descending by date
        return df.sort_values("报告日", ascending=False)

    @staticmethod
    def _f(row: pd.Series, col: str, default: float = 0.0) -> float:
        v = row.get(col)
        if pd.isna(v):
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _f_any(row: pd.Series, *cols: str, default: float = 0.0) -> float:
        for col in cols:
            v = row.get(col)
            if not pd.isna(v):
                try:
                    return float(v)
                except (ValueError, TypeError):
                    continue
        return default


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
