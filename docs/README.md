## Docs Index

开发入口：

- 后端 API：`uv run uvicorn agent_trader.api.main:app --reload`
- 后台 worker：`uv run python -m agent_trader.worker`
- 前端控制台：`cd frontend/admin-console && npm run dev`

- `ARCHITECTURE.md`: 系统数据架构总览（无 Event 设计）。
- `DB_DESIGN.md`: 当前数据库设计（MongoDB 文档/索引 + InfluxDB 时序结构）。
- `DATASOURCE.md`: 多数据源动态路由与优先级管理。
- `SOURCE_CAPABILITY_CONTRACTS.md`: 各数据源能力声明与接口契约。
- `UNIFIED_SOURCE_PAYLOAD_SPEC.md`: K 线/新闻/财务统一字段规范。
- `DEVELOPMENT_CONVENTIONS.md`: 开发规范与测试准入规则。
- `REAL_DATA_SOURCE_TESTING.md`: 真实数据源联调与冒烟策略。
- `SCHEDULER_DEVELOPMENT.md`: 定时任务开发指南（AsyncIOScheduler 推荐实践）。
