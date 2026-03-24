# 数据源能力契约

本文档定义 provider 必须实现的最小契约。

## 基础要求

每个 provider 必须具备：

- `name: str`
- `capabilities() -> list[SourceCapabilitySpec]`

`capabilities()` 用于声明该 provider 支持哪些能力、市场、周期。

## 能力接口

### K 线能力

- `fetch_klines_unified(query: KlineQuery) -> KlineFetchResult`
- `fetch_basic_info(market: ExchangeKind | None = None) -> BasicInfoFetchResult`

说明：`basic_info` 与 K 线能力绑定，不单独声明 capability。

### 新闻能力

- `fetch_news_unified(query: NewsQuery) -> NewsFetchResult`

### 财务能力

- `fetch_financial_reports_unified(query: FinancialReportQuery) -> FinancialReportFetchResult`

## 返回约束

所有统一接口返回“按能力分型”的结果对象（`KlineFetchResult` / `BasicInfoFetchResult` / `NewsFetchResult` / `FinancialReportFetchResult`），并满足：

- `data_kind` 与能力语义一致。
- `schema_version` 当前固定 `v1`。
- `metadata["count"] == len(payload)`。
- `route_key` 必须映射本次能力与维度。

## 错误约束

- provider 内部可以抛异常。
- 由选择器统一处理降级与切换。
- provider 不直接处理优先级重排。
