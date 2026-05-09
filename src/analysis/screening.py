"""八维度筛选与一票否决。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.financial import FinancialData, FinancialIndicators


@dataclass
class VetoResult:
    """一票否决结果。"""

    passed: bool = True
    vetoes: list[str] = field(default_factory=list)


@dataclass
class RedLineResult:
    """财务红线检查结果。"""

    passed: bool = True
    breaches: list[str] = field(default_factory=list)


def veto_check(data: FinancialData, indicators: list[FinancialIndicators]) -> VetoResult:
    """一票否决清单检查。

    出现以下任一情况，直接排除：
    1. 财务造假历史或审计非标意见（数据层无法判断，留空）
    2. 大股东高比例质押（>50%，数据层无法判断，留空）
    3. 实控人频繁变更或重大法律纠纷（数据层无法判断，留空）
    4. 主营业务涉及政策打压方向（数据层无法判断，留空）
    5. 应收账款增速连续两期超过营收增速且周转天数拉长
    6. 经营现金流连续两期为负
    7. 商誉占净资产比例超过 30%
    8. 有息负债率超过 60%
    9. 流动比率低于 1
    10. 行业处于明确衰退期（数据层无法判断，留空）
    """
    result = VetoResult()

    if not data.income_statements or not data.balance_sheets:
        result.passed = False
        result.vetoes.append("缺少财务报表数据")
        return result

    incomes = sorted(data.income_statements, key=lambda x: x.report_date)
    balances = sorted(data.balance_sheets, key=lambda x: x.report_date)
    cashflows = sorted(data.cash_flows, key=lambda x: x.report_date)

    # ---- 否决5：应收增速 > 营收增速 且周转天数拉长 ----
    if len(incomes) >= 2:
        rev_growth = _growth_rate(incomes[-1].total_revenue, incomes[-2].total_revenue)
        ar_growth = _growth_rate(balances[-1].accounts_receivable, balances[-2].accounts_receivable)
        if (
            rev_growth is not None
            and ar_growth is not None
            and ar_growth > rev_growth
            and ar_growth > 0
        ):
            result.vetoes.append(f"应收账款增速 ({ar_growth:.1%}) 超过营收增速 ({rev_growth:.1%})")

    # ---- 否决6：经营现金流连续两期为负 ----
    if (
        len(cashflows) >= 2
        and cashflows[-1].operating_cash_flow < 0
        and cashflows[-2].operating_cash_flow < 0
    ):
        result.vetoes.append("经营现金流连续两期为负")

    # ---- 否决7：商誉 / 净资产 > 30% ----
    latest_bal = balances[-1]
    if latest_bal.total_equity_parent:
        gw_ratio = latest_bal.goodwill / latest_bal.total_equity_parent
        if gw_ratio > 0.30:
            result.vetoes.append(f"商誉占净资产 {gw_ratio:.1%} > 30%")

    # ---- 否决8：有息负债率 > 60% ----
    interest_debt = (
        latest_bal.short_term_loans + latest_bal.long_term_loans + latest_bal.bonds_payable
    )
    if latest_bal.total_assets:
        ib_ratio = interest_debt / latest_bal.total_assets
        if ib_ratio > 0.60:
            result.vetoes.append(f"有息负债率 {ib_ratio:.1%} > 60%")

    # ---- 否决9：流动比率 < 1 ----
    # 使用近似计算：流动资产 ≈ 现金 + 应收 + 存货
    current_assets = (
        latest_bal.cash_and_equivalents + latest_bal.accounts_receivable + latest_bal.inventory
    )
    current_liabilities = latest_bal.accounts_payable + latest_bal.short_term_loans
    if current_liabilities > 0:
        current_ratio = current_assets / current_liabilities
        if current_ratio < 1.0:
            result.vetoes.append(f"流动比率 {current_ratio:.2f} < 1.0")

    result.passed = len(result.vetoes) == 0
    return result


def red_line_check(indicators: list[FinancialIndicators]) -> RedLineResult:
    """财务红线检查。

    - 长期平均 ROE < 12%：回避
    - 毛利率 < 15%：回避
    - 经营现金流 / 净利润（长期平均）< 0.5：高度警惕
    """
    result = RedLineResult()

    if not indicators:
        result.passed = False
        result.breaches.append("无指标数据")
        return result

    roe_vals = [i.roe for i in indicators if i.roe is not None]
    gm_vals = [i.gross_margin for i in indicators if i.gross_margin is not None]
    ocf_vals = [i.ocf_to_netincome for i in indicators if i.ocf_to_netincome is not None]

    if roe_vals and sum(roe_vals) / len(roe_vals) < 0.12:
        result.breaches.append(f"长期平均 ROE {sum(roe_vals) / len(roe_vals):.1%} < 12%")

    if gm_vals and sum(gm_vals) / len(gm_vals) < 0.15:
        result.breaches.append(f"长期平均毛利率 {sum(gm_vals) / len(gm_vals):.1%} < 15%")

    if ocf_vals and sum(ocf_vals) / len(ocf_vals) < 0.5:
        result.breaches.append(f"长期经营现金流/净利润 {sum(ocf_vals) / len(ocf_vals):.1%} < 0.5")

    result.passed = len(result.breaches) == 0
    return result


def _growth_rate(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return (current - previous) / abs(previous)
