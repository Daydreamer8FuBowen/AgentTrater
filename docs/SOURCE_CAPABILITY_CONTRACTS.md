# 数据源能力契约

本文档定义 `ingestion/sources` 的统一契约，当前保留 K 线域能力与公司详情能力。

## 基础要求

每个 provider 必须具备：

- `name: str`
- `capabilities() -> list[SourceCapabilitySpec]`

`capabilities()` 用于声明该 provider 支持哪些市场与周期范围。当前 capability 包含 `kline` 与 `company_detail`。

## 能力接口

### K 线域能力

- `fetch_klines_unified(query: KlineQuery) -> KlineFetchResult`
- `fetch_basic_info(market: ExchangeKind | None = None) -> BasicInfoFetchResult`

说明：`basic_info` 与 K 线能力绑定，不单独声明 capability，且 `capabilities()` 不再声明 `news/financial_report`。

### 公司详情能力 (company_detail)

- `fetch_company_valuation_unified(symbol: str, market: ExchangeKind | None = None) -> CompanyValuationFetchResult`
- `fetch_company_financial_indicators_unified(symbol: str, market: ExchangeKind | None = None) -> CompanyFinancialIndicatorFetchResult`
- `fetch_company_income_statements_unified(symbol: str, market: ExchangeKind | None = None) -> CompanyIncomeStatementFetchResult`

说明：公司详情能力需要单独声明 `DataCapability.COMPANY_DETAIL`。

## 返回约束

所有统一接口返回“按能力分型”的结果对象（`KlineFetchResult` / `BasicInfoFetchResult` / `CompanyValuationFetchResult` / `CompanyFinancialIndicatorFetchResult` / `CompanyIncomeStatementFetchResult`），并满足：

- `data_kind` 与能力语义一致。
- `schema_version` 当前固定 `v1`。
- `metadata["count"] == len(payload)`。
- `route_key` 必须映射本次能力与维度。
- `fetch_klines_unified` 的 `payload` 必须按 `KlineRecord.bar_time` 递增排序（从旧到新）。

### K 线时间语义

- `KlineRecord.bar_time` 表示 bar 开始时间，必须与对应周期和市场交易语义对齐。
- `KlineQuery.start_time/end_time` 必须按 UTC 传入，并精确到分钟（秒与微秒必须为 0）。
- provider 内部可按接口规范转换到市场时区发起查询，但响应 `bar_time` 必须统一为 UTC。
- 日线不能补成自然日 `00:00`；若上游仅返回日期，A 股市场（`sse` / `szse`）必须按本地 `09:30` 对齐后再转 UTC。

## 错误约束

- provider 内部可以抛异常。
- 由选择器按优先级顺序尝试可用源并处理切换。
- provider 不直接处理优先级重排。
