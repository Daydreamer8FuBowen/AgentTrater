# 数据源开发指南

本文档说明项目中数据源路由的设计、如何添加数据提供者、路由优先级的存储模式，以及请求失败时的处理策略。

**图片**
- 概览图： [docs/ppt_overall.png](docs/ppt_overall.png)
- 请求流程： [docs/ppt_sequence.png](docs/ppt_sequence.png)
- 核心数据模型： [docs/ppt_model.png](docs/ppt_model.png)

**快速概述**
- 业务代码通过统一门面 `DataAccessGateway` 发起数据请求（K 线、新闻、财报等）。
- `DataAccessGateway` 构造一个 `DataRouteKey`，并将执行委托给 `SourceSelectionAdapter.execute(route_key, invoker)`。
- `SourceSelectionAdapter` 会首先查询 `SourcePriorityRepository`（Mongo）以获取按优先级排序的提供者名单；若无存储记录则按 `DataSourceRegistry` 的注册顺序使用提供者列表。
- 适配器按优先顺序通过 `invoker(source_name, provider)` 回调调用提供者，首次成功的结果会立即返回给调用方。
- 当某个提供者调用失败时，适配器会在该路由的优先级列表中将该提供者降至末尾（持久化的重排），并继续尝试下一个提供者；系统不做自动重试或后台健康探测。

**路由键格式**
- `DataRouteKey` 字段：
  - `capability`：枚举 `DataCapability`（例如 KLINE、NEWS、FINANCIAL_REPORT 等）
  - `market`：交易市场标识（如 `SH`、`SZ` 等）
  - `interval`：时间周期字符串或空（例如 `1m`、`5m`），用于 KLINE 能力
- 存储键：`DataRouteKey.as_storage_key()` 返回用于仓库索引的规范字符串，例如 `KLINE:SH:1m`。

**优先级存储模式**
- Mongo 集合文档示例字段：
  - `route_key`（字符串，唯一索引）
  - `priorities`（字符串数组）— 按顺序的提供者名称
  - `enabled`（布尔）— 若为 false，系统回退使用注册顺序
- 仓库接口（`SourceSelectionAdapter` 使用）：
  - `get(route_key) -> SourcePriorityRouteDocument | None`
  - `upsert(route_key, priorities, enabled=True)`
  - `reorder(route_key, priorities)`

**提供者接口（适配器契约）**
- 提供者需暴露统一的异步方法，供 `invoker` 调用：
  - `fetch_klines_unified(query: KlineQuery) -> SourceFetchResult`
  - `fetch_news_unified(query: NewsQuery) -> SourceFetchResult`
  - `fetch_financial_reports_unified(query: FinancialReportQuery) -> SourceFetchResult`
- 提供者应包含用于注册的 `name` 属性（字符串）。
- 在注册表中使用 `DataSourceRegistry.register(provider, name=...)` 注册提供者。
- 使用 `DataSourceRegistry.names()` 可按注册顺序枚举提供者名称。

**失败处理与降级策略**
- 在请求路径中遇到提供者异常时：
  1. `SourceSelectionAdapter` 会调用仓库的 `reorder()` 或 `upsert()`，将失败的提供者移动到对应 `route_key` 的 `priorities` 列表末尾。
  2. 适配器记录警告日志并立即继续调用下一个提供者。
  3. 若所有提供者都失败，适配器会以最后一个异常为原因向上抛出 `RuntimeError`。
- 设计理由：行为简单、可观测；不依赖后台健康检查或复杂的重试计数器，运维人员可通过查看 `SourcePriorityRouteDocument` 观察顺序变化。

**启动引导（bootstrap）**
- 应用的生命周期启动阶段可通过遍历各提供者的 `capabilities()` 与注册顺序，生成默认的 `SourcePriorityRouteDocument` 条目并写入数据库。
- 当前仓库实现已更新为：引导逻辑仅补齐缺失的 `route_id` 条目，不会清空已有配置（避免覆盖运行时/手工调整）。具体实现见 [src/agent_trader/api/main.py](src/agent_trader/api/main.py)。

**如何添加新提供者（步骤）**
1. 实现提供者类，包含所需的统一方法，并提供 `name` 属性。
2. 在应用启动或依赖注入配置处注册提供者，例如： `registry.register(provider_instance, name="myprovider")`。
3. 若需为特定路由设置自定义优先级，可通过仓库调用 `upsert(route_key, priorities=[...])` 写入。
4. 为提供者方法添加单元测试，并为注册 + 选择流程编写集成测试。

**测试建议**
- 单元测试 `SourceSelectionAdapter.execute` 时可以 mock `priority_repository` 与 `registry`，验证：
  - 当存在存储优先级时优先使用存储顺序
  - 当文档缺失或被禁用时回退到注册顺序
  - 提供者失败时被降至队尾（断言调用了 `reorder`/`upsert`）
  - 返回第一个成功的 `SourceFetchResult`
- 集成测试：运行启动引导并验证针对示例 `DataRouteKey` 的优先级是否被补齐。参见测试： `tests/unit/application/test_data_source_gateway.py`。

**示例**
- 提供者骨架示例：

```python
class ExampleProvider:
    name = "example"

    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:
        # 在此实现抓取与归一化逻辑
        return SourceFetchResult(data=..., metadata=...)
```

- 在启动代码中注册：

```python
registry.register(ExampleProvider(), name="example")
```

- 为某条路由强制设置优先级（管理 API 或引导脚本示例）：

```python
repo.upsert("KLINE:SH:1m", priorities=["tushare","baostock"], enabled=True)
```

**运维说明**
- 系统采用的是即时的每次请求降级策略（而非重试或后台健康检查）。若需要更复杂的行为（指数回退、熔断窗口、重试策略等），建议实现自定义的 `SourceSelectionAdapter` 并替换默认实现。
- 若需在文档图像脚本中保证 CJK 字形， 请将支持 CJK 的字体放到 `docs/fonts/`（例如 Noto Sans CJK），脚本会自动使用该字体。

**后续可选任务**
- 添加管理 API 用于查看/更新 `SourcePriorityRouteDocument` 条目。
- 为生产库编写迁移脚本（若需要更改 `DataRouteKey` 格式）。
- 在 `docs/providers.md` 中加入示例提供者与能力清单。

---

如果你需要，我还可以：
- 将此文件提交到仓库（已存在于 `docs/DATASOURCE.md`）。
- 在项目根 README 中加一段短引导并链接到此文档。
- 生成一个管理路由优先级的 API 存根。

你希望我接下来做哪一项？