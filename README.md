# AgentTrader

Agent-centric quantitative research backend built with FastAPI, LangGraph, MongoDB, and InfluxDB.

## Development

# AgentTrader

以事件触发为核心的 Agent 驱动量化研究后端，使用 FastAPI、LangGraph、MongoDB 与 InfluxDB 等技术栈。

系统设计思想（简述）：系统以事件（例如行情数据、信号、定时调度或外部 webhook）为触发点，经过 `TriggerService` 路由到 Agent 图（graphs）执行决策流程（可接入 LLM、技能或工具），将输出写回候选池/信号存储，或触发回测与执行流程，形成端到端的事件驱动闭环。

## 开发（Development）

在本地开发时可使用：

```bash
uv sync
uv run uvicorn agent_trader.api.main:app --reload
```

本地基础服务（MongoDB / InfluxDB）示例：

```bash
docker compose up -d mongo influxdb
```

前端管理控制台（开发模式）：

```bash
cd frontend/admin-console
npm install
npm run dev
```

## 简要进度（任务清单）

### 已完成
- [x] 项目骨架与开发文档/示例：包含 Ingestion 三层模板与 TuShare 示例、调度器与任务 scaffold、Demo Agent graph、Mongo 存储 scaffold、API 触发入口与测试布局。

### 未完成（待办）
- [ ] 具体 Agent 节点与 LLM/工具接入
- [ ] 更多数据源与规范化实现（例如 EastMoney、Sina）
- [ ] 候选池与持久化仓库实现
- [ ] 回测框架与任务实现
- [ ] 端到端集成测试、CI 与监控

更多详细状态与后续计划请参见 `docs/` 与 `tests/` 目录。

## 未完成任务细化（可执行子任务）

下面是将未完成项拆解为可执行子任务的列表，包含产物/位置、验收标准与预计工时，便于逐项实现。
