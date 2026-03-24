# 开发规范

## 目录与边界

- `api/`: 仅协议转换与依赖注入。
- `application/data_access/`: 路由与网关编排。
- `ingestion/models.py`: 数据契约中心。
- `ingestion/sources/`: provider 适配层。
- `storage/`: 持久化与连接管理。

禁止跨层绕行：

- API 不直接依赖 provider。
- provider 不直接操作 Mongo 优先级仓储。

## 命名规则

- Provider 类名：`<Name>Source`
- 统一方法名：`fetch_<domain>_unified`
- 查询模型：`<Domain>Query`
- 路由键：`DataRouteKey`
- 返回模型：按能力分型结果对象（`KlineFetchResult` / `BasicInfoFetchResult` / `NewsFetchResult` / `FinancialReportFetchResult`）

## 数据规范

- 输出必须遵循 `UNIFIED_SOURCE_PAYLOAD_SPEC.md`。
- 统一字段必须在 source 层完成映射。
- 不允许将 provider 原生字段直接暴露给上层。

## 路由策略规范

- 失败源必须降级到队尾。
- 重排必须持久化到 Mongo。
- 默认路由仅补齐，不覆盖人工配置。

## 测试规范

至少覆盖：

1. 契约测试
   - 能力声明完整性
   - payload 字段一致性

2. 网关测试
   - 优先级命中
   - 失败切换与重排

3. 集成测试
   - 真实源调用（可按环境变量跳过）

## 变更准入

涉及以下任一项时，必须同步更新文档与测试：

- `DataRouteKey` 结构
- 任一分型结果对象字段
- 任一能力的 payload 必填字段
- provider 能力声明
