"""Sina direct API adapter — lightweight alternative to AKShare."""

from __future__ import annotations

import requests

from src.cache.sqlite_cache import SQLiteCache
from src.data_sources.base import DataSource
from src.models.financial import (
    BalanceSheet,
    CashFlowStatement,
    FinancialIndicators,
    IncomeStatement,
    StockInfo,
)

_SINA_REPORT_URL = (
    "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
)
_SINA_SYMBOL_MAP = {"资产负债表": "fzb", "利润表": "lrb", "现金流量表": "llb"}


class SinaSource(DataSource):
    """Direct Sina finance API adapter.

    Fetches raw financial statements without the heavy AKShare dependency.
    """

    name = "sina"

    def __init__(self, cache: SQLiteCache | None = None) -> None:
        self._cache = cache

    def connect(self) -> bool:
        # Stateless; verify endpoint responds with a lightweight probe.
        try:
            r = requests.get(
                _SINA_REPORT_URL,
                params={
                    "paperCode": "600519",
                    "source": "lrb",
                    "type": "0",
                    "page": "1",
                    "num": "1",
                },
                timeout=10,
            )
            return r.status_code == 200 and "result" in r.json()
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

    @staticmethod
    def _to_symbol(ts_code: str) -> str:
        return ts_code.split(".")[0]

    def _fetch_report(self, symbol: str, report_type: str) -> dict:
        """Raw Sina API call returning parsed JSON."""
        r = requests.get(
            _SINA_REPORT_URL,
            params={
                "paperCode": symbol,
                "source": _SINA_SYMBOL_MAP[report_type],
                "type": "0",
                "page": "1",
                "num": "100",
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["result"]["data"]

    def get_stock_info(self, ts_code: str) -> StockInfo | None:
        # Sina does not expose stock metadata in this API; rely on other sources.
        return None

    def get_income_statements(self, ts_code: str, years: int = 10) -> list[IncomeStatement]:
        cached = self._cached("get_income_statements", ts_code)
        if cached is not None:
            return [IncomeStatement(**c) for c in cached]

        symbol = self._to_symbol(ts_code)
        try:
            data = self._fetch_report(symbol, "利润表")
            results = self._parse_income(data, years)
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
            data = self._fetch_report(symbol, "资产负债表")
            results = self._parse_balance(data, years)
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
            data = self._fetch_report(symbol, "现金流量表")
            results = self._parse_cashflow(data, years)
            self._store("get_cash_flows", ts_code, [r.__dict__ for r in results])
            return results
        except Exception:
            return []

    def get_daily_basic(self, ts_code: str, trade_date: str) -> FinancialIndicators | None:
        return None

    # ------------------------------------------------------------------ #
    # Parsers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_items(data: dict, date: str) -> dict[str, float]:
        items = data["report_list"][date]["data"]
        return {item["item_title"]: float(item["item_value"]) for item in items}

    def _parse_income(self, data: dict, years: int) -> list[IncomeStatement]:
        dates = [d["date_value"] for d in data["report_date"]][:years]
        results = []
        for date in dates:
            items = self._extract_items(data, date)
            results.append(
                IncomeStatement(
                    report_date=date,
                    total_revenue=items.get("营业总收入", items.get("营业收入", 0.0)),
                    operating_cost=items.get("营业成本", items.get("营业支出", 0.0)),
                    gross_profit=items.get("营业总收入", items.get("营业收入", 0.0))
                    - items.get("营业成本", items.get("营业支出", 0.0)),
                    operating_profit=items.get("营业利润", 0.0),
                    net_income=items.get("净利润", 0.0),
                    net_income_parent=items.get(
                        "归属于母公司所有者的净利润",
                        items.get("归属于母公司股东的净利润", items.get("净利润", 0.0)),
                    ),
                    basic_eps=0.0,
                    rd_expense=items.get("研发费用", 0.0),
                    sales_expense=items.get("销售费用", 0.0),
                    admin_expense=items.get("管理费用", 0.0),
                    financial_expense=items.get("财务费用", 0.0),
                    asset_impairment=items.get("资产减值损失", 0.0),
                )
            )
        return results

    def _parse_balance(self, data: dict, years: int) -> list[BalanceSheet]:
        dates = [d["date_value"] for d in data["report_date"]][:years]
        results = []
        for date in dates:
            items = self._extract_items(data, date)
            results.append(
                BalanceSheet(
                    report_date=date,
                    total_assets=items.get("资产总计", 0.0),
                    total_liabilities=items.get("负债合计", 0.0),
                    total_equity=items.get(
                        "所有者权益(或股东权益)合计",
                        items.get("所有者权益合计", 0.0),
                    ),
                    total_equity_parent=items.get(
                        "归属于母公司股东权益合计",
                        items.get(
                            "归属于母公司的股东权益合计",
                            items.get("归属于母公司股东的权益", 0.0),
                        ),
                    ),
                    inventory=items.get("存货", 0.0),
                    accounts_receivable=items.get("应收账款", 0.0),
                    accounts_payable=items.get("应付账款", 0.0),
                    short_term_loans=items.get("短期借款", 0.0),
                    long_term_loans=items.get("长期借款", 0.0),
                    bonds_payable=items.get("应付债券", 0.0),
                    long_term_payables=items.get("长期应付款", 0.0),
                    cash_and_equivalents=items.get("货币资金", 0.0),
                    goodwill=items.get("商誉", 0.0),
                    fixed_assets=items.get("固定资产", 0.0),
                    construction_in_progress=items.get("在建工程", 0.0),
                    intangible_assets=items.get("无形资产", 0.0),
                )
            )
        return results

    def _parse_cashflow(self, data: dict, years: int) -> list[CashFlowStatement]:
        dates = [d["date_value"] for d in data["report_date"]][:years]
        results = []
        for date in dates:
            items = self._extract_items(data, date)
            results.append(
                CashFlowStatement(
                    report_date=date,
                    operating_cash_flow=items.get("经营活动产生的现金流量净额", 0.0),
                    investing_cash_flow=items.get("投资活动产生的现金流量净额", 0.0),
                    financing_cash_flow=items.get("筹资活动产生的现金流量净额", 0.0),
                    capex=items.get("购建固定资产、无形资产和其他长期资产支付的现金", 0.0),
                    dividend_paid=items.get("分配股利、利润或偿付利息支付的现金", 0.0),
                )
            )
        return results
