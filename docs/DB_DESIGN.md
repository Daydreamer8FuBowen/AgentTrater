# DB Design (Current)

本文档描述当前代码实现下的数据库设计现状，覆盖 MongoDB 与 InfluxDB。

## 1. 总览

系统采用双存储：
- MongoDB：承载元数据、配置、事件、候选与持仓等文档型数据。
- InfluxDB：承载 K 线时序数据（candles measurement）。

连接生命周期由 AppConnectionManager 统一管理：
- 启动：Mongo ping + ensure_indexes，Influx ping。
- 关闭：先关闭 Influx，再关闭 Mongo。

## 2. MongoDB 设计

### 2.1 文档基类与约束

- MongoDocument：extra=forbid，禁止未声明字段写入。
- TimestampedDocument：统一 created_at、updated_at。
- 每个文档声明：collection_name、primary_key、searchable_fields、json_fields、editable_fields。

说明：索引由 DOCUMENT_REGISTRY 集中声明，并通过 MongoConnectionManager.ensure_indexes() 在启动阶段创建。

### 2.2 集合与主键

#### Agent/Skill 相关
- agent_definitions，主键 agent_id
- skill_definitions，主键 skill_id
- skill_versions，主键 skill_version_id
- agent_releases，主键 agent_release_id
- agent_release_pointers，主键 agent_id

### 2.2.1 Agent/Skill 表含义说明

#### agent_definitions（主键 agent_id）
- 含义：Agent 的主定义表（静态档案）。
- 记录内容：name、type、status、description、skill_bindings、execution_policy、model_policy、tags、metadata。
- 作用：定义“这个 Agent 是谁、具备哪些能力绑定、是否可用”。

#### skill_definitions（主键 skill_id）
- 含义：Skill 的主定义表（不含具体版本）。
- 记录内容：name、category、description、interfaces、tool_policy、status。
- 作用：定义“技能的业务身份与能力边界”。

#### skill_versions（主键 skill_version_id）
- 含义：Skill 的版本发布表。
- 记录内容：skill_id、version、status、prompt_spec、input_schema、output_schema、runtime_policy、tool_policy、implementation_ref、checksum、published_at。
- 作用：管理技能迭代、灰度发布与回滚，保证同一 skill 可并存多个历史版本。

#### agent_releases（主键 agent_release_id）
- 含义：Agent 的发布版本表。
- 记录内容：agent_id、version、status、graph_spec、execution_policy、published_at。
- 作用：沉淀 Agent 在某次上线时的完整可执行配置（发布快照）。

#### agent_release_pointers（主键 agent_id）
- 含义：Agent 的当前生效版本指针表。
- 记录内容：current_release_id、previous_release_id、updated_by、updated_at。
- 作用：快速确定“当前应运行哪个 release”，并支持一键回退到上一个版本。

#### 关系总结
- 定义层：agent_definitions + skill_definitions
- 版本层：skill_versions + agent_releases
- 生效控制层：agent_release_pointers

#### 任务运行相关
- task_runs，主键 run_id
- task_events，主键 event_id
- task_artifacts，主键 artifact_id
- task_checkpoints，主键 checkpoint_id

### 2.2.2 任务运行表含义说明

#### task_runs（主键 run_id）
- 含义：一次任务执行的主记录（运行摘要）。
- 记录内容：task_kind、status、trigger、context、agent、graph、execution、metrics、result、error。
- 作用：用于追踪任务的生命周期（queued -> running -> completed/failed）与最终结果摘要。

#### task_events（主键 event_id）
- 含义：任务执行过程中的事件流水。
- 记录内容：run_id、seq、event_type、timestamp、node、agent、skill、payload、trace。
- 作用：用于还原执行过程、排查节点级问题、支持可观测与回放。

#### task_artifacts（主键 artifact_id）
- 含义：任务运行产物表。
- 记录内容：run_id、node_id、artifact_type、content_type、content、size_bytes、created_at。
- 作用：存储任务输出附件（结构化 JSON、文本日志、模型输出等）。
- 约定：artifact_id 可被业务表（如 candidates/positions 的 audit_ids）引用为审计报告ID。

#### task_checkpoints（主键 checkpoint_id）
- 含义：任务中间状态快照表。
- 记录内容：run_id、seq、node_id、checkpoint_type、state、created_at。
- 作用：支持长流程中断恢复、阶段回滚和调试对比。

#### 关系总结
- 主轴：task_runs（1） -> task_events（N）
- 产物：task_runs（1） -> task_artifacts（N）
- 检查点：task_runs（1） -> task_checkpoints（N）

#### 业务数据相关
- news_items，主键 news_id
- basic_infos，主键 symbol
- source_priority_routes，主键 route_id
- candidates，主键 candidate_id
- positions，主键 position_id

### 2.2.3 业务数据表含义说明

#### news_items（主键 news_id）
- 含义：新闻/公告标准化后的落库表。
- 记录内容：title、content、summary、source、published_at、market、industry_tags、concept_tags、stock_tags、credibility、dedupe_key。
- 作用：为事件触发与资讯分析提供统一新闻事实源；通过 dedupe_key 做去重。

#### basic_infos（主键 symbol）
- 含义：标的基础信息快照表。
- 记录内容：name、industry、area、market、status、security_type、primary_source、source_trace、conflict_fields。
- 作用：作为全市场标的主数据，用于候选/持仓补全和同步 universe 基座。

#### source_priority_routes（主键 route_id）
- 含义：多数据源路由优先级配置表。
- 记录内容：capability、market、interval、priorities、enabled、metadata。
- 作用：决定某类请求（例如 kline:sse:5m）按哪个源顺序拉取；支持故障后动态重排。

#### candidates（主键 candidate_id）
- 含义：候选池实体表。
- 记录内容：symbol_id、symbol、status、score、audit_ids、created_at、deprecated_at、tags、notes、metadata。
- 作用：维护候选标的及评分，并通过 audit_ids 关联审计报告。
- 约定绑定：audit_ids 中每个值约定为 task_artifacts.artifact_id。

#### positions（主键 position_id）
- 含义：持仓快照表（与策略解耦）。
- 记录内容：symbol_id、symbol、status、position_ratio、position_cost、audit_ids、created_at、deprecated_at、metadata。
- 作用：维护当前持仓信息，作为 5m 同步 Tier A 数据源。
- 约定绑定：audit_ids 中每个值约定为 task_artifacts.artifact_id。

#### 关系总结
- 主数据基座：basic_infos
- 配置控制：source_priority_routes
- 业务分层：positions（持仓）+ candidates（候选）
- 审计关联：candidates/positions 通过 audit_ids 约定绑定到 task_artifacts.artifact_id

#### 审计绑定约束（约定）
- 非外键：Mongo 当前不做数据库级外键约束，该绑定为应用层约定。
- 建议校验：写入 candidates/positions 前，校验 audit_ids 对应 artifact_id 是否存在。
- 建议类型约束：被引用的 task_artifacts 建议使用统一 artifact_type（例如 `audit_report`）。

### 2.3 关键字段设计（当前）

#### basic_infos
- symbol（PK）
- name、industry、area、market、list_date、status、delist_date、security_type
- primary_source、source_trace、conflict_fields、metadata
- created_at、updated_at

用途：维护标的基础信息快照及多源合并痕迹。

#### source_priority_routes
- route_id（PK）= capability:market:interval
- capability、market、interval
- priorities（数据源优先级列表）
- enabled、metadata
- created_at、updated_at

用途：按能力/市场/周期维度管理源路由优先级。

#### candidates
- candidate_id（PK）
- symbol_id、symbol
- status
- score
- audit_ids（对应外部报告ID）
- created_at
- deprecated_at（软废弃时间）
- tags、notes、metadata

用途：候选池（评分 + 软废弃 + 外部报告关联）。

#### positions
- position_id（PK）
- symbol_id、symbol
- status
- position_ratio（持仓占比）
- position_cost（持仓成本）
- audit_ids（对应外部报告ID）
- created_at
- deprecated_at（软废弃时间）
- metadata

用途：持仓快照（与策略无关）。

### 2.4 当前索引设计

#### candidates
- unique(candidate_id)
- (symbol_id, status)
- (status, created_at desc)
- (deprecated_at)

#### positions
- unique(position_id)
- (symbol_id, status)
- (status, created_at desc)
- (deprecated_at)

#### 其他关键索引（节选）
- news_items：dedupe_key 唯一索引；source/market/tags + published_at 复合索引
- basic_infos：symbol 唯一索引；market/primary_source + updated_at 索引
- source_priority_routes：route_id 唯一；(capability, market, interval) 唯一
- task_events：run_id + seq 唯一

### 2.5 仓储操作语义（当前实现）

#### MongoCandidateRepository
- upsert(candidate)
- upsert_many(items)
- get_by_id(candidate_id)
- list_active()：deprecated_at 为 null 且 status != deprecated
- list_by_status(status, page, page_size)
- deprecate(candidate_id, status=deprecated, audit_id=None)

写入规则：
- upsert 使用 $set + $setOnInsert(created_at)
- deprecate 使用原子 update_one 写 status + deprecated_at；可追加 audit_ids

#### MongoPositionRepository
- upsert(position)
- upsert_many(items)
- get_by_id(position_id)
- list_active()：deprecated_at 为 null 且 status != deprecated
- list_by_status(status, page, page_size)
- deprecate(position_id, status=deprecated, audit_id=None)

写入规则与 candidates 一致。

#### 其他仓储（当前已用）
- MongoNewsRepository：add、add_many、exists_by_dedupe_key
- MongoBasicInfoRepository：upsert_many_by_symbol（bulk_write）
- MongoSourcePriorityRepository：get、upsert、reorder
- Task 系列仓储：task_runs/task_events/task_artifacts

### 2.6 UnitOfWork 装配（Mongo）

MongoUnitOfWork 当前已装配：
- task_runs, task_events, task_artifacts
- news, basic_infos, source_priorities
- candidates, positions

当前仍为占位（NotImplemented）：
- memories（MemoryRepository）
- signals（SignalRepository，当前走 Influx）
- candles（CandleRepository，当前走 Influx）

## 3. InfluxDB 设计

### 3.1 Measurement

- measurement：candles

### 3.2 Tags

- symbol
- interval
- asset_class
- exchange
- adjusted
- source

### 3.3 Fields

必填：
- open, high, low, close, volume

可选：
- turnover
- trade_count

时间戳：
- point time 使用 Candle.open_time，精度 WritePrecision.S（秒）。
- `Candle.open_time` 必须是 UTC 时间；写入 Influx 时不允许使用市场本地时间。
- **注**：`Candle.close_time` 不存储在 InfluxDB 中。在应用需要 close_time 时，通过 `get_bar_close_time(open_time, interval)` 推导。

### 3.4 写入语义

- 单条写入：write(candle)
- 批量写入：write_batch(candles)
- API：InfluxDB client write_api，SYNCHRONOUS

## 4. 设计约定

### 4.1 软废弃约定

对于 candidates/positions：
- 有效记录：deprecated_at 为 null
- 废弃记录：deprecated_at 非 null（通常 status=deprecated）

### 4.2 审计关联约定

- audit_ids 存储外部报告ID列表，不在主文档内嵌报告全文。

### 4.3 与同步任务的衔接

- Tier A：positions 的 active symbols
- Tier B：candidates 的 active symbols（去重后减 Tier A）
- Tier C：basic_infos 全量减 Tier A/B
- 同步策略：5m 仅 A/B；1d 覆盖 A/B/C

## 5. 后续演进建议

- 为 candidates/positions 增加统一 status 枚举约束（active/inactive/deprecated）
- 为 deprecate 增加 reason 字段（可写入 metadata）
- 为 candidates/positions 增加按 symbol_id 批量更新接口
- 增加仓储级单元测试覆盖 upsert_many、deprecate、list_active 的边界场景
