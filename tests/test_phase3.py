"""Tests for Phase 3 valuation and elasticity modules."""

from __future__ import annotations

from src.analysis.elasticity import calculate
from src.analysis.valuation import evaluate
from tests.test_analysis import _make_data


def test_valuation_basic():
    data = _make_data(roe=0.15, debt_ratio=0.40)
    # 当前市值设为净资产的 2 倍 → PB=2.0
    latest_bal = data.balance_sheets[-1]
    mcap = latest_bal.total_equity_parent * 2.0
    result = evaluate(data, current_market_cap=mcap, reasonable_pb=1.5)

    assert result.current_pb == 2.0
    assert result.cycle_adjusted_pe is not None
    assert result.avg_profit is not None
    assert result.safety_margin is not None
    # PB=2.0 > 合理 PB=1.5，安全边际应为负
    assert result.safety_margin < 0


def test_valuation_cheap():
    data = _make_data(roe=0.15, debt_ratio=0.40)
    latest_bal = data.balance_sheets[-1]
    mcap = latest_bal.total_equity_parent * 0.8  # PB=0.8
    result = evaluate(data, current_market_cap=mcap, reasonable_pb=1.5)

    assert result.current_pb == 0.8
    assert result.safety_margin > 0


def test_valuation_pb_percentile():
    data = _make_data(roe=0.15, debt_ratio=0.40)
    latest_bal = data.balance_sheets[-1]
    mcap = latest_bal.total_equity_parent * 1.0
    # 构造历史市值序列：对应 6 期财报，PB 分别为 0.5, 1.0, 1.5, 2.0, 2.5, 3.0
    hist_mcaps = [
        (bal.report_date, bal.total_equity_parent * (0.5 + i * 0.5))
        for i, bal in enumerate(data.balance_sheets)
    ]
    result = evaluate(data, current_market_cap=mcap, historical_mcaps=hist_mcaps)
    # current PB = 1.0，在历史序列中排第 2 位（0.5, 1.0, ...），百分位 ≈ 33%
    assert result.pb_percentile is not None
    assert 30 <= result.pb_percentile <= 35


def test_elasticity_default_scenarios():
    data = _make_data(profit_history=[100, 120, 150, 130, 110, 140])
    latest_bal = data.balance_sheets[-1]
    mcap = latest_bal.total_equity_parent * 2.0
    result = calculate(data, current_market_cap=mcap)

    assert result.historical_elasticity is not None
    # peak=150, trough=100 → elasticity=1.5
    assert result.historical_elasticity == 1.5
    assert len(result.scenarios) == 3

    names = [s.name for s in result.scenarios]
    assert "悲观" in names
    assert "基准" in names
    assert "乐观" in names

    # 乐观情景上涨空间应 > 悲观情景
    pessimistic = next(s for s in result.scenarios if s.name == "悲观")
    optimistic = next(s for s in result.scenarios if s.name == "乐观")
    assert optimistic.upside_pct > pessimistic.upside_pct


def test_elasticity_custom_scenarios():
    data = _make_data(profit_history=[100, 110, 120])
    latest_bal = data.balance_sheets[-1]
    mcap = latest_bal.total_equity_parent * 2.0
    scenarios = [{"name": "测试", "revenue_change": 0.10, "gm_premium": 0.02, "pe": 15}]
    result = calculate(data, current_market_cap=mcap, scenarios=scenarios)

    assert len(result.scenarios) == 1
    assert result.scenarios[0].name == "测试"
    assert result.scenarios[0].target_pe == 15
