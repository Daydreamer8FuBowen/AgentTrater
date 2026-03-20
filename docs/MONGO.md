# MongoDB 使用指南（开发者）

本文档概述本项目中 MongoDB 的使用方式，包含配置项、连接管理、文档模型（collections）、索引和常用代码示例，帮助开发者快速上手存取数据。

**位置参考**
- `src/agent_trader/core/config.py` — 配置项定义与环境变量映射。[src/agent_trader/core/config.py](src/agent_trader/core/config.py#L1)
- `src/agent_trader/storage/mongo/client.py` — 连接管理与索引初始化。[src/agent_trader/storage/mongo/client.py](src/agent_trader/storage/mongo/client.py#L1)
- `src/agent_trader/storage/mongo/documents.py` — Pydantic 文档模型与集合名称定义。[src/agent_trader/storage/mongo/documents.py](src/agent_trader/storage/mongo/documents.py#L1)
- `src/agent_trader/storage/mongo/schema.py` — 文档注册与索引定义。[src/agent_trader/storage/mongo/schema.py](src/agent_trader/storage/mongo/schema.py#L1)
- `src/agent_trader/storage/mongo/repository.py` — 领域仓库实现示例（task_runs / task_events / task_artifacts）。[src/agent_trader/storage/mongo/repository.py](src/agent_trader/storage/mongo/repository.py#L1)
- `src/agent_trader/storage/mongo/unit_of_work.py` — Mongo 单元工作（UnitOfWork）接口实现。[src/agent_trader/storage/mongo/unit_of_work.py](src/agent_trader/storage/mongo/unit_of_work.py#L1)

## 1. 配置

主要环境变量（在 `.env` 或部署平台注入）：

- `MONGO_DSN`（默认 `mongodb://localhost:27017`）
- `MONGO_DATABASE`（默认 `agent_trader`）
- `MONGO_APP_NAME`（默认 `agent-trader`）

这些变量由 `Settings` 映射为 `MongoConfig`，通过 `get_settings().mongo` 获取。[src/agent_trader/core/config.py](src/agent_trader/core/config.py#L1)

示例 `.env`：

```
MONGO_DSN=mongodb://mongo:27017
MONGO_DATABASE=agent_trader
MONGO_APP_NAME=agent-trader
```

## 2. 连接管理

使用异步 Motor 客户端；入口在 `create_mongo_connection_manager`：

- `MongoConnectionManager` 提供 `client`、`database`、`ping()`、`ensure_indexes()`、`close()`。
-- 在应用启动时调用 `ensure_indexes()` 以创建 schema 中声明的索引（来自 `schema.DOCUMENT_REGISTRY`）。

示例（异步启动）:

```py
from agent_trader.core.config import get_settings
from agent_trader.storage.mongo.client import create_mongo_connection_manager

settings = get_settings()
mgr = create_mongo_connection_manager(settings.mongo)

async def on_startup():
    await mgr.ping()
    await mgr.ensure_indexes()

async def on_shutdown():
    await mgr.close()
```

## 3. 文档模型（Collections）

模型定义在 `documents.py`，每个类声明了 `collection_name`、`primary_key`、和 JSON / 可编辑字段。

主要集合（非穷尽）及用途：

- `agent_definitions` — 代理（Agent）定义与元数据（主键 `agent_id`）。
- `skill_definitions`, `skill_versions` — 技能定义与版本管理。
- `agent_releases`, `agent_release_pointers` — 发布的代理版本与指针。
- `task_runs` — 任务运行信息（状态、执行、结果）。
- `task_events` — 任务执行过程中的事件流。
- `task_artifacts` — 任务生成的产物（日志、文件、序列化对象）。

查看详细字段声明：`src/agent_trader/storage/mongo/documents.py`。[src/agent_trader/storage/mongo/documents.py](src/agent_trader/storage/mongo/documents.py#L1)

## 4. 索引与 Schema 注册

索引在 `schema.py` 的 `DOCUMENT_REGISTRY` 中声明，`MongoConnectionManager.ensure_indexes()` 会为每个注册文档创建索引。建议在应用首次启动或迁移时运行一次 `ensure_indexes()`。

示例（查看索引）:

```py
from agent_trader.storage.mongo.schema import DOCUMENT_REGISTRY

for name, cfg in DOCUMENT_REGISTRY.items():
    print(name, cfg.indexes)
```

## 5. 仓库（Repository）与工作单元（UnitOfWork）

- `MongoTaskRunRepository` / `MongoTaskEventRepository` / `MongoTaskArtifactRepository`：提供增删改查等基本操作，位于 `repository.py`。[src/agent_trader/storage/mongo/repository.py](src/agent_trader/storage/mongo/repository.py#L1)
- `MongoUnitOfWork`：将上述仓库聚合为单元工作接口，注意部分仓库（candidates / memories / signals / candles）在 Mongo 实现中被标记为未支持或由其它存储（如 Influx）负责。[src/agent_trader/storage/mongo/unit_of_work.py](src/agent_trader/storage/mongo/unit_of_work.py#L1)

使用示例（直接使用仓库）：

```py
from agent_trader.storage.mongo.repository import MongoTaskRunRepository

async def create_run(db, run_payload):
    repo = MongoTaskRunRepository(db)
    saved = await repo.add(run_payload)
    return saved
```

或通过 `MongoUnitOfWork` 聚合使用。

## 6. 常见操作示例

1) 新增 TaskRun（示例）

```py
from agent_trader.storage.mongo.client import create_mongo_connection_manager
from agent_trader.core.config import get_settings
from agent_trader.storage.mongo.documents import TaskRunDocument

settings = get_settings()
mgr = create_mongo_connection_manager(settings.mongo)

async def add_run_example():
    db = mgr.database
    run = TaskRunDocument(task_kind="research", context={"symbol": "000001.SZ"})
    from agent_trader.storage.mongo.repository import MongoTaskRunRepository
    repo = MongoTaskRunRepository(db)
    await repo.add(run)

```

2) 写入事件与产物

```py
from agent_trader.storage.mongo.documents import TaskEventDocument, TaskArtifactDocument

event = TaskEventDocument(run_id="run_xxx", seq=1, event_type="started")
artifact = TaskArtifactDocument(run_id="run_xxx", artifact_type="log", content={"text": "..."})

await MongoTaskEventRepository(db).add(event)
await MongoTaskArtifactRepository(db).add(artifact)
```

## 7. 测试与本地开发

- 在本地可以使用 Docker Compose 启动 Mongo：若项目提供 `docker-compose.yml`，可在其中加入 Mongo 服务并启动。
- 单元测试中可能使用内存或测试用数据库；查看 `tests/unit/storage/test_storage_clients.py` 了解测试用例如何配置数据库客户端。

## 8. 注意事项与故障排查

- 索引未创建：确认在应用启动时执行了 `ensure_indexes()`，或手动在 Mongo Shell 中检查 `db.collection.getIndexes()`。
- 数据模型变更：Pydantic 模型字段变更可能导致旧文档不兼容，考虑在迁移脚本中逐步转换旧数据。
- 连接问题：检查 `MONGO_DSN`（认证、网络、防火墙、用户名/密码、replica set 参数等）。

---

如果你希望我把這份文檔擴展為英文版、或將示例改寫為同步阻塞調用（非 async）、或添加遷移腳本範例，我可以繼續補充。
