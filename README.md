# stock-analyzer

A股低估值周期投资策略的自动化分析框架。

基于「四步排雷法 + 八维度筛选 + 十维评分 + 财报预警 + 估值弹性」的完整个股深度分析流水线，支持多数据源自动降级、本地缓存和端到端批量分析。

---

## 核心功能

| 阶段 | 模块 | 说明 |
|------|------|------|
| **Phase 1 数据层** | `data_sources` | Tushare / Sina 直联 / Baostock / AKShare 多源自动降级，SQLite TTL 缓存 |
| **Phase 2 分析层** | `analysis` | 四步排雷法、一票否决、财务红线、十维评分、财报预警信号 |
| **Phase 3 估值层** | `valuation` / `elasticity` | PB 与周期调整 PE、安全边际、利润弹性三情景测算 |

### Phase 2 分析模块详解

- **四步排雷法** (`mine_sweeper`): 纯 PB 陷阱识别、跨周期十年数据审查、ROE≈PE 定价校验、高杠杆排查
- **一票否决** (`screening`): 10 项否决清单（应收/营收异常、经营现金流连续为负、商誉过高、有息负债率 >60%、流动比率 <1 等）
- **财务红线** (`screening`): ROE <12%、毛利率 <15%、经营现金流/净利润 <0.5
- **十维评分** (`scoring`): 12 维度 100 分制，4 维度（商业模式质量、财务质量、风险可控性、周期顶部盈利潜力）自动评分，其余支持人工覆盖
- **财报预警信号** (`warnings`): 周期顶峰（最强卖出）、下行拐点前夜、周期底部启动（最强买入确认）

### Phase 3 估值模块详解

- **估值模型** (`valuation`): 当前 PB、PB 历史分位、周期调整 PE、利润变异系数、基于合理 PB 的安全边际
- **利润弹性** (`elasticity`): 历史顶部/底部利润弹性倍数 + 悲观/基准/乐观三情景收益空间测算

---

## 快速开始

### 环境要求

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装

```bash
git clone <repo-url>
cd stock-analyzer
uv sync
```

### 配置数据源（可选）

在项目根目录创建 `.env` 文件：

```bash
TUSHARE_TOKEN=your_tushare_token
```

未配置 Tushare Token 时，系统会自动降级至 Sina 直联 API（无需认证）。

### 运行验证脚本

```bash
uv run python validate.py
```

该脚本会抓取 3 只样本股票的财报数据，跑完整 Phase 1+2+3 流水线，并输出分析结果：

```
Stock: 600519.SH (贵州茅台)
  Market Cap:     1,719,354,000,000
  ...
  [Phase 2] Mine Sweeper:    Passed: True
  [Phase 2] Screening:       Veto Passed: False
  [Phase 3] Valuation:       Current PB: 6.35  Safety Margin: -76.4% (overvalued)
  [Phase 3] Profit Elasticity:
    悲观   Upside=-90.3%
    基准   Upside=-84.2%
    乐观   Upside=-74.8%
```

---

## 项目结构

```
stock-analyzer/
├── src/
│   ├── analysis/           # Phase 2+3 分析模块
│   │   ├── mine_sweeper.py   # 四步排雷法
│   │   ├── screening.py      # 一票否决 + 财务红线
│   │   ├── scoring.py        # 十维评分模型
│   │   ├── warnings.py       # 财报预警信号
│   │   ├── valuation.py      # PB / 周期调整 PE / 安全边际
│   │   └── elasticity.py     # 利润弹性与收益空间测算
│   ├── data_sources/       # Phase 1 数据获取
│   │   ├── adapter.py        # 统一适配器（自动降级）
│   │   ├── base.py           # 抽象基类
│   │   ├── sina.py           # Sina 直联 API
│   │   ├── tushare.py        # Tushare Pro
│   │   ├── baostock.py       # Baostock
│   │   └── akshare.py        # AKShare
│   ├── indicators/         # 财务指标计算
│   │   └── calculator.py
│   ├── models/             # 数据模型
│   │   └── financial.py
│   └── cache/              # SQLite 本地缓存
│       └── sqlite_cache.py
├── tests/                  # 单元测试
├── validate.py             # 端到端验证脚本
├── pyproject.toml          # uv 项目配置
└── README.md
```

---

## 代码调用示例

### 获取数据并计算指标

```python
from src.data_sources.adapter import DataSourceAdapter
from src.indicators.calculator import calc_indicators

adapter = DataSourceAdapter()
data = adapter.fetch_full("600519.SH", years=5)
data.indicators = calc_indicators(data)
```

### Phase 2 分析

```python
from src.analysis.mine_sweeper import sweep
from src.analysis.screening import veto_check, red_line_check
from src.analysis.scoring import score
from src.analysis.warnings import analyze

ms = sweep(data, latest_pe=20)
veto = veto_check(data, data.indicators)
red = red_line_check(data.indicators)
sc = score(data, data.indicators, overrides={})
ws = analyze(data)
```

### Phase 3 估值与弹性

```python
from src.analysis.valuation import evaluate
from src.analysis.elasticity import calculate

val = evaluate(data, current_market_cap=1.7e12, reasonable_pb=1.5)
el = calculate(data, current_market_cap=1.7e12)

print(f"PB: {val.current_pb:.2f}, Safety Margin: {val.safety_margin:+.1%}")
for s in el.scenarios:
    print(f"{s.name}: Upside={s.upside_pct:+.1f}%")
```

---

## 数据源说明

| 优先级 | 数据源 | 特点 | 认证要求 |
|--------|--------|------|----------|
| 1 | Tushare Pro | 数据最全、最规范 | Token 认证 |
| 2 | Sina 直联 | 无需认证、稳定性高 | 无 |
| 3 | Baostock | 免费、历史数据全 | 无 |
| 4 | AKShare | 备用来源 | 无 |

`DataSourceAdapter` 会按优先级依次尝试，任一源成功即返回数据，并自动写入 SQLite 缓存（默认 7 天 TTL）。

---

## 测试

```bash
# 运行全部测试
uv run pytest -v

# 仅运行 Phase 2 分析测试
uv run pytest tests/test_analysis.py -v

# 仅运行 Phase 3 估值测试
uv run pytest tests/test_phase3.py -v
```

当前共 16 个测试用例，覆盖数据缓存、指标计算、排雷、筛选、评分、预警、估值和弹性测算。

---

## 开发规范

- **格式化**: `uv run ruff format src tests validate.py`
- **静态检查**: `uv run ruff check src tests validate.py`
- **目标 Python 版本**: 3.10+

---

## 免责声明

本项目仅供学习研究使用，不构成任何投资建议。财务数据和计算结果可能存在误差，投资决策请结合多方信息独立判断。
