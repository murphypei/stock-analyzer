"""估值模型：PB 分位、周期调整 PE、安全边际。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.financial import FinancialData


@dataclass
class ValuationResult:
    """估值分析结果。"""

    current_pb: float | None = None
    pb_percentile: float | None = None  # 0-100
    cycle_adjusted_pe: float | None = None
    avg_profit: float | None = None
    profit_cv: float | None = None  # 利润变异系数
    intrinsic_value_pb: float | None = None
    safety_margin: float | None = None  # (内在价值 - 当前市值) / 当前市值
    notes: list[str] = field(default_factory=list)


def evaluate(
    data: FinancialData,
    current_market_cap: float,
    reasonable_pb: float = 1.5,
    historical_mcaps: list[tuple[str, float]] | None = None,
) -> ValuationResult:
    """对给定股票进行估值分析。

    Args:
        data: 财务数据
        current_market_cap: 当前总市值（元）
        reasonable_pb: 合理 PB 倍数，默认 1.5
        historical_mcaps: 可选的历史市值序列 [(日期, 市值), ...] 用于计算 PB 分位
    """
    result = ValuationResult()
    balances = sorted(data.balance_sheets, key=lambda x: x.report_date)
    incomes = sorted(data.income_statements, key=lambda x: x.report_date)

    if not balances or not incomes:
        result.notes.append("缺少财务报表")
        return result

    latest_bal = balances[-1]
    if not latest_bal.total_equity_parent:
        result.notes.append("缺少归母净资产")
        return result

    # 当前 PB
    result.current_pb = current_market_cap / latest_bal.total_equity_parent

    # 周期调整 PE = 当前市值 / 多年平均利润
    profits = [inc.net_income_parent for inc in incomes if inc.net_income_parent]
    if profits:
        result.avg_profit = sum(profits) / len(profits)
        if result.avg_profit:
            result.cycle_adjusted_pe = current_market_cap / result.avg_profit
            if len(profits) >= 3:
                mean_p = result.avg_profit
                variance = sum((p - mean_p) ** 2 for p in profits) / len(profits)
                std = variance**0.5
                result.profit_cv = std / mean_p if mean_p else None

    # PB 历史分位
    if historical_mcaps:
        pb_series = []
        for date, mcap in historical_mcaps:
            bal = _find_balance_for_date(balances, date)
            if bal and bal.total_equity_parent:
                pb_series.append(mcap / bal.total_equity_parent)
        if pb_series and result.current_pb is not None:
            result.pb_percentile = _percentile(pb_series, result.current_pb)

    # 安全边际（基于合理 PB）
    result.intrinsic_value_pb = latest_bal.total_equity_parent * reasonable_pb
    if current_market_cap:
        result.safety_margin = (result.intrinsic_value_pb - current_market_cap) / current_market_cap

    return result


def _find_balance_for_date(balances: list, date: str) -> object | None:
    """找到不超过给定日期的最新财报。"""
    candidates = [b for b in balances if b.report_date <= date]
    return candidates[-1] if candidates else None


def _percentile(series: list[float], value: float) -> float:
    """计算 value 在 series 中的百分位（0-100）。"""
    if not series:
        return 0.0
    count = sum(1 for s in series if s <= value)
    return count / len(series) * 100
