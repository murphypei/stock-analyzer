"""财报预警信号组合。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.financial import FinancialData


@dataclass
class WarningSignals:
    """预警信号结果。"""

    signals: list[str] = field(default_factory=list)
    cycle_phase: str = "未知"
    action: str = ""


def analyze(data: FinancialData) -> WarningSignals:
    """分析财报预警信号组合。

    最强卖出信号：利润创新高 + Capex 暴增 + 库存大幅上升
    下行拐点前夜：利润还在增长 + 经营现金流萎缩 + 应收激增
    最强买入确认：扭亏为盈 + 经营现金流改善 + 库存去化
    """
    result = WarningSignals()

    if not data.income_statements or not data.balance_sheets or not data.cash_flows:
        result.signals.append("缺少完整财报数据，无法判断预警信号")
        return result

    incomes = sorted(data.income_statements, key=lambda x: x.report_date)
    balances = sorted(data.balance_sheets, key=lambda x: x.report_date)
    cashflows = sorted(data.cash_flows, key=lambda x: x.report_date)

    if len(incomes) < 3:
        result.signals.append("历史数据不足（需至少3期）")
        return result

    cf_map = {cf.report_date: cf for cf in cashflows}
    bal_map = {b.report_date: b for b in balances}

    # 提取关键序列
    profits = [inc.net_income_parent for inc in incomes if inc.net_income_parent]
    ocf_seq = [
        cf_map[inc.report_date].operating_cash_flow for inc in incomes if inc.report_date in cf_map
    ]
    ar_seq = [
        bal_map[inc.report_date].accounts_receivable
        for inc in incomes
        if inc.report_date in bal_map
    ]
    inv_seq = [bal_map[inc.report_date].inventory for inc in incomes if inc.report_date in bal_map]
    capex_seq = [cf_map[inc.report_date].capex for inc in incomes if inc.report_date in cf_map]

    # ---- 信号1：周期顶峰（最强卖出） ----
    peak_signal = _check_cycle_peak(profits, capex_seq, inv_seq)
    if peak_signal:
        result.signals.append(peak_signal)
        result.cycle_phase = "繁荣/顶峰"
        result.action = "最强卖出信号"
        return result  # 顶峰信号优先级最高，直接返回

    # ---- 信号2：下行拐点前夜 ----
    downturn_signal = _check_downturn(incomes, ocf_seq, ar_seq)
    if downturn_signal:
        result.signals.append(downturn_signal)
        result.cycle_phase = "衰退下行"
        result.action = "减仓或清仓"

    # ---- 信号3：周期底部启动（最强买入确认） ----
    bottom_signal = _check_bottom(incomes, ocf_seq, inv_seq)
    if bottom_signal:
        result.signals.append(bottom_signal)
        result.cycle_phase = "复苏上行"
        result.action = "最强买入确认"

    if not result.signals:
        result.signals.append("未触发显著预警信号")
        result.cycle_phase = "中性"
        result.action = "继续观察"

    return result


def _check_cycle_peak(
    profits: list[float],
    capex_seq: list[float],
    inv_seq: list[float],
) -> str:
    """周期顶峰信号：利润新高 + Capex 暴增 + 库存上升。"""
    if len(profits) < 3 or not capex_seq or not inv_seq:
        return ""

    profit_peak = profits[-1] == max(profits) and profits[-1] > 0

    # Capex 暴增：最近一期比前一期增长 > 50%
    capex_surge = len(capex_seq) >= 2 and capex_seq[-2] != 0 and capex_seq[-1] / capex_seq[-2] > 1.5

    # 库存上升：最近一期比前一期增长 > 20%
    inv_rise = len(inv_seq) >= 2 and inv_seq[-2] != 0 and inv_seq[-1] / inv_seq[-2] > 1.2

    if profit_peak and (capex_surge or inv_rise):
        parts = ["利润创历史新高"]
        if capex_surge:
            parts.append("Capex 激增")
        if inv_rise:
            parts.append("库存上升")
        return "周期顶峰：" + " + ".join(parts) + " → 最强卖出信号"

    return ""


def _check_downturn(
    incomes: list,
    ocf_seq: list[float],
    ar_seq: list[float],
) -> str:
    """下行拐点信号：利润还在增长 + 经营现金流萎缩 + 应收激增。"""
    if len(incomes) < 3 or len(ocf_seq) < 2 or len(ar_seq) < 2:
        return ""

    # 利润还在增长
    profit_growing = incomes[-1].net_income_parent > incomes[-2].net_income_parent

    # 经营现金流萎缩：最近一期 < 前一期 的 70%
    ocf_shrink = ocf_seq[-2] != 0 and ocf_seq[-1] / abs(ocf_seq[-2]) < 0.7

    # 应收激增：最近一期比前一期增长 > 30%
    ar_surge = ar_seq[-2] != 0 and ar_seq[-1] / ar_seq[-2] > 1.3

    if profit_growing and (ocf_shrink or ar_surge):
        parts = ["利润仍在增长"]
        if ocf_shrink:
            parts.append("经营现金流萎缩")
        if ar_surge:
            parts.append("应收激增")
        return "下行拐点前夜：" + " + ".join(parts) + " → 减仓或清仓"

    return ""


def _check_bottom(
    incomes: list,
    ocf_seq: list[float],
    inv_seq: list[float],
) -> str:
    """周期底部信号：扭亏为盈 + 经营现金流改善 + 库存去化。"""
    if len(incomes) < 2 or len(ocf_seq) < 2 or len(inv_seq) < 2:
        return ""

    # 扭亏为盈
    turn_profit = incomes[-2].net_income_parent <= 0 and incomes[-1].net_income_parent > 0

    # 经营现金流改善：最近一期 > 前一期
    ocf_improve = ocf_seq[-1] > ocf_seq[-2]

    # 库存去化：最近一期 < 前一期 的 90%
    inv_reduce = inv_seq[-2] != 0 and inv_seq[-1] / inv_seq[-2] < 0.9

    if turn_profit and ocf_improve and inv_reduce:
        return "周期底部启动：扭亏为盈 + 经营现金流改善 + 库存去化 → 最强买入确认"

    # 放宽条件：满足其中两项
    count = sum([turn_profit, ocf_improve, inv_reduce])
    if count >= 2:
        parts = []
        if turn_profit:
            parts.append("扭亏为盈")
        if ocf_improve:
            parts.append("经营现金流改善")
        if inv_reduce:
            parts.append("库存去化")
        return "底部积极信号：" + " + ".join(parts)

    return ""
