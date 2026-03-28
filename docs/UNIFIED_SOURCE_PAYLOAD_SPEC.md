# 统一数据源字段规范

本文档定义分型结果对象中 `payload` 的统一字段契约。所有 `*_unified` 数据源接口必须输出符合本文档的标准字段，调用方不得再依赖 provider 原生字段名（例如 `ts_code`、`trade_date`、`code`、`date`）。

## 总体约束

- 每个分型结果对象的 `payload` 中记录都必须是“标准字段”记录。
- 分型结果对象中的 `data_kind` 必须与记录类型一致。
- 分型结果对象中的 `schema_version` 当前固定为 `v1`。
- provider 原生字段只允许在 source 内部映射时使用，不允许泄漏到统一接口的返回值中。
- 协议层约束：`basic_info` 必须作为 `KlineDataSource` 的绑定能力出现（提供 K 线能力的 source 必须同时实现 `fetch_basic_info`）。
- 能力声明约束：`basic_info` 不再使用独立 capability，统一归属 `DataCapability.KLINE`。
- 当前 sources 实现范围包含 `kline/basic_info` 和 `company_detail`，不包含 `news/financial_report`。

## Kline 记录

- `data_kind`: `kline`
- 适用接口：`fetch_klines_unified`

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | `str` | 统一证券代码，例如 `000001.SZ` |
| `bar_time` | `datetime` | K 线时间点 |
| `interval` | `str` | 统一周期值，例如 `5m`、`1d` |
| `open` | `float \\| None` | 开盘价 |
| `high` | `float \\| None` | 最高价 |
| `low` | `float \\| None` | 最低价 |
| `close` | `float \\| None` | 收盘价 |
| `volume` | `float \\| None` | 成交量 |
| `amount` | `float \\| None` | 成交额 |
| `change_pct` | `float \\| None` | 涨跌幅 |
| `turnover_rate` | `float \\| None` | 换手率 |
| `adjusted` | `bool` | 是否复权 |

### 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_trading` | `bool \\| None` | 是否处于可交易状态；无此信息时可为 `None` |

### 时间与 symbol 规则

- `KlineQuery.start_time/end_time` 输入必须是 UTC 时间并精确到分钟（秒与微秒为 0）。
- source 内部可以按市场时区换算为 provider 查询参数。
- `KlineRecord.bar_time` 输出必须是 UTC，且语义为 bar 开始时间。
- A 股 `1d` 的 `bar_time` 必须按北京时间 `09:30` 对齐后转换为 UTC。
- A 股 symbol 对外统一为 `000001.SZ` / `600000.SH` 格式，由各 source 内部完成 provider 适配。
- `fetch_klines_unified` 的 `payload` 必须按 `KlineRecord.bar_time` 递增排序（从旧到新）。

## Basic Info 记录

- `data_kind`: `basic_info`
- 适用接口：`fetch_basic_info`

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | `str` | 统一证券代码 |
| `name` | `str \\| None` | 名称 |
| `industry` | `str \\| None` | 行业 |
| `area` | `str \\| None` | 地域 |
| `market` | `str \\| None` | 市场标识，如 `main`、`sh`、`sz` |
| `list_date` | `datetime \\| None` | 上市日期 |
| `status` | `str \\| None` | 上市/退市状态 |

### 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `delist_date` | `datetime \\| None` | 退市日期 |
| `security_type` | `str \\| None` | 证券类型（统一符号值，见下文 `#sym:security_type` 映射规则） |

### BaoStock 字段映射与说明（basic_info）

BaoStock 的 `query_stock_basic()` 返回常见字段：

- `code`: 证券代码（如 `sh.600000`）
- `code_name`: 证券名称
- `ipoDate`: 上市日期
- `outDate`: 终止/退市日期（空串表示未退市）
- `status`: 上市状态（常见 `1`=上市中，`0`=非上市/终止）
- `type`: BaoStock 原生证券类别代码（字符串编码）

当前系统在 `basic_info` 聚合场景中默认以 BaoStock 作为优先源（若 TuShare 已配置，则为回退源）。

### `#sym:security_type` 候选映射表（基于现网样本）

说明：下表为候选规则，来源于当前样本观测（`query_stock_basic` 约 8k+ 记录）。若后续新增类型码，应按“未知值回退”规则处理并补充映射。

| provider | raw value | candidate symbol (`#sym:security_type`) | 说明 |
|------|------|------|------|
| baostock | `1` | `stock` | 普通股票（A 股个股） |
| baostock | `2` | `index` | 指数类（样本含 `sh.000001`） |
| baostock | `4` | `bond` | 债券类（样本含可转债） |
| baostock | `5` | `fund` | 基金类（样本含 ETF） |

### `#sym:security_type` 映射规则（面向后续接口规范）

为兼容后续多源接口收敛，`security_type` 采用“统一符号值优先、provider 原值可追溯”的策略：

1. 统一输出值域
	- 对外 `security_type` 仅输出统一符号值：`stock` / `index` / `bond` / `fund` / `unknown`。
	- 不直接向调用方暴露 provider 原始编码（如 BaoStock 的 `"1"`、`"2"`）。

2. provider 到 `#sym:security_type` 的映射
	- 先按 provider 专属映射表转换（BaoStock 先按上表处理）。
	- 无法命中映射时统一落为 `unknown`，禁止抛错中断主流程。

3. 可追溯性要求
	- 建议在持久化层/调试元数据保留 `provider_security_type_raw`（或等价字段）用于排障与回溯。
	- 统一接口响应层不强制暴露该原始字段。

4. 兼容性与演进
	- 新 provider 接入时必须提供 `raw -> #sym:security_type` 映射，并补充 contract tests。
	- 若未来需要引入新的统一符号值（例如 `reit`），属于语义扩展：
	  - 向后兼容时可保持 `schema_version = v1`；
	  - 若改动已有符号语义或删除值域，需升级 `schema_version`。

## Company Valuation 记录

- `data_kind`: `company_valuation`
- 适用接口：`fetch_company_valuation_unified`

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `trade_date` | `datetime \\| None` | 交易日期（UTC时间，与日线对齐） |
| `pe_ttm` | `float \\| None` | 滚动市盈率 |
| `pe` | `float \\| None` | 市盈率 |
| `pb` | `float \\| None` | 市净率 |

## Company Financial Indicator 记录

- `data_kind`: `company_financial_indicator`
- 适用接口：`fetch_company_financial_indicators_unified`

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `report_date` | `datetime \\| None` | 财报日期（UTC时间） |
| `grossprofit_margin` | `float \\| None` | 销售毛利率 |
| `netprofit_margin` | `float \\| None` | 销售净利率 |
| `roe` | `float \\| None` | 净资产收益率 |
| `debt_to_assets` | `float \\| None` | 资产负债率 |

## Company Income Statement 记录

- `data_kind`: `company_income_statement`
- 适用接口：`fetch_company_income_statements_unified`

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `report_date` | `datetime \\| None` | 财报日期（UTC时间） |
| `total_revenue` | `float \\| None` | 营业总收入 |
| `total_operate_costs` | `float \\| None` | 营业总成本 |
| `operate_profit` | `float \\| None` | 营业利润 |
| `total_profit` | `float \\| None` | 利润总额 |
| `net_profit` | `float \\| None` | 净利润 |

## 路由与元数据约束

- `fetch_klines_unified` 返回的 `route_key.capability` 必须为 `DataCapability.KLINE`。
- `fetch_basic_info` 返回的 `route_key.capability` 必须为 `DataCapability.KLINE`（`interval=None`）。
- `route_key.market` 应保留调用方传入的市场维度，不能在 source 内被静默清空。
- `metadata["count"]` 必须等于 `len(payload)`。

## Contract Test 要求

新增或修改 source 时，至少应通过以下 contract tests：

- 共享能力的字段集合一致性测试
- 共享能力的字段类型一致性测试
- `data_kind` / `schema_version` / `route_key.capability` 一致性测试
- `KlineDataSource` 与 `fetch_basic_info` 绑定一致性测试

当前仓库中的跨源 contract tests 位于：

- [tests/unit/ingestion/test_source_contracts.py](tests/unit/ingestion/test_source_contracts.py)

## 变更规则

- 若新增字段且保持向后兼容，可保留 `schema_version = v1`，同时更新本文档与 contract tests。
- 若删除字段、重命名字段或改变字段语义，必须升级 `schema_version`，并补充迁移说明。
