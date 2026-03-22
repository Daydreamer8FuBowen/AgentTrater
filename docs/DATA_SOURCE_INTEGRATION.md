数据源集成与路由（开发指南）

概述
----
本指南描述如何在 AgentTrader 中接入新的行情/新闻/财报等数据源，并说明统一能力接口、Mongo 优先级路由与运行时选择器的使用方式。该框架只负责“选择与路由/策略”，实际抓取与写入由各数据源实现，入库（Influx/Mongo）由后续实现决定。

目标
----
- 定义统一的数据能力接口（K线、新闻、财报）。
- 通过 Mongo 管理每种路由（capability+market+interval+mode）的优先级链。
- 提供运行时选择器：按优先级顺序尝试数据源，失败降级 / 熔断 / 成功晋升。
- 提供调度框架：健康检测与优先级维护任务（仅框架）。

代码位置（快速索引）
-----------------
- 能力模型与请求/响应类型：
  - src/agent_trader/ingestion/models.py
- 数据源协议（协议层）：
  - src/agent_trader/ingestion/sources/base.py
- 路由优先级与状态文档：
  - src/agent_trader/storage/mongo/documents.py
  - src/agent_trader/storage/mongo/schema.py
- 仓储实现（优先级 / 健康）：
  - src/agent_trader/storage/mongo/repository.py
- 统一网关与选择器：
  - src/agent_trader/application/services/data_source_gateway.py
- 配置项与 DI：
  - src/agent_trader/core/config.py
  - src/agent_trader/api/dependencies.py
- 调度任务骨架：
  - src/agent_trader/worker/main.py
  - src/agent_trader/api/main.py (lifespan 中启动调度器)
- 单元测试样例：
  - tests/unit/application/test_data_source_gateway.py

核心概念（摘要）
----------------
1. DataCapability: kline / news / financial_report
2. FetchMode: realtime / history / incremental
3. DataRouteKey: (capability, mode, market?, interval?)，并提供 `as_storage_key()` 用作 Mongo 的 route_id。
4. SourcePriorityRouteDocument: 存储 route 对应的优先级源列表（字段：route_id, priorities, enabled, metadata）。
5. SourceRouteHealthDocument: 存储每个 route+source 的运行健康信息（成功/失败计数、熔断信息、下一次重试时间等）。
6. SourceSelectionAdapter: 读取优先级链依次调用 provider，失败时记录并可能熔断，低优源成功可晋级。
7. DataAccessGateway: 统一门面，业务方通过它调用数据能力（比如 fetch_klines），不直接依赖具体 provider。

如何实现并接入一个新数据源（步骤）
---------------------------
1. 实现能力协议（选其一或多个）：
   - K线能力：实现 `fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult`。
   - 新闻能力：实现 `fetch_news_unified(self, query: NewsQuery) -> SourceFetchResult`。
   - 财报能力：实现 `fetch_financial_reports_unified(self, query: FinancialReportQuery) -> SourceFetchResult`。

   注意：方法应为 async，并返回 `SourceFetchResult`，其中 `payload` 为原始条目列表（dict）。

   示例（伪代码）
   ```py
   class MyTuShareProvider:
       name = "tushare"

       async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:
           # 使用 tushare 客户端拉取，转换为统一 payload
           rows = await ...
           return SourceFetchResult(source=self.name, route_key=..., payload=[...])
   ```

2. 注册 provider：在应用启动阶段（或通过依赖注入位置）将 provider 注册到 `DataSourceRegistry`：
   - 在 `FastAPI` lifespan 或 `api/dependencies.get_source_registry` 的位置调用 `registry.register(provider)`。

   示例：
   ```py
   from agent_trader.application.services.data_source_gateway import DataSourceRegistry

   registry = DataSourceRegistry()
   registry.register(MyTuShareProvider())
   app.state.source_registry = registry
   ```

3. 配置路由优先级（Mongo）：
   - 使用 `UnitOfWork.source_priorities.upsert(route_key, priorities=[...])` 初始化或修改某个 route 的优先级链。
   - route_key 请使用 `DataRouteKey(...).as_storage_key()` 或通过 `SourcePriorityRepository.upsert` 传入 `DataRouteKey`（仓储支持直接接受 DataRouteKey）。

   示例（伪代码）
   ```py
   route_key = DataRouteKey(capability=DataCapability.KLINE, mode=FetchMode.REALTIME, market=ExchangeKind.SSE, interval=BarInterval.M5)
   await uow.source_priorities.upsert(route_key, priorities=["tushare", "backup"])
   ```

4. 配置健康/策略参数：
   - 通过环境变量或 `Settings.data_routing` 设置如下项：
     - `DATA_ROUTING_FAILURE_THRESHOLD`（连续失败阈值）
     - `DATA_ROUTING_CIRCUIT_OPEN_SECONDS`（熔断持续秒数）
     - `DATA_ROUTING_PROMOTION_STEP`（成功晋升步长）
     - `DATA_ROUTING_PROMOTE_ON_SUCCESS`（是否在成功时尝试晋升）

5. 使用 Gateway 拉取数据（业务侧示例）：
   - 从依赖注入中获取 `DataAccessGateway`，然后调用 `fetch_klines(query)` / `fetch_news(query)`。

   ```py
   gateway: DataAccessGateway = Depends(get_data_access_gateway)
   result = await gateway.fetch_klines(query)
   ```

调试与测试
---------
- 本仓库包含 `tests/unit/application/test_data_source_gateway.py`，演示了：
  - 当首选源失败时，降级到后备源并在成功后晋升到高优先级；
  - 熔断在达到失败阈值后生效。

- 运行示例测试（仅针对本功能）：

```bash
uv run pytest tests/unit/application/test_data_source_gateway.py -q
```

运维注意事项
-----------
- 优先级配置保存在 Mongo，建议管理员页面或运维脚本维护这些记录，并对关键路由添加监控告警。
- 熔断与晋升机制会改变优先级链，请确保有审计或变更记录以便追踪异常波动。
- 对接外部数据源时，请关注 API 限流策略，必要时在 provider 内部实现本地限流/退避。

FAQ
---
Q: 我能直接在业务里 new 某个 provider 并调用吗？
A: 请不要直接引用具体 provider，始终通过 `DataAccessGateway`。直接依赖具体 provider 会绕开优先级策略与健康检查，导致路由不可观测。

Q: 我实现了 provider，但想强制测试优先级变化怎么做？
A: 在测试中使用内存实现的 `SourcePriorityRepository` / `SourceRouteHealthRepository`（参见 `tests/unit/application/test_data_source_gateway.py`），并注册若干模拟 provider。

最后
---
如需我把示例 provider 或快速 CLI 管理脚本（用于初始化 route 优先级）也加入到仓库，请回复我将继续实现。