# 开发规范

## 核心开发准则（最高优先级）

1. **不发明架构**：严格沿用现有单体多模块与分层；不新建一套DDD/新目录体系。
2. **最小侵入**：只改实现需求所需文件；禁止顺手重构/全文件格式化/升级依赖。
3. **禁止循环依赖**：模块依赖保持单向；跨模块且有循环风险时，应抽取 `*-api`（接口+DTO）或通过 `Protocol` 解耦。
4. **契约优先**：修改或新增 API 必须明确 URL、ReqVO/RespVO 等，枚举必须归档（如 `ExchangeKind`）。
5. **先搜再写**：遇到不确定的约定（如字典常量、类型定义）必须先在仓库搜索，对齐既有实现。

---

## 目录与边界

### 各层职责

| 目录 | 职责 | 禁止行为 |
|---|---|---|
| `api/` | 协议转换、依赖注入、HTTP 路由 | 直接依赖 provider；包含业务逻辑 |
| `application/services/` | 查询型 application service（聚合、查询、编排） | 直接操作 Influx/Mongo 连接；调度任务 |
| `application/jobs/` | 后台 job 领域逻辑（同步、回补、tiered symbol 管理） | 直接发起 HTTP 请求；持有 scheduler 引用 |
| `application/data_access/` | 路由与网关编排（`DataAccessGateway`、`SourceSelectionAdapter`） | 包含业务规则；直接写存储 |
| `ingestion/models.py` | 数据契约中心，查询/路由/结果模型 | 引入任何框架依赖 |
| `ingestion/sources/` | provider 适配层（`*Source` 类） | 直接操作 Mongo 优先级仓储 |
| `storage/` | 持久化与连接管理（Mongo/Influx） | 包含路由/调度逻辑 |
| `worker/` | 调度器注册、连接生命周期、进程入口 | 包含 job 领域逻辑（移至 `application/jobs/`） |
| `domain/` | 纯领域模型（`Candle`、`BarInterval` 等），无外部依赖 | 引入框架或基础设施依赖 |
| `core/` | 跨层基础设施（`Settings`、`logging`） | 依赖任何业务层 |

### `application/services/` 与 `application/jobs/` 的区别

- **`services/`**：面向"查询/读取/聚合"——被 API 路由调用，生命周期与 HTTP 请求绑定。  
  例：`BasicInfoAggregationService`、`SymbolQueryService`
- **`jobs/`**：面向"后台定期执行"——被 `worker/factory.py` 组装，生命周期与 scheduler 绑定。  
  例：`KlineSyncService`、`TierCollectionService`

禁止跨层绕行：

- API 不直接依赖 provider。
- provider 不直接操作 Mongo 优先级仓储。
- `worker/jobs.py` 不包含 job 领域逻辑，只负责调度注册与时段守卫。

---

## 命名规则

| 类型 | 命名模式 | 示例 |
|---|---|---|
| Provider 类 | `<Name>Source` | `BaoStockSource`、`TuShareSource` |
| Application service | `<Domain>Service` | `BasicInfoAggregationService` |
| Application job | `<Domain>SyncService` / `<Domain>Job` | `KlineSyncService` |
| Repo 类 | `<Name>Repository` | `InfluxCandleRepository`、`MongoSourcePriorityRepository` |
| 连接管理器 | `<Name>ConnectionManager` | `InfluxConnectionManager`、`MongoConnectionManager` |
| 查询模型 | `<Domain>Query` | `KlineQuery` |
| 路由键 | `DataRouteKey` | — |
| 统一方法名 | `fetch_<domain>` | `fetch_klines`、`fetch_basic_info` |
| 返回模型 | 按能力分型 | `KlineFetchResult`、`BasicInfoFetchResult`、`NewsFetchResult`、`FinancialReportFetchResult` |

---

## 数据规范

- 输出必须遵循 `UNIFIED_SOURCE_PAYLOAD_SPEC.md`。
- 统一字段必须在 source 适配层完成映射，不允许将 provider 原生字段直接暴露给上层。
- **市场标识必须使用 `ExchangeKind` 枚举**：项目中所有涉及市场（market）传递的地方，必须使用 `agent_trader.domain.models.ExchangeKind` 枚举，严禁使用原生字符串（如 `"sh"`, `"sz"`, `"sse"` 等）。数据源接入时需在最外层完成标准化转换。
- **状态字段（status）标准化**：系统内部对于标的上市状态（`status`）统一使用字符串 `'0'`（非活跃/退市）和 `'1'`（活跃/上市）表示。数据源接入时需在适配层完成标准化转换。
- 所有**管理类时间**（创建时间、更新时间、同步状态时间、回补进度时间、任务运行时间）统一使用 **UTC**。
- 后端内部禁止传播 naive `datetime`；新代码默认使用 UTC-aware `datetime`。
- 市场时区仅用于两类边界转换：
   - **数据抓取边界**：例如 A 股 09:30/11:30/13:00/15:00 的交易时段判断、5m bar 对齐。
   - **页面显示边界**：前端收到 UTC `Z` 字符串后，再按浏览器本地时区格式化显示。
- API 对外返回时间时，统一序列化为 **UTC ISO 8601**，并使用 `Z` 结尾，例如 `2026-03-26T05:00:00Z`。
- K 线数据写入 InfluxDB 的固定位置：
  - **org**：`INFLUX_ORG`（默认 `"agent-trader"`）
  - **bucket**：`INFLUX_BUCKET`（默认 `"market-data"`）
  - **measurement**：硬编码 `"candles"`
  - **tags**：`symbol`、`interval`、`asset_class`、`exchange`、`adjusted`、`source`
  - **fields**：`open`、`high`、`low`、`close`、`volume`、`turnover?`、`trade_count?`
  - **time precision**：秒级（`WritePrecision.S`），使用 `Candle.open_time` 作为唯一时间索引
  - **time 语义**：只存储 `open_time`（K线开始时间，UTC aware）。`close_time` 由应用层通过 `get_bar_close_time(open_time, interval)` 计算得出
- `basic_info` 路由归属 `DataCapability.KLINE`（`interval=None`），不单独设路由键。

### 时间处理约定

- `core/time.py` 是统一时间工具入口；新增时间转换逻辑优先放这里，不要在业务代码里散落写 `tzinfo`/`ZoneInfo`/`astimezone`。
- source 适配层负责把 provider 返回的时间转换为 UTC-aware `datetime`：
   - K 线时间：按 provider 所属市场本地时间解释，再转换到 UTC。
   - 基础信息/财报/公告等自然日字段：统一转成 UTC-aware 日期时间对象。
- `worker/jobs.py` 与 `application/jobs/kline_sync.py` 内部使用 UTC 当前时间；交易所时段判断必须先转换到市场时区后再判断。
- Mongo 与 Influx 仓储层只接收和写入 UTC 时间，不负责业务层时区推断。

---

## 路由策略规范

- 失败源必须降级到队尾（持久化到 Mongo `source_priority_routes`）。
- 重排必须持久化到 Mongo；默认路由仅补齐，不覆盖人工配置。

---

## Worker / 调度规范

### 代码落点

| 文件 | 职责 |
|---|---|
| `worker/factory.py` | 构造调度器；组装 `KlineSyncService` 及其依赖 |
| `worker/jobs.py` | **仅**注册调度任务与交易时段守卫（`_should_run_*`） |
| `worker/runtime.py` | 连接生命周期、调度器启动/停止、优雅退出 |
| `application/jobs/kline_sync.py` | K 线同步全部领域逻辑（tiered symbol 分类、fetch、zero-fill、回补） |

### 调度任务注册约定

```python
scheduler.add_job(
    _run_xxx,
    "interval",
    seconds=...,
    kwargs={...},
    id="unique_job_id",       # 必须稳定且唯一
    replace_existing=True,    # 重启后覆盖旧定义
    max_instances=1,          # 防止任务重叠
    coalesce=True,            # 积压合并，防回补风暴
)
```

### 任务函数约定

- 必须为 `async def`。
- 每个任务只负责一个明确职责。
- 必须做异常捕获并记录日志，不让未处理异常导致调度器退出。
- worker 进程独立运行，不在 `uvicorn --workers N` 的 API 进程中启动调度器。

---

## 配置规范

- 所有配置通过 `Settings`（`core/config.py`）集中管理，对应环境变量全部在 `Settings` 中声明 `alias`。
- 子配置（`InfluxConfig`、`WorkerConfig`、`KlineSyncConfig` 等）为 frozen `BaseModel`，只通过 `settings.*` 属性访问。
- 本地开发覆盖使用 `.env.local`（优先于 `.env`）。
- `get_settings()` 使用 `@lru_cache` 在进程内单例复用，不允许在业务代码中直接实例化 `Settings()`。

---

## 测试规范

至少覆盖：

1. **契约测试**
   - 能力声明完整性
   - payload 字段一致性

2. **网关测试**
   - 优先级命中
   - 失败切换与重排

3. **Job 单元测试**（`tests/unit/application/`）
   - 使用内存 UoW 替代真实数据库
   - 使用 `_fake_now_provider` 注入固定时间
   - 覆盖：实时同步、零填充、回补分块、tiered symbol 分类
   - 涉及时间断言时，统一使用 UTC-aware `datetime`

4. **Worker 单元测试**（`tests/unit/worker/`）
   - 交易时段守卫的所有边界（开盘/收盘/午休/周末）
   - 调度注册完整性
   - A 股时段测试使用 UTC 输入，验证内部按市场时区换算后的行为

5. **集成测试**（`tests/integration/`）
   - 真实源调用（可按环境变量 `SKIP_REAL_SOURCE_TESTS` 跳过）

6. **端到端时间链路测试**
   - 至少覆盖一次“抓取 -> 聚合 -> API -> 页面显示契约”
   - API 响应中的时间字段必须断言为 UTC `Z` 字符串

---

## 变更准入

涉及以下任一项时，必须同步更新**文档与测试**：

- `DataRouteKey` 结构
- 任一分型结果对象字段
- 任一能力的 payload 必填字段
- provider 能力声明
- InfluxDB measurement schema（tags / fields / precision）
- 时间序列化契约（UTC / `Z` 字符串 / 市场时区边界）
- `KlineSyncConfig` 新增配置项
- `application/jobs/` 或 `application/services/` 的分层边界调整
