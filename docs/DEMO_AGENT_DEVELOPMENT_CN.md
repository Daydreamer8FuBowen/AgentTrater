# Demo Agent 开发指南

本文档说明如何在 AgentTrader 中实现一个可运行的 LangGraph Demo Agent，并在不破坏现有服务层接口的前提下逐步演进到真实多智能体流程。

## 1. 目标与边界

当前 demo 的目标是提供一个稳定、可测试、可扩展的研究主图：

1. analyst 节点：生成初步分析结论。
2. reviewer 节点：执行规则化复核。
3. synthesizer 节点：汇总最终报告。

边界说明：

- 当前实现不接入真实 LLM 或外部工具调用。
- 输出为确定性内容，便于测试与回归。
- 对外接口保持 `ResearchGraph.invoke(state)` 不变。

## 2. 代码位置

- 图实现：`src/agent_trader/agents/graphs/research_graph.py`
- 共享状态：`src/agent_trader/agents/state.py`
- 路由入口：`src/agent_trader/agents/graphs/trigger_router.py`
- 服务调用：`src/agent_trader/application/services/trigger_service.py`
- 集成测试：`tests/integration/agent_nodes/test_research_graph.py`

## 3. 设计说明

### 3.1 状态设计

图使用 `GraphState`（`TypedDict`）作为节点间共享上下文。Demo 重点使用字段：

- `trigger`: 输入触发信息（类型、标的）。
- `opportunity`: 可选机会对象，用于补充符号等上下文。
- `report`: 各节点增量写入的最终报告。

### 3.2 图编排

在 `ResearchGraph.__init__` 中构建并编译：

1. `START -> analyst`
2. `analyst -> reviewer`
3. `reviewer -> synthesizer`
4. `synthesizer -> END`

每个节点返回新的 state 副本，避免原地修改共享对象。

### 3.3 报告结构

`report` 最终包含：

- `analysis`: 初始分析结论。
- `review`: 复核结论与检查项。
- `summary`: 汇总摘要。
- `reasoning`: 汇总阶段的解释信息。
- `pipeline`: 实际执行轨迹，用于测试和调试。

## 4. 本地开发流程

### 4.1 运行测试

在项目根目录执行：

```bash
uv run pytest tests/integration/agent_nodes/test_research_graph.py -v
```

### 4.2 通过 API 间接触发

`TriggerService.submit_trigger` 会调用 `TriggerRouterGraph.invoke`，随后进入 `ResearchGraph.invoke`。你可以通过触发接口验证该链路。

## 5. 如何扩展为真实 Agent

### 5.1 替换节点内部逻辑

优先从节点内部替换开始，而不是先改边：

1. analyst：接入财务、新闻、技术面工具，输出结构化观察。
2. reviewer：增加风险规则（流动性、行业暴露、事件冲突）。
3. synthesizer：统一置信度口径，形成可持久化报告。

### 5.2 状态扩展原则

- 新增字段优先追加到 `GraphState`，避免复用语义不清字段。
- 节点输出应保持幂等，重复执行不产生不可控副作用。
- 只在确有必要时写入数据库，图内部优先操作内存状态。

### 5.3 失败处理建议

- 节点内捕获可恢复异常，写入 `report.errors` 并继续。
- 不可恢复异常直接抛出，由服务层决定重试或告警。
- 对外部依赖调用增加超时和重试上限。

## 6. 验收标准

一个合格的 demo agent 版本应满足：

1. 能从 `TriggerService` 全链路触发。
2. 集成测试可稳定断言执行顺序与关键输出。
3. 节点职责清晰，便于后续替换成真实推理节点。
4. 不改变现有公共接口和上层依赖注入方式。
