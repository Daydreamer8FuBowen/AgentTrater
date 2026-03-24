# 架构总览（数据层）

本版本不再采用 Event 驱动的数据处理链路，核心目标是统一多数据源的数据能力访问。

## 目标

- 能力分块：K 线、新闻、财务。
- 统一输出：不同 provider 输出同一 payload 结构。
- 动态路由：Mongo 管理优先级，失败自动降级。
- 外部无感：业务只依赖网关，不感知 provider 细节。

## 模块分层

- `ingestion/models.py`
  - 查询模型、路由键、统一返回模型。

- `ingestion/sources/*`
  - provider 适配层。
  - 各 provider 完成 provider-native -> unified payload 的转换。

- `application/data_access/gateway.py`
  - 注册表、选择器、统一网关。

- `storage/mongo/repository.py`
  - 优先级路由持久化。

- `api/routes/data.py`
  - 对外数据 API。

## 请求路径

1. 外部调用 `/api/v1/data/*`。
2. API 将请求转换为统一 Query。
3. `DataAccessGateway` 构造 `DataRouteKey`。
4. `SourceSelectionAdapter` 获取优先级并尝试 provider。
5. provider 返回按能力分型的结果对象（统一 schema）。
6. API 序列化返回。

> 说明：当前返回模型已升级为“按能力分型结果对象”，即
> `KlineFetchResult` / `BasicInfoFetchResult` / `NewsFetchResult` / `FinancialReportFetchResult`。
> 其中 `basic_info` 仍归属 `DataCapability.KLINE` 的路由域（`interval=None`）。

## 非目标

以下内容已从主链路移除：

- `RawEvent` / `NormalizedEvent` / `ResearchTrigger`
- Trigger API 与 TriggerService
- data_fetch 模块
- ingestion normalizers
