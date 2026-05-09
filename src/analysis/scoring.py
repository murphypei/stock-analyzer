"""十维评分模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.financial import FinancialData, FinancialIndicators


@dataclass
class DimensionScore:
    """单个维度得分。"""

    name: str
    weight: float
    score: float | None = None  # None = 需要人工评估
    max_score: float = 10.0
    note: str = ""


@dataclass
class ScoringResult:
    """评分结果。"""

    dimensions: list[DimensionScore] = field(default_factory=list)
    total_score: float = 0.0
    max_possible: float = 0.0
    grade: str = ""
    passed: bool = False


# 维度定义（权重总和 = 1.0）
_DIMENSIONS: list[tuple[str, float]] = [
    ("国资背景", 0.15),
    ("行业适配", 0.10),
    ("稀缺性/不可替代", 0.15),
    ("主营集中度", 0.10),
    ("商业模式简单", 0.05),
    ("估值与位置", 0.10),
    ("市值弹性", 0.05),
    ("周期顶部盈利潜力", 0.10),
    ("商业模式质量", 0.05),
    ("周期位置", 0.05),
    ("财务质量", 0.05),
    ("风险可控性", 0.05),
]


def score(
    data: FinancialData,
    indicators: list[FinancialIndicators],
    overrides: dict[str, float] | None = None,
) -> ScoringResult:
    """十维评分。

    Args:
        data: 完整财务数据
        indicators: 计算指标列表（已排序，最新在前）
        overrides: 人工覆盖评分，key 为维度名，value 为 0-10 分
    """
    overrides = overrides or {}
    result = ScoringResult()
    total = 0.0
    max_total = 0.0

    for name, weight in _DIMENSIONS:
        dim = DimensionScore(name=name, weight=weight)

        if name in overrides:
            dim.score = overrides[name]
            dim.note = "人工评分"
        else:
            dim.score, dim.note = _auto_score(name, data, indicators)

        if dim.score is not None:
            total += dim.score * weight
            max_total += 10.0 * weight

        result.dimensions.append(dim)

    result.total_score = total
    result.max_possible = max_total
    result.grade = _to_grade(total)
    result.passed = total >= 70.0
    return result


# --------------------------------------------------------------------------- #
# Auto-scoring helpers
# --------------------------------------------------------------------------- #


def _auto_score(
    name: str, data: FinancialData, indicators: list[FinancialIndicators]
) -> tuple[float | None, str]:
    """对可自动评分的维度给出机器评分；其余返回 None。"""

    if name == "商业模式质量":
        return _score_biz_quality(indicators)

    if name == "财务质量":
        return _score_financial_quality(data, indicators)

    if name == "风险可控性":
        return _score_risk(data, indicators)

    if name == "周期顶部盈利潜力" and data.income_statements:
        return _score_peak_potential(data.income_statements)

    # 其余维度需要人工判断
    return None, "需人工评估"


def _score_biz_quality(indicators: list[FinancialIndicators]) -> tuple[float, str]:
    """评分依据：ROE 稳定性、毛利率水平、现金流质量。"""
    if not indicators:
        return 0.0, "无数据"

    roes = [i.roe for i in indicators if i.roe is not None]
    gms = [i.gross_margin for i in indicators if i.gross_margin is not None]
    ocfs = [i.ocf_to_netincome for i in indicators if i.ocf_to_netincome is not None]

    score = 5.0  # 基准分
    notes: list[str] = []

    if roes:
        avg_roe = sum(roes) / len(roes)
        if avg_roe >= 0.15:
            score += 2.0
        elif avg_roe >= 0.12:
            score += 1.0
        elif avg_roe < 0.08:
            score -= 2.0
        notes.append(f"平均 ROE {avg_roe:.1%}")

        # 稳定性
        if len(roes) >= 2:
            std = (sum((r - sum(roes) / len(roes)) ** 2 for r in roes) / len(roes)) ** 0.5
            if std < 0.05:
                score += 1.0
                notes.append("ROE 稳定")
            elif std > 0.15:
                score -= 1.0
                notes.append("ROE 波动大")

    if gms:
        avg_gm = sum(gms) / len(gms)
        if avg_gm >= 0.30:
            score += 1.0
        elif avg_gm < 0.15:
            score -= 1.0
        notes.append(f"平均毛利率 {avg_gm:.1%}")

    if ocfs:
        avg_ocf = sum(ocfs) / len(ocfs)
        if avg_ocf >= 1.0:
            score += 1.0
        elif avg_ocf < 0.5:
            score -= 1.0
        notes.append(f"平均 OCF/净利润 {avg_ocf:.1%}")

    score = max(0.0, min(10.0, score))
    return score, "; ".join(notes)


def _score_financial_quality(
    data: FinancialData, indicators: list[FinancialIndicators]
) -> tuple[float, str]:
    """评分依据：负债结构、应收存货、资产质量。"""
    if not data.balance_sheets or not indicators:
        return 0.0, "无数据"

    latest_bal = max(data.balance_sheets, key=lambda b: b.report_date)
    score = 5.0
    notes: list[str] = []

    # 负债结构
    if latest_bal.total_assets:
        debt_ratio = latest_bal.total_liabilities / latest_bal.total_assets
        if debt_ratio < 0.40:
            score += 2.0
        elif debt_ratio < 0.60:
            score += 0.5
        else:
            score -= 2.0
        notes.append(f"负债率 {debt_ratio:.1%}")

    # 应收 + 存货
    rev = max(data.income_statements, key=lambda i: i.report_date).total_revenue
    if rev:
        ar_ratio = latest_bal.accounts_receivable / rev
        inv_ratio = latest_bal.inventory / rev
        if ar_ratio < 0.10 and inv_ratio < 0.15:
            score += 1.5
        elif ar_ratio > 0.30 or inv_ratio > 0.30:
            score -= 1.5
        notes.append(f"应收/营收 {ar_ratio:.1%}, 存货/营收 {inv_ratio:.1%}")

    # 商誉
    if latest_bal.total_equity_parent:
        gw_ratio = latest_bal.goodwill / latest_bal.total_equity_parent
        if gw_ratio > 0.30:
            score -= 2.0
            notes.append(f"商誉占比高 {gw_ratio:.1%}")

    score = max(0.0, min(10.0, score))
    return score, "; ".join(notes)


def _score_risk(data: FinancialData, indicators: list[FinancialIndicators]) -> tuple[float, str]:
    """评分依据：杠杆水平、流动比率、利息覆盖。"""
    if not data.balance_sheets or not indicators:
        return 0.0, "无数据"

    latest_bal = max(data.balance_sheets, key=lambda b: b.report_date)
    latest_ind = indicators[0] if indicators else None
    score = 5.0
    notes: list[str] = []

    # 有息负债率
    if latest_bal.total_assets:
        ib_debt = (
            latest_bal.short_term_loans + latest_bal.long_term_loans + latest_bal.bonds_payable
        )
        ib_ratio = ib_debt / latest_bal.total_assets
        if ib_ratio < 0.30:
            score += 2.0
        elif ib_ratio < 0.50:
            score += 0.5
        else:
            score -= 2.0
        notes.append(f"有息负债率 {ib_ratio:.1%}")

    # 流动比率
    if latest_ind and latest_ind.current_ratio is not None:
        if latest_ind.current_ratio >= 1.5:
            score += 1.5
        elif latest_ind.current_ratio < 1.0:
            score -= 1.5
        notes.append(f"流动比率 {latest_ind.current_ratio:.2f}")

    # 利息覆盖
    if latest_ind and latest_ind.interest_coverage is not None:
        if latest_ind.interest_coverage >= 5:
            score += 1.5
        elif latest_ind.interest_coverage < 2:
            score -= 1.5
        notes.append(f"利息覆盖 {latest_ind.interest_coverage:.1f}")

    score = max(0.0, min(10.0, score))
    return score, "; ".join(notes)


def _score_peak_potential(
    income_statements: list[FinancialIndicators],
) -> tuple[float, str]:
    """评分依据：历史周期顶部利润弹性。"""
    if len(income_statements) < 3:
        return 5.0, "数据不足，默认5分"

    profits = [inc.net_income_parent for inc in income_statements if inc.net_income_parent]
    if not profits:
        return 5.0, "无利润数据"

    peak = max(profits)
    trough = min(p for p in profits if p > 0) if any(p > 0 for p in profits) else min(profits)
    if trough == 0:
        return 5.0, "无法计算弹性"

    elasticity = peak / abs(trough)
    if elasticity >= 10:
        return 9.0, f"顶部利润是底部 {elasticity:.1f} 倍，弹性极高"
    elif elasticity >= 5:
        return 7.5, f"顶部利润是底部 {elasticity:.1f} 倍，弹性高"
    elif elasticity >= 2:
        return 6.0, f"顶部利润是底部 {elasticity:.1f} 倍，弹性中等"
    else:
        return 4.0, f"顶部利润是底部 {elasticity:.1f} 倍，弹性偏低"


def _to_grade(total: float) -> str:
    if total >= 90:
        return "S"
    if total >= 80:
        return "A"
    if total >= 70:
        return "B"
    if total >= 60:
        return "C"
    return "D"
