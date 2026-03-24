# 定时任务开发指南（推荐方案）

本文档给出 AgentTrader 中定时任务的推荐实现方式，目标是：

- 与当前项目架构一致（FastAPI + 独立 worker 模块）。
- 可配置、可观测、可优雅停止。
- 避免多进程部署下重复执行任务。

## 1. 适用架构与推荐结论

### 推荐结论

本项目推荐使用：

- `APScheduler` 的 `AsyncIOScheduler` 作为调度器。
- `async def` 任务函数作为执行单元。
- 将调度器运行在独立 worker 进程，而不是 API 多 worker 进程中。

### 为什么这样做

- 项目已有 `apscheduler` 依赖与 `worker` 配置项。
- 项目已有 `worker/main.py` 的调度器工厂函数，便于扩展。
- 若在 `uvicorn --workers N` 的 API 进程中直接启调度器，容易出现同一任务被执行 N 次。

## 2. 代码落点

建议按以下边界组织：

- `src/agent_trader/worker/main.py`
  - 创建调度器、注册任务、启动与关闭。
- `src/agent_trader/worker/tasks.py`
  - 具体任务函数（如 `ingestion_job`、`refresh_candidates_job`）。
- `src/agent_trader/core/config.py`
  - 任务间隔与时区配置（`WorkerConfig`）。
- `src/agent_trader/storage/connection_manager.py`
  - 复用连接生命周期管理，避免任务中直接 new 连接。

## 3. 标准实现步骤

### 步骤 1：实现任务函数（`tasks.py`）

规则：

- 优先使用 `async def`。
- 每个任务只负责一个明确职责。
- 必须做异常捕获并记录日志，不让异常导致调度器退出。

示例：

```python
import logging

logger = logging.getLogger(__name__)


async def ingestion_job(*, gateway) -> None:
    try:
        logger.info("ingestion_job start")
        # TODO: 调用网关拉取并落库
        logger.info("ingestion_job done")
    except Exception:
        logger.exception("ingestion_job failed")
```

### 步骤 2：注册任务（`main.py`）

核心 API：

```python
scheduler.add_job(
    ingestion_job,
    trigger=IntervalTrigger(seconds=config.ingestion_interval_seconds, timezone=tz),
    kwargs={"gateway": gateway},
    id="ingestion",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60,
)
```

参数建议：

- `id`：必须稳定唯一，便于管理。
- `replace_existing=True`：重复启动时覆盖旧任务定义。
- `max_instances=1`：避免任务重叠并发。
- `coalesce=True`：积压触发合并为一次，防止补偿风暴。
- `misfire_grace_time`：允许短暂错过触发后补执行。

### 步骤 3：启动与优雅关闭

- 启动顺序建议：初始化配置与连接 -> 注册任务 -> `scheduler.start()`。
- 关闭顺序建议：先停 scheduler，再关闭数据库连接。

示例：

```python
from zoneinfo import ZoneInfo
from apscheduler.triggers.interval import IntervalTrigger


def register_jobs(scheduler, config, gateway):
    tz = ZoneInfo(config.timezone)

    scheduler.add_job(
        ingestion_job,
        trigger=IntervalTrigger(seconds=config.ingestion_interval_seconds, timezone=tz),
        kwargs={"gateway": gateway},
        id="ingestion",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
```

## 4. 与 FastAPI 生命周期的关系

### 生产建议

- API 服务只处理请求，不承担核心定时调度。
- 调度器放在独立 worker 进程（可由容器编排单独拉起）。

### 本地调试建议

- 可临时挂在 FastAPI `lifespan` 中验证任务逻辑。
- 但上线前应迁移回独立 worker，避免多实例重复执行。

## 5. 配置规范

沿用 `WorkerConfig`：

- `WORKER_TIMEZONE`
- `WORKER_INGESTION_INTERVAL_SECONDS`
- `WORKER_CANDIDATE_REFRESH_SECONDS`
- `WORKER_BACKTEST_INTERVAL_SECONDS`

建议：

- 本地调试可设短间隔（如 10~30 秒）。
- 生产环境使用分钟级以上，并结合任务耗时评估。

## 6. 并发与可靠性约束

- 不要在 job 中维护跨执行全局可变状态。
- 对同一业务对象写入时保证幂等（可重试不重复污染数据）。
- 长耗时或高失败率任务，建议调度器仅“触发入队”，由专用消费 worker 执行。
- 多实例部署下，如果不能保证只有一个 scheduler 实例，请增加分布式锁。

## 7. 观测与排障

至少记录以下日志字段：

- `job_id`
- `scheduled_time`
- `start_time`
- `duration_ms`
- `status`（success/failed）
- `error`（失败时）

建议增加健康检查：

- 暴露最近一次任务执行时间与状态（可用于告警）。

## 8. 常见反模式

- 在 API 多 worker 进程内直接启动同一调度器。
- 任务函数抛异常但不捕获，导致调度器状态不可控。
- 间隔配置与任务耗时不匹配，造成长期堆积。
- 直接使用原生线程执行异步 I/O 任务（优先 `asyncio` 方案）。

## 9. 最小落地清单

上线前至少完成：

1. 任务函数可重复执行且幂等。
2. 每个任务有稳定 `job_id` 与日志。
3. 任务间隔来自配置，不硬编码。
4. 启停路径验证通过（启动能注册，关闭能优雅退出）。
5. 多实例部署策略明确（单实例或分布式锁）。
