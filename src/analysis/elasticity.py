"""利润弹性与收益空间测算。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.financial import FinancialData


@dataclass
class ScenarioResult:
    """单个情景测算结果。"""

    name: str
    revenue_change_pct: float
    gross_margin_assumed: float
    net_profit: float
    target_pe: float
    implied_market_cap: float
    upside_pct: float


@dataclass
class ElasticityResult:
    """利润弹性分析结果。"""

    historical_elasticity: float | None = None  # 顶部利润 / 底部利润
    peak_profit: float | None = None
    trough_profit: float | None = None
    scenarios: list[ScenarioResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def calculate(
    data: FinancialData,
    current_market_cap: float,
    scenarios: list[dict] | None = None,
) -> ElasticityResult:
    """测算利润弹性与收益空间。

    Args:
        data: 财务数据
        current_market_cap: 当前总市值（元）
        scenarios: 自定义情景列表，每个 dict 含 name/revenue_change/gm_premium/pe
                   为 None 时使用默认三情景（悲观/基准/乐观）
    """
    result = ElasticityResult()
    incomes = sorted(data.income_statements, key=lambda x: x.report_date)

    if not incomes:
        result.notes.append("缺少利润表")
        return result

    profits = [inc.net_income_parent for inc in incomes if inc.net_income_parent]

    # 历史弹性
    if profits:
        result.peak_profit = max(profits)
        positive = [p for p in profits if p > 0]
        result.trough_profit = min(positive) if positive else min(profits)
        if result.trough_profit and result.trough_profit != 0:
            result.historical_elasticity = result.peak_profit / result.trough_profit

    # 默认三情景
    if scenarios is None:
        scenarios = [
            {"name": "悲观", "revenue_change": -0.15, "gm_premium": -0.05, "pe": 8},
            {"name": "基准", "revenue_change": 0.00, "gm_premium": 0.00, "pe": 10},
            {"name": "乐观", "revenue_change": 0.25, "gm_premium": 0.03, "pe": 12},
        ]

    latest = incomes[-1]
    base_revenue = latest.total_revenue
    base_gm = latest.gross_profit / latest.total_revenue if latest.total_revenue else 0.30
    base_net_margin = (
        latest.net_income_parent / latest.total_revenue if latest.total_revenue else 0.10
    )

    for sc in scenarios:
        name = sc["name"]
        rev_change = sc["revenue_change"]
        gm_premium = sc.get("gm_premium", 0.0)
        pe = sc.get("pe", 10.0)

        projected_revenue = base_revenue * (1 + rev_change)
        projected_gm = max(0.05, min(0.95, base_gm + gm_premium))
        # 毛利率变化近似等幅度传导至净利率
        projected_net_margin = max(0.01, base_net_margin + gm_premium)
        projected_profit = projected_revenue * projected_net_margin

        implied_mcap = projected_profit * pe
        upside = (
            (implied_mcap - current_market_cap) / current_market_cap if current_market_cap else 0.0
        )

        result.scenarios.append(
            ScenarioResult(
                name=name,
                revenue_change_pct=rev_change * 100,
                gross_margin_assumed=projected_gm,
                net_profit=projected_profit,
                target_pe=pe,
                implied_market_cap=implied_mcap,
                upside_pct=upside * 100,
            )
        )

    return result


def _estimate_expense_ratio(incomes: list) -> float:
    """估算历史平均费用率 = (营收 - 净利润) / 营收。"""
    ratios = []
    for inc in incomes:
        if inc.total_revenue and inc.total_revenue > 0:
            ratios.append((inc.total_revenue - inc.net_income_parent) / inc.total_revenue)
    return sum(ratios) / len(ratios) if ratios else 0.70
