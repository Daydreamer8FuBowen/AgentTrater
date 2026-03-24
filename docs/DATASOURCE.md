# 数据源路由设计

本文档描述 AgentTrader 当前多数据源路由机制：

- 数据源按能力声明支持范围。
- 路由优先级存于 Mongo。
- 外部调用通过统一网关发起，不感知具体命中源。

## 核心组件

- `DataSourceRegistry`
  - 负责注册与发现 provider。
  - 不承载路由策略。

- `SourceSelectionAdapter`
  - 输入 `DataRouteKey`。
  - 读取 Mongo 中优先级链。
  - 按优先级逐个尝试 provider。
  - 失败源降级到队尾并持久化。

- `DataAccessGateway`
  - 对外提供统一方法：
    - `fetch_klines`
    - `fetch_news`
    - `fetch_financial_reports`
    - `fetch_basic_info`

## 路由键

`DataRouteKey` 由三元组组成：

- `capability`: `kline` / `news` / `financial_report`
- `market`: 市场维度（可空）
- `interval`: 周期维度（仅 K 线有意义，可空）

存储键格式固定为：

- `capability:market:interval`
- 例如：`kline:szse:1d`
- 通配为 `*`，例如：`news:*:*`

## 优先级存储

Mongo 集合：`source_priority_routes`

建议字段：

- `route_id`: `DataRouteKey.as_storage_key()`
- `capability`
- `market`
- `interval`
- `priorities`: 数据源名称列表
- `enabled`
- `metadata`

启动引导策略：

- 由已注册 provider 的 `capabilities()` 生成默认路由。
- 仅补齐缺失路由，不覆盖已存在配置。
- 默认优先级按注册顺序写入；当前实现中启动时先注册 BaoStock，再按配置决定是否注册 TuShare，因此默认链路为 `baostock -> tushare`（当 TuShare 已配置 token 时）。

## 失败与降级

单次调用行为：

1. 读取当前路由优先级链。
2. 从头尝试 provider。
3. 某 provider 抛错：
   - 将该 provider 移到队尾并持久化。
   - 继续尝试下一个 provider。
4. 全部失败后抛出运行时错误。

系统默认不做后台健康探测和自动恢复，简化行为并保证可解释性。

## 与能力契约关系

- `basic_info` 归属于 K 线能力，不是独立 capability。
- 统一字段规范见 `UNIFIED_SOURCE_PAYLOAD_SPEC.md`。
- provider 协议定义见 `SOURCE_CAPABILITY_CONTRACTS.md`。
