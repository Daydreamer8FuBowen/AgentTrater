# AgentTrader

统一多数据源量化数据后端，基于 FastAPI + MongoDB + InfluxDB。

当前版本采用能力分块的数据架构：

- K 线能力（`kline`）
- 新闻能力（`news`）
- 财务能力（`financial_report`）

每个数据源按能力声明并实现统一方法，外部调用统一走 `DataAccessGateway`，无须感知具体命中哪个数据源。

## 架构要点

- 统一访问入口：`DataAccessGateway`
- 数据源注册：`DataSourceRegistry`
- 动态选源与故障降级：`SourceSelectionAdapter`
- 优先级持久化：Mongo 集合 `source_priority_routes`
- 分型返回模型：`KlineFetchResult` / `BasicInfoFetchResult` / `NewsFetchResult` / `FinancialReportFetchResult`

失败处理策略：

- 某源失败后，按当前路由将其降级到优先级队尾并持久化。
- 同一次请求继续尝试下一个源。
- 全部失败时抛出错误。

## API

当前公开数据接口：

- `POST /api/v1/data/klines`
- `POST /api/v1/data/news`
- `POST /api/v1/data/financial-reports`
- `GET /api/v1/data/basic-info`
- `GET /health`

## 开发

```bash
uv sync
uv run uvicorn agent_trader.api.main:app --reload
```

本地依赖服务：

```bash
docker compose up -d mongo influxdb
```

运行测试：

```bash
uv run pytest -q
```

## 文档

- `docs/ARCHITECTURE.md`
- `docs/DATASOURCE.md`
- `docs/SOURCE_CAPABILITY_CONTRACTS.md`
- `docs/UNIFIED_SOURCE_PAYLOAD_SPEC.md`
- `docs/DEVELOPMENT_CONVENTIONS.md`
- `docs/REAL_DATA_SOURCE_TESTING.md`
- `docs/SCHEDULER_DEVELOPMENT.md`
