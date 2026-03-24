# 统一数据源字段规范

本文档定义分型结果对象中 `payload` 的统一字段契约。所有 `*_unified` 数据源接口必须输出符合本文档的标准字段，调用方不得再依赖 provider 原生字段名（例如 `ts_code`、`trade_date`、`code`、`date`）。

## 总体约束

- 每个分型结果对象的 `payload` 中记录都必须是“标准字段”记录。
- 分型结果对象中的 `data_kind` 必须与记录类型一致。
- 分型结果对象中的 `schema_version` 当前固定为 `v1`。
- provider 原生字段只允许在 source 内部映射时使用，不允许泄漏到统一接口的返回值中。
- 协议层约束：`basic_info` 必须作为 `KlineDataSource` 的绑定能力出现（提供 K 线能力的 source 必须同时实现 `fetch_basic_info`）。
- 能力声明约束：`basic_info` 不再使用独立 capability，统一归属 `DataCapability.KLINE`。

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

## News 记录

- `data_kind`: `news`
- 适用接口：`fetch_news_unified`

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `published_at` | `datetime \\| None` | 发布时间 |
| `title` | `str` | 标题 |
| `content` | `str` | 正文/摘要 |
| `source_channel` | `str` | 新闻来源渠道 |
| `url` | `str \\| None` | 原始链接 |
| `symbols` | `list[str]` | 关联证券代码列表 |

## Financial Report 记录

- `data_kind`: `financial_report`
- 适用接口：`fetch_financial_reports_unified`

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | `str` | 统一证券代码 |
| `report_type` | `str` | 报表类型，例如 `profit`、`forecast` |
| `report_date` | `datetime \\| None` | 报告日期 |
| `published_at` | `datetime \\| None` | 公告日期 |
| `report_year` | `int \\| None` | 报告年度 |
| `report_quarter` | `int \\| None` | 报告季度 |
| `metrics` | `dict[str, object]` | 剩余指标字段的统一容器 |

## 路由与元数据约束

- `fetch_klines_unified` 返回的 `route_key.capability` 必须为 `DataCapability.KLINE`。
- `fetch_basic_info` 返回的 `route_key.capability` 必须为 `DataCapability.KLINE`（`interval=None`）。
- `fetch_news_unified` 返回的 `route_key.capability` 必须为 `DataCapability.NEWS`。
- `fetch_financial_reports_unified` 返回的 `route_key.capability` 必须为 `DataCapability.FINANCIAL_REPORT`。
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