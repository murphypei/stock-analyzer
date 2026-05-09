"""四步排雷法 — 价值陷阱识别。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.financial import BalanceSheet, CashFlowStatement, FinancialData, IncomeStatement


@dataclass
class MineSweepResult:
    """排雷结果。"""

    passed: bool = True
    warnings: list[str] = field(default_factory=list)

    # 四步排雷明细
    step1_pb_trap: bool = False
    step2_short_history: bool = False
    step3_roe_pe_mismatch: bool = False
    step4_high_leverage: bool = False

    # 三大陷阱
    pure_pb_trap: bool = False
    cycle_top_low_pe_trap: bool = False
    double_low_trap: bool = False


def sweep(data: FinancialData, latest_pe: float | None = None) -> MineSweepResult:
    """执行四步排雷法。

    Args:
        data: 完整财务数据（至少包含近5-10年数据）
        latest_pe: 最新PE（用于第三步和双低陷阱判断）
    """
    result = MineSweepResult()

    if not data.income_statements or not data.balance_sheets:
        result.passed = False
        result.warnings.append("缺少财务报表数据，无法排雷")
        return result

    incomes = sorted(data.income_statements, key=lambda x: x.report_date)
    balances = sorted(data.balance_sheets, key=lambda x: x.report_date)
    cashflows = sorted(data.cash_flows, key=lambda x: x.report_date)

    # 对齐最新一期
    incomes[-1]
    latest_bal = balances[-1]
    cashflows[-1] if cashflows else None

    # 计算长期平均值
    avg_roe = _avg_roe(incomes, balances)
    _avg_gross_margin(incomes)

    # ---- 第一步：回避纯 PB 陷阱 ----
    # 需要 PB 数据，如果未传入则跳过此步的硬性判断
    # 但可以通过 ROE 和盈利能力间接判断
    if avg_roe is not None and avg_roe < 0.08:
        result.step1_pb_trap = True
        result.warnings.append(f"长期 ROE {avg_roe:.1%} < 8%，疑似纯 PB 陷阱（资产便宜但不赚钱）")

    # ---- 第二步：跨周期看十年财务数据 ----
    if len(incomes) < 5:
        result.step2_short_history = True
        result.warnings.append(f"财务数据仅 {len(incomes)} 期，不足以跨周期判断（建议 >=5 年）")

    # ---- 第三步：长期 ROE ≈ 长期 PE ----
    if avg_roe is not None and latest_pe is not None:
        # 经验：长期合理 PE 数值上约等于长期 ROE（%）
        implied_pe = avg_roe * 100  # 例如 ROE=15% → 合理 PE≈15
        if abs(latest_pe - implied_pe) / implied_pe < 0.3:
            result.step3_roe_pe_mismatch = True
            result.warnings.append(
                f"长期 ROE {avg_roe:.1%} ≈ 当前 PE {latest_pe:.1f}，属于合理定价而非低估"
            )

    # ---- 第四步：识别高杠杆 ----
    debt_ratio = (
        latest_bal.total_liabilities / latest_bal.total_assets if latest_bal.total_assets else None
    )
    if debt_ratio is not None and debt_ratio > 0.60:
        result.step4_high_leverage = True
        result.warnings.append(f"资产负债率 {debt_ratio:.1%} > 60%，高杠杆风险")

    # ---- 三大陷阱识别 ----
    # 陷阱1：纯 PB 陷阱（已在 step1 判断）
    if result.step1_pb_trap:
        result.pure_pb_trap = True

    # 陷阱2：周期顶部低 PE 陷阱
    # 利润创新高 + Capex 暴增 + 库存上升
    if _is_cycle_top(incomes, balances, cashflows):
        result.cycle_top_low_pe_trap = True
        result.warnings.append("周期顶部信号：利润高点 + Capex 激增 + 库存上升，低 PE 可能是陷阱")

    # 陷阱3：双低陷阱（低 PE + 低 PB + 低 ROE）
    if avg_roe is not None and avg_roe < 0.10 and latest_pe is not None and latest_pe < 10:
        result.double_low_trap = True
        result.warnings.append(
            f"双低陷阱：低 PE ({latest_pe:.1f}) + 低 ROE ({avg_roe:.1%})，市场公允定价"
        )

    # 汇总
    result.passed = len(result.warnings) == 0
    return result


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _avg_roe(incomes: list[IncomeStatement], balances: list[BalanceSheet]) -> float | None:
    """计算各期 ROE 的平均值。"""
    roes: list[float] = []
    bal_map = {b.report_date: b for b in balances}
    for inc in incomes:
        bal = bal_map.get(inc.report_date)
        if bal and bal.total_equity_parent and inc.net_income_parent:
            roes.append(inc.net_income_parent / bal.total_equity_parent)
    return sum(roes) / len(roes) if roes else None


def _avg_gross_margin(incomes: list[IncomeStatement]) -> float | None:
    gms = [inc.gross_profit / inc.total_revenue for inc in incomes if inc.total_revenue]
    return sum(gms) / len(gms) if gms else None


def _is_cycle_top(
    incomes: list[IncomeStatement],
    balances: list[BalanceSheet],
    cashflows: list[CashFlowStatement],
) -> bool:
    """判断是否为周期顶部：利润创新高 + Capex 暴增 + 库存上升。"""
    if len(incomes) < 3 or not cashflows or not balances:
        return False

    # 利润是否处于历史高位
    profits = [inc.net_income_parent for inc in incomes if inc.net_income_parent]
    if not profits or profits[-1] != max(profits):
        return False

    # Capex 是否激增（最近一期 Capex 是否显著高于前期平均）
    cf_map = {cf.report_date: cf for cf in cashflows}
    capex_values = []
    for inc in incomes[-3:]:
        cf = cf_map.get(inc.report_date)
        if cf:
            capex_values.append(cf.capex)
    if len(capex_values) >= 2 and capex_values[-1] > capex_values[-2] * 1.5:
        capex_surge = True
    else:
        capex_surge = False

    # 库存是否上升
    {b.report_date: b for b in balances}
    latest_bal = balances[-1]
    prev_bal = balances[-2] if len(balances) >= 2 else None
    inventory_rise = prev_bal is not None and latest_bal.inventory > prev_bal.inventory * 1.2

    return profits[-1] == max(profits) and (capex_surge or inventory_rise)
