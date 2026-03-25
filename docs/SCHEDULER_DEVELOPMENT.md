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
- 项目已有 `worker/factory.py`、`worker/jobs.py`、`worker/runtime.py`，便于分层扩展。
- 若在 `uvicorn --workers N` 的 API 进程中直接启调度器，容易出现同一任务被执行 N 次。

## 2. 代码落点

建议按以下边界组织：

- `src/agent_trader/worker/factory.py`
  - 构造调度器、组装 `KlineSyncService` 依赖。
- `src/agent_trader/worker/jobs.py`
  - 注册任务与交易时段判断（实时/回补守卫）。
- `src/agent_trader/worker/runtime.py`
  - 连接生命周期、调度器启动/停止、优雅退出。
- `src/agent_trader/worker/main.py`
  - 兼容入口与对外导出。
- `src/agent_trader/core/config.py`
  - 时区配置（`WorkerConfig`）与同步任务配置（`KlineSyncConfig`）。
- `src/agent_trader/storage/connection_manager.py`
  - 复用连接生命周期管理，避免任务中直接 new 连接。

## 3. 标准实现步骤

### 步骤 1：实现任务函数（`jobs.py`）

规则：

- 优先使用 `async def`。
- 每个任务只负责一个明确职责。
- 必须做异常捕获并记录日志，不让异常导致调度器退出。

示例（交易时段守卫）：

```python
from datetime import datetime

def _should_run_realtime(market: str, now: datetime | None = None) -> bool:
  now_value = now or datetime.now()
  return _is_market_trading_time(market, now_value)


def _should_run_backfill(market: str, now: datetime | None = None) -> bool:
  now_value = now or datetime.now()
  return not _is_market_trading_time(market, now_value)
```

### 步骤 2：注册任务（`jobs.py`）

核心 API：

```python
scheduler.add_job(
  _run_realtime_positions,
  "interval",
  seconds=sync_config.realtime_m5_interval_seconds,
  kwargs={"service_factory": service_factory, "market": market},
  id=f"realtime_m5_positions_{market}",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

参数建议：

- `id`：必须稳定唯一，便于管理。
- `replace_existing=True`：重复启动时覆盖旧任务定义。
- `max_instances=1`：避免任务重叠并发。
- `coalesce=True`：积压触发合并为一次，防止补偿风暴。
- 可按任务特性补充 `misfire_grace_time`。

### 步骤 3：启动与优雅关闭

- 启动顺序建议：初始化配置与连接 -> 注册任务 -> `scheduler.start()`。
- 关闭顺序建议：先停 scheduler，再关闭数据库连接。

示例：

当前实现中，任务由 `register_kline_sync_jobs(...)` 统一注册，包含：

- 实时 5m 持仓同步
- 实时 5m 候选同步
- 每日 D1 同步
- 非交易时段 D1 回补
- 非交易时段 M5 回补

## 4. 与 FastAPI 生命周期的关系

### 生产建议

- API 服务只处理请求，不承担核心定时调度。
- 调度器放在独立 worker 进程（可由容器编排单独拉起）。

### 本地调试建议

- 可临时挂在 FastAPI `lifespan` 中验证任务逻辑。
- 但上线前应迁移回独立 worker，避免多实例重复执行。

## 5. 配置规范

沿用 `WorkerConfig` 与 `KlineSyncConfig`：

- `WORKER_TIMEZONE`
- `SYNC_ENABLED_MARKETS`
- `SYNC_D1_WINDOW_DAYS`
- `SYNC_M5_WINDOW_DAYS`
- `SYNC_REALTIME_M5_INTERVAL_SECONDS`
- `SYNC_D1_SYNC_HOUR`
- `SYNC_BACKFILL_BATCH_SYMBOLS`
- `SYNC_M5_BACKFILL_CHUNK_DAYS`

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
