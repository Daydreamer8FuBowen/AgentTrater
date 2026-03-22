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



## 开发指南

先不考虑回测进行设计，但是要保证数据、agent的分离。快速迭代出一个可以市场分析的项目；
那么现在的问题就是设计k线数据集合，不回测也会用到行业历史k线；设计相关重大新闻评估影响力在不同分析模式下的使用（做长线的关注更长时间线的新闻）；
同一个事件的报告需要被重复使用并屏蔽相关新闻；同一指标的的历史分析如果没有变动或在不再候选池中那么也使用相同报告；

1. 后台数据补充线程，在交易日时尽可能快的补充实时5m数据。同时补充历史缺失数据1d，5m数据，1d需要2年数据，5m需要一个月数据；设计mongo表记录symbol；

2. 规范化新闻事件流程，需要设计爬虫去访问网站能够找到最新的新闻并评估其影响力（我觉得这里触发只做大新闻的而不是每个小新闻都触发）（小新闻具体分析时再去检索）