# AgentTrader

AgentTrader 是一个面向量化研究与数据服务的单体多模块项目，后端基于 FastAPI，使用 MongoDB + InfluxDB 作为双存储，并提供独立 worker 执行后台同步任务。

本 README 作为项目导览，按“先启动、再理解、再扩展”的顺序组织信息。

## 1. 项目结构速览

```text
AgentTrader/
├─ src/agent_trader/                 # Python 后端主代码
│  ├─ api/                           # FastAPI 路由与依赖
│  ├─ application/                   # 应用层：data access / services / jobs
│  ├─ ingestion/                     # 数据源适配层
│  ├─ storage/                       # Mongo / Influx 连接与仓储
│  ├─ worker/                        # 调度器与后台任务进程入口
│  ├─ core/                          # 配置、日志、时间工具
│  └─ domain/                        # 领域模型
├─ frontend/admin-console/           # 管理台前端（Vue + Vite）
├─ tests/                            # 单元/集成测试
├─ docs/                             # 项目文档（核心文档索引见 docs/README.md）
├─ docker-compose.yml
└─ pyproject.toml
```

## 2. 核心能力

- 统一数据访问入口：`DataAccessGateway`
- 数据源注册与路由：`DataSourceRegistry` + `SourceSelectionAdapter`
- 路由优先级持久化：Mongo `source_priority_routes`
- K 线与基础信息统一输出契约：按 `DataFetchResult` 分型返回
- 独立 worker 调度：按市场执行实时/回补 K 线同步
- 管理台前端：标的列表、详情、监控与 K 线展示

## 3. 本地启动（最短路径）

### 3.1 安装依赖

```bash
uv sync
```

### 3.2 启动依赖服务

```bash
docker compose up -d mongo influxdb
```

### 3.3 启动后端 API

```bash
uv run uvicorn agent_trader.api.main:app --reload
```

默认地址：`http://127.0.0.1:8000`

### 3.4 启动 worker

```bash
uv run python -m agent_trader.worker
```

### 3.5 启动前端管理台

```bash
cd frontend/admin-console
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5174`

## 4. API 导航

### 4.1 健康检查

- `GET /health`

### 4.2 数据接口

- `POST /api/v1/data/klines`
- `POST /api/v1/data/news`
- `POST /api/v1/data/financial-reports`
- `GET /api/v1/data/basic-info`
- `POST /api/v1/data/basic-info/refresh`

### 4.3 数据源路由管理

- `GET /api/v1/data-sources/routes`
- `PATCH /api/v1/data-sources/routes/{route_id}`

### 4.4 标的与图表

- `GET /api/v1/symbols`
- `GET /api/v1/symbols/monitor`
- `GET /api/v1/symbols/{symbol}`
- `GET /api/v1/charts/history`

## 5. 测试与质量检查

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
```

## 6. 配置说明

复制并按环境修改：

- `.env.example`：基础示例配置
- `.env.local`：本地覆盖配置（优先级高于 `.env`）

关键配置项：

- Mongo：`MONGO_DSN`、`MONGO_DATABASE`
- Influx：`INFLUX_URL`、`INFLUX_TOKEN`、`INFLUX_ORG`、`INFLUX_BUCKET`
- 数据源：`TUSHARE_TOKEN`、`TUSHARE_API_URL`
- 同步任务：`SYNC_ENABLED_MARKETS`、`SYNC_REALTIME_M5_INTERVAL_SECONDS`、`SYNC_D1_WINDOW_DAYS`、`SYNC_M5_WINDOW_DAYS`

## 7. 文档入口

核心文档请从 [docs/README.md](docs/README.md) 进入，按架构、数据契约、调度、测试等主题查阅。
