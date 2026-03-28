# 文档导览

本目录按“核心文档优先”组织，默认先阅读核心文档，再按专题深入。

## 快速入口

- 后端 API：`uv run uvicorn agent_trader.api.main:app --reload`
- 后台 worker：`uv run python -m agent_trader.worker`
- 前端控制台：`cd frontend/admin-console && npm run dev`

## 核心文档（保留）

- `ARCHITECTURE.md`：系统架构总览与主链路说明
- `DEVELOPMENT_CONVENTIONS.md`：分层边界、命名、时间与测试规范
- `DB_DESIGN.md`：Mongo + Influx 当前数据模型与索引语义
- `DATASOURCE.md`：多数据源路由、优先级与失败降级机制
- `SOURCE_CAPABILITY_CONTRACTS.md`：数据源能力契约
- `UNIFIED_SOURCE_PAYLOAD_SPEC.md`：统一 payload 字段规范
- `SCHEDULER_DEVELOPMENT.md`：worker 调度落地规范
- `REALTIME_M5_UPDATE_DESIGN.md`：实时 M5 覆盖更新设计
- `MEASUREMENT_DESIGN.md`：Influx `candles` measurement 设计
- `TRADINGVIEW_FRONTEND_GUIDE.md`：前端 K 线模块与管理台说明
- `REAL_DATA_SOURCE_TESTING.md`：真实数据源联调说明

## 测试相关文档

- `../tests/README.md`：测试目录结构与 marker 约定
