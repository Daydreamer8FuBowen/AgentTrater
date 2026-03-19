# 📚 AgentTrader 学习指南

> 为从 Java 转向 Python Web 开发的工程师编写

---

## 📖 文档导航

### 🎯 快速开始（新手必读）

| 文档 | 内容 | 适合人群 |
|------|------|--------|
| [开发完全指南](DEVELOPER_GUIDE_CN.md) | 项目核心概念、架构设计、完整实现示例 | **必读** - 所有开发者 |
| [配置系统指南](CONFIGURATION_GUIDE_CN.md) | 环境变量、Pydantic Settings、配置管理 | 需要配置的任何时候 |
| [快速演示](QUICK_START_DEMO.md) | 事件系统演示代码（可运行） | 想快速了解概念 |

### 🏗️ 深度学习（Java开发者特别推荐）

| 文档 | 核心内容 | 掌握后能做什么 |
|------|--------|-------------|
| [Ingestion 架构深度解析](INGESTION_ARCHITECTURE_CN.md) | 三层转换模式、数据源扩展、设计模式对比 | 添加新数据源的任何操作 |
| [DEVELOPER_GUIDE_CN.md](DEVELOPER_GUIDE_CN.md) 第 3 节 | 现有数据源分析、完整的添加新源示例 | 理解数据流、实现扩展 |

### 🔧 实现参考

| 文档 | 内容 | 使用场景 |
|------|------|--------|
| [TUSHARE_INTEGRATION.md](TUSHARE_INTEGRATION.md) | TuShare 集成细节 | 调试 TuShare 数据源 |
| [TUSHARE_TOKEN_SETUP_SUMMARY.md](TUSHARE_TOKEN_SETUP_SUMMARY.md) | Token 配置总结 | Token 相关问题 |

---

## 🚀 学习路径

### 第 1 天：理解基础概念

```
⏱️  预计：2 小时

1. 阅读 [开发完全指南](DEVELOPER_GUIDE_CN.md)
   - 第 1 节：事件驱动系统设计
   - 第 2 节：定时任务配置（只看概览，不用完全理解）
   - 第 4 节：对比 Java

2. 运行演示脚本：
   uv run python -m scripts.demo_events

3. 查看项目中的实际代码：
   - src/agent_trader/domain/models.py (事件定义)
   - src/agent_trader/ingestion/sources/tushare_source.py
   - src/agent_trader/ingestion/normalizers/tushare_normalizer.py
```

**理解核心问题**：
- ✅ 事件是如何定义的？
- ✅ 为什么要三层转换？
- ✅ RawEvent、NormalizedEvent、ResearchTrigger 的区别？

### 第 2 天：理解定时任务

```
⏱️  预计：1.5 小时

1. 阅读 [开发完全指南](DEVELOPER_GUIDE_CN.md) 第 2 节
   - 定时任务技术栈对比
   - APScheduler 集成
   - FastAPI 生命周期管理

2. 查看项目中的代码：
   - src/agent_trader/worker/main.py (原始框架)
   - src/agent_trader/worker/scheduler.py (应该已配置)
   - src/agent_trader/api/main.py (lifespan 集成)

3. 自己编写一个简单的定时任务：
   - 在 src/agent_trader/worker/tasks.py 中添加
   - 在 scheduler 中注册
```

**理解核心问题**：
- ✅ APScheduler 如何在 FastAPI 中集成？
- ✅ 定时任务是如何执行的？
- ✅ 如何配置任务间隔？

### 第 3 天：理解数据摄入层

```
⏱️  预计：3 小时

1. 阅读 [开发完全指南](DEVELOPER_GUIDE_CN.md) 第 3 节
   - 现有 TuShare 数据源分析
   - 添加新数据源的 5 个步骤

2. 深入阅读 [Ingestion 架构深度解析](INGESTION_ARCHITECTURE_CN.md)
   - 理解三层转换的原因
   - 扩展性检查清单

3. **动手实践**：添加一个简单的模拟数据源
   - 创建 src/agent_trader/ingestion/sources/demo_source.py
   - 创建 src/agent_trader/ingestion/normalizers/demo_normalizer.py
   - 参考 [DEVELOPER_GUIDE_CN.md](DEVELOPER_GUIDE_CN.md) 的东方财富示例

4. 编写单元测试：
   - tests/ingestion/sources/test_demo_source.py
   - 运行: uv run pytest tests/ingestion/ -v
```

**理解核心问题**：
- ✅ SourceAdapter 的职责是什么？
- ✅ EventNormalizer 的职责是什么？
- ✅ 如何添加新的数据源？
- ✅ 异步编程在这里如何应用？

### 第 4 天+：实战项目

```
⏱️  预计：根据复杂度而定

选择以下任一项目：

【项目 A】集成实际的财经数据源
- 选择一个免费的财经数据 API（新浪财经、东财、 Choice、 Wind 等）
- 按照 [Ingestion 架构深度解析](INGESTION_ARCHITECTURE_CN.md) 的步骤实现
- 编写完整的测试

【项目 B】实现更复杂的定时任务
- 实现 refresh_candidate_pool() 任务
- 从数据库读取候选项
- 计算评分
- 更新状态

【项目 C】深化 Agent 系统理解
- 理解 TriggerRouter 的路由逻辑
- 实现一个简单的 Agent Graph
```

---

## 📋 与 Java 开发的对比速查表

### 概念映射

| Java 概念 | Python 等价物 | AgentTrader 中的位置 |
|----------|-------------|-------------------|
| `interface` | `Protocol` | `src/agent_trader/ingestion/sources/base.py` |
| `@Component` | 函数或类 | `src/agent_trader/api/dependencies.py` |
| `@Scheduled` | `APScheduler` | `src/agent_trader/worker/scheduler.py` |
| `@Value` | `Pydantic BaseSettings` | `src/agent_trader/core/config.py` |
| `@Autowired` | `FastAPI Depends()` | API 函数参数 |
| `Stream<T>` | `async for` / 列表推导 | 任何数据处理逻辑 |
| `ThreadPool` | `asyncio` | 所有网络 I/O 操作 |
| `Enum` | `class E(str, Enum)` | `src/agent_trader/domain/models.py` |

### 模式对比

| Java 模式 | Python 对应 | 优势 |
|---------|-----------|------|
| **工厂模式** | `@classmethod from_xxx()` | 更简洁，不需要额外类 |
| **适配器模式** | `Protocol` + 实现 | 鸭子类型，无需显式继承 |
| **观察者模式** | `async` 回调 | 更自然的异步支持 |
| **单例模式** | `@lru_cache(maxsize=1)` | 更简洁，自动管理 |
| **依赖注入** | `FastAPI Depends()` | 类似 Spring，更轻量 |

### 常见做法对比

```java
// Java Spring Boot
@Service
@Scheduled(fixedRate = 5 * 60 * 1000)
public void syncData() {
    // 任务逻辑
}
```

```python
# Python FastAPI + APScheduler
async def sync_data():
    # 任务逻辑
    pass

scheduler.add_job(
    sync_data,
    trigger="interval",
    seconds=300,
)
```

---

## 🔍 代码导航

### 关键文件速查

```
AgentTrader/
│
├── 📁 src/agent_trader/
│   ├── domain/
│   │   └── models.py              ← 事件定义（TriggerKind）
│   │
│   ├── ingestion/
│   │   ├── sources/
│   │   │   ├── base.py            ← SourceAdapter 协议
│   │   │   └── tushare_source.py  ← 现有实现示例
│   │   ├── normalizers/
│   │   │   ├── base.py            ← EventNormalizer 协议
│   │   │   └── tushare_normalizer.py  ← 现有实现示例
│   │   └── models.py              ← RawEvent, NormalizedEvent 定义
│   │
│   ├── core/
│   │   └── config.py              ← 配置系统（Settings）
│   │
│   ├── worker/
│   │   ├── main.py                ← 原始框架
│   │   ├── scheduler.py            ← 任务调度器（关键）
│   │   └── tasks.py               ← 任务定义
│   │
│   └── api/
│       ├── main.py                ← 应用入口（查看 lifespan）
│       └── dependencies.py        ← 依赖注入
│
├── 📁 tests/
│   ├── ingestion/
│   └── ...
│
├── 📁 docs/
│   ├── DEVELOPER_GUIDE_CN.md          ← 完整指南（开始这里）
│   ├── CONFIGURATION_GUIDE_CN.md      ← 配置指南
│   ├── INGESTION_ARCHITECTURE_CN.md   ← 深度解析
│   └── ...
│
├── .env                           ← 配置文件（必须有）
└── .env.example                   ← 配置模板
```

### 快速代码查看

**问题 1: 事件是如何定义的？**
```bash
# 查看事件定义
cat src/agent_trader/domain/models.py | grep -A 10 "TriggerKind"
```

**问题 2: 定时任务是如何配置的？**
```bash
# 查看任务配置
cat src/agent_trader/worker/scheduler.py | grep -A 5 "add_job"
```

**问题 3: 如何添加新数据源？**
```bash
# 参考现有实现
cat src/agent_trader/ingestion/sources/tushare_source.py
cat src/agent_trader/ingestion/normalizers/tushare_normalizer.py
```

---

## 🧪 演示脚本

### 演示 1: 事件驱动系统完整流程

```bash
# 运行事件演示脚本
uv run python -m scripts.demo_events

# 预期输出：
# [数据源] 正在获取 000001.SZ 的 K 线数据...
# [规范化器] 检测到异常波动: 000001.SZ 6.5%
# [Agent系统] 接收到触发...
# ✓ 分析结果: 建议关注 000001.SZ
```

### 演示 2: 配置系统

```bash
# 查看当前配置加载
uv run python -c "from agent_trader.core.config import get_settings; s = get_settings(); print(f'MySQL: {s.mysql}'); print(f'Worker: {s.worker}')"
```

### 演示 3: 启动应用（带定时任务）

```bash
# 启动 FastAPI 应用，观察定时任务日志
uv run uvicorn agent_trader.api.main:app --reload

# 应该看到：
# ✓ 定时任务调度器已启动
# [定时任务] 开始摄入 K 线数据...
# [定时任务] 开始刷新候选池...
```

---

## ❓ 常见问题

### Q1: 我是 Java 开发者，Python 的异步编程怎么学？

**A**: AgentTrader 使用 `async/await` 模式，类似 JavaScript 的 Promise。
- 阅读：[Python 官方 asyncio 教程](https://docs.python.org/3/library/asyncio.html)
- 实践：修改 `scripts/demo_events.py` 中的异步函数
- 核心规则：
  - 调用异步函数时必须 `await`
  - 异步函数定义为 `async def`
  - 在异步函数中调用同步函数用 `asyncio.to_thread()`

### Q2: 为什么三层转换这么复杂？不能直接存储吗？

**A**: 三层转换是为了解耦合，方便扩展：
1. 如果直接存储原始数据，每个数据源格式不同
2. 添加新数据源时，系统各部分都要改动
3. 三层转换把不同格式的数据统一为 ResearchTrigger，后续系统不需要改动

### Q3: 如何调试数据源？

**A**: 以 TuShare 为例：
```python
# 临时测试脚本
import asyncio
from agent_trader.core.config import get_settings
from agent_trader.ingestion.sources.tushare_source import TuShareSource

async def test():
    settings = get_settings()
    source = TuShareSource.from_settings(settings)
    data = await source.fetch_klines("000001.SZ", "20240101", "20240131")
    for evt in data:
        print(evt.payload)

asyncio.run(test())
```

### Q4: 定时任务为什么不执行？

**A**: 检查清单：
1. ✅ 应用是否启动？ `uv run uvicorn ...`
2. ✅ 任务是否在 scheduler.py 中注册？ `scheduler.add_job(...)`
3. ✅ 看日志是否有错误？查看 `log_level = DEBUG`
4. ✅ 时间间隔是否太长？改成 10 秒临时测试

### Q5: 如何添加新配置项？

**A**: 三步走：
1. 在 `.env.example` 中添加示例：`MY_NEW_CONFIG=value`
2. 在 `config.py` Settings 中添加字段：`my_new_config: str = "default"`
3. 在代码中使用：`settings.my_new_config`

---

## 🎓 推荐学习资源

### Python 异步编程
- [Real Python - Async IO](https://realpython.com/async-io-python/)
- [Python 官方 asyncio 文档](https://docs.python.org/3/library/asyncio.html)

### FastAPI
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [FastAPI 生命周期管理](https://fastapi.tiangolo.com/advanced/events/)

### APScheduler
- [APScheduler 官方文档](https://apscheduler.readthedocs.io/)
- [APScheduler 触发器说明](https://apscheduler.readthedocs.io/en/3.12.1/modules/triggers/interval.html)

### Pydantic
- [Pydantic 官方文档](https://docs.pydantic.dev/)
- [Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

## 📞 获取帮助

### 遇到问题？

1. **首先查看文档**：
   - 事件系统问题 → [DEVELOPER_GUIDE_CN.md](DEVELOPER_GUIDE_CN.md)
   - 配置问题 → [CONFIGURATION_GUIDE_CN.md](CONFIGURATION_GUIDE_CN.md)
   - 数据源问题 → [INGESTION_ARCHITECTURE_CN.md](INGESTION_ARCHITECTURE_CN.md)

2. **查看代码示例**：
   - 现有数据源：`src/agent_trader/ingestion/`
   - 单元测试：`tests/`
   - 演示脚本：`scripts/demo_events.py`

3. **运行演示**：
   ```bash
   uv run python -m scripts.demo_events
   ```

---

## 📝 学习进度检查表

使用此表跟踪你的学习进度：

```
【第 1 天】理解基础概念
☐ 阅读 DEVELOPER_GUIDE_CN.md 第 1 节
☐ 理解 TriggerKind、RawEvent、NormalizedEvent 的定义
☐ 运行 uv run python -m scripts.demo_events
☐ 查看项目中的 models.py 文件

【第 2 天】理解定时任务
☐ 阅读 DEVELOPER_GUIDE_CN.md 第 2 节
☐ 理解 APScheduler 和 FastAPI 的集成
☐ 查看项目中的 scheduler.py、worker/tasks.py 文件
☐ 编写一个简单的定时任务

【第 3 天】理解数据摄入
☐ 阅读 DEVELOPER_GUIDE_CN.md 第 3 节
☐ 阅读 INGESTION_ARCHITECTURE_CN.md
☐ 理解三层转换模式
☐ 查看 TuShare 实现作为参考

【第 4 天+】实战项目
☐ 添加一个新的数据源
☐ 编写完整的单元测试
☐ 验证定时任务工作正常
☐ 理解数据如何流经系统
```

---

## 🎉 恭喜！

当你完成以上学习时，你将掌握：

✅ Python 异步编程在 Web 项目中的应用
✅ FastAPI 应用的架构和生命周期管理
✅ 事件驱动系统的设计与实现
✅ 可扩展的数据摄入层设计
✅ 定时任务的配置与管理
✅ 如何从 Java 思维过渡到 Python 思维

**下一步：**
- 🚀 为 AgentTrader 添加新的数据源
- 🔧 实现更复杂的 Agent 处理逻辑
- 📊 连接真实的数据库和服务
- 🧠 深入学习 LangGraph 和多智能体系统

---

**最后更新**: 2024-01-15
**作者**: Agent Copilot
**适合**: 从 Java 转向 Python Web 的开发者
