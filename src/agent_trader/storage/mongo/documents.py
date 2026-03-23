"""Pydantic 文档模型集合。

本模块定义了与 Mongo 集合对应的 Pydantic 模型（文档结构）。
每个模型声明了 `collection_name`、`primary_key`、以及 `json_fields` / `editable_fields` 等元信息，
便于仓库层序列化/反序列化和索引管理。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _new_identifier(prefix: str) -> str:
    """生成带前缀的唯一标识符，用作主键默认值（例如 `run_xxx`）。"""
    return f"{prefix}_{uuid4().hex}"


class MongoDocument(BaseModel):
    """Mongo 文档实体基类。

    通过 `model_config` 禁止额外字段（`extra='forbid'`），保证写入时字段可控。
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TimestampedDocument(MongoDocument):
    """带 `created_at` / `updated_at` 时间戳的基类文档。"""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentDefinitionDocument(TimestampedDocument):
    """Agent 定义文档（集合 `agent_definitions`）。"""
    collection_name: ClassVar[str] = "agent_definitions"
    primary_key: ClassVar[str] = "agent_id"
    searchable_fields: ClassVar[tuple[str, ...]] = ("agent_id", "name", "type", "description", "status")
    json_fields: ClassVar[tuple[str, ...]] = (
        "skill_bindings",
        "execution_policy",
        "model_policy",
        "tags",
        "metadata",
    )
    editable_fields: ClassVar[tuple[str, ...]] = (
        "name",
        "type",
        "status",
        "description",
        "owner",
        "skill_bindings",
        "execution_policy",
        "model_policy",
        "tags",
        "metadata",
        "updated_at",
    )

    agent_id: str
    name: str
    type: str
    status: Literal["draft", "active", "archived"] = "draft"
    description: str = ""
    owner: str | None = None
    skill_bindings: list[dict[str, Any]] = Field(default_factory=list)
    execution_policy: dict[str, Any] = Field(default_factory=dict)
    model_policy: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillDefinitionDocument(TimestampedDocument):
    """Skill 定义文档（集合 `skill_definitions`）。"""
    collection_name: ClassVar[str] = "skill_definitions"
    primary_key: ClassVar[str] = "skill_id"
    searchable_fields: ClassVar[tuple[str, ...]] = ("skill_id", "name", "category", "description", "status")
    json_fields: ClassVar[tuple[str, ...]] = ("interfaces", "tool_policy")
    editable_fields: ClassVar[tuple[str, ...]] = (
        "name",
        "category",
        "description",
        "interfaces",
        "tool_policy",
        "status",
        "updated_at",
    )

    skill_id: str
    name: str
    category: str
    description: str = ""
    interfaces: dict[str, Any] = Field(default_factory=dict)
    tool_policy: dict[str, Any] = Field(default_factory=dict)
    status: Literal["draft", "active", "archived"] = "draft"


class SkillVersionDocument(TimestampedDocument):
    """Skill 版本文档（集合 `skill_versions`）。"""
    collection_name: ClassVar[str] = "skill_versions"
    primary_key: ClassVar[str] = "skill_version_id"
    searchable_fields: ClassVar[tuple[str, ...]] = (
        "skill_version_id",
        "skill_id",
        "version",
        "status",
        "created_by",
        "change_log",
    )
    json_fields: ClassVar[tuple[str, ...]] = (
        "prompt_spec",
        "input_schema",
        "output_schema",
        "runtime_policy",
        "tool_policy",
        "implementation_ref",
    )
    editable_fields: ClassVar[tuple[str, ...]] = (
        "status",
        "change_log",
        "prompt_spec",
        "input_schema",
        "output_schema",
        "runtime_policy",
        "tool_policy",
        "implementation_ref",
        "published_at",
        "updated_at",
    )

    skill_version_id: str
    skill_id: str
    version: str
    status: Literal["draft", "published", "archived"] = "draft"
    change_log: str = ""
    prompt_spec: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    runtime_policy: dict[str, Any] = Field(default_factory=dict)
    tool_policy: dict[str, Any] = Field(default_factory=dict)
    implementation_ref: dict[str, Any] = Field(default_factory=dict)
    checksum: str = ""
    created_by: str | None = None
    published_at: datetime | None = None


class AgentReleaseDocument(TimestampedDocument):
    """Agent 发布文档（集合 `agent_releases`）。"""
    collection_name: ClassVar[str] = "agent_releases"
    primary_key: ClassVar[str] = "agent_release_id"
    searchable_fields: ClassVar[tuple[str, ...]] = ("agent_release_id", "agent_id", "version", "status")
    json_fields: ClassVar[tuple[str, ...]] = ("graph_spec", "execution_policy")
    editable_fields: ClassVar[tuple[str, ...]] = (
        "status",
        "graph_spec",
        "execution_policy",
        "published_at",
        "updated_at",
    )

    agent_release_id: str
    agent_id: str
    version: str
    status: Literal["draft", "published", "archived"] = "draft"
    graph_spec: dict[str, Any] = Field(default_factory=dict)
    execution_policy: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    published_at: datetime | None = None


class AgentReleasePointerDocument(TimestampedDocument):
    """记录 Agent 当前/历史发布指针（集合 `agent_release_pointers`）。"""
    collection_name: ClassVar[str] = "agent_release_pointers"
    primary_key: ClassVar[str] = "agent_id"
    searchable_fields: ClassVar[tuple[str, ...]] = ("agent_id", "current_release_id", "previous_release_id")
    json_fields: ClassVar[tuple[str, ...]] = ()
    editable_fields: ClassVar[tuple[str, ...]] = (
        "current_release_id",
        "previous_release_id",
        "updated_by",
        "updated_at",
    )

    agent_id: str
    current_release_id: str
    previous_release_id: str | None = None
    updated_by: str | None = None


class TaskRunDocument(TimestampedDocument):
    """任务运行状态文档（集合 `task_runs`）。

    存储任务的执行上下文、状态、执行元数据与结果摘要。
    """
    collection_name: ClassVar[str] = "task_runs"
    primary_key: ClassVar[str] = "run_id"
    searchable_fields: ClassVar[tuple[str, ...]] = (
        "run_id",
        "task_kind",
        "status",
        "context.symbol",
        "trigger.kind",
        "agent.agent_id",
        "result.summary",
    )
    json_fields: ClassVar[tuple[str, ...]] = ("trigger", "context", "agent", "graph", "execution", "metrics", "result", "error", "search_tags")
    editable_fields: ClassVar[tuple[str, ...]] = ("status", "result", "error", "updated_at")

    run_id: str = Field(default_factory=lambda: _new_identifier("run"))
    task_kind: str = "research"
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    trigger: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    agent: dict[str, Any] = Field(default_factory=dict)
    graph: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    search_tags: list[str] = Field(default_factory=list)


class TaskEventDocument(MongoDocument):
    """任务执行事件（集合 `task_events`），适合用于事件流存储与回放。"""
    collection_name: ClassVar[str] = "task_events"
    primary_key: ClassVar[str] = "event_id"
    searchable_fields: ClassVar[tuple[str, ...]] = ("event_id", "run_id", "event_type", "node.node_id", "skill.skill_version_id")
    json_fields: ClassVar[tuple[str, ...]] = ("node", "agent", "skill", "payload", "trace")
    editable_fields: ClassVar[tuple[str, ...]] = ()

    event_id: str = Field(default_factory=lambda: _new_identifier("evt"))
    run_id: str
    seq: int
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node: dict[str, Any] = Field(default_factory=dict)
    agent: dict[str, Any] = Field(default_factory=dict)
    skill: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    trace: dict[str, Any] = Field(default_factory=dict)


class TaskArtifactDocument(MongoDocument):
    """任务产物（集合 `task_artifacts`），用于存储日志、二进制或 JSON 内容。"""
    collection_name: ClassVar[str] = "task_artifacts"
    primary_key: ClassVar[str] = "artifact_id"
    searchable_fields: ClassVar[tuple[str, ...]] = ("artifact_id", "run_id", "node_id", "artifact_type", "content_type")
    json_fields: ClassVar[tuple[str, ...]] = ("content",)
    editable_fields: ClassVar[tuple[str, ...]] = ()

    artifact_id: str = Field(default_factory=lambda: _new_identifier("artifact"))
    run_id: str
    node_id: str | None = None
    artifact_type: str
    content_type: str = "application/json"
    content: dict[str, Any] | list[Any] | str
    size_bytes: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskCheckpointDocument(MongoDocument):
    """任务检查点（集合 `task_checkpoints`），用于保存节点级别的中间状态。"""
    collection_name: ClassVar[str] = "task_checkpoints"
    primary_key: ClassVar[str] = "checkpoint_id"
    searchable_fields: ClassVar[tuple[str, ...]] = ("checkpoint_id", "run_id", "node_id", "checkpoint_type")
    json_fields: ClassVar[tuple[str, ...]] = ("state",)
    editable_fields: ClassVar[tuple[str, ...]] = ()

    checkpoint_id: str = Field(default_factory=lambda: _new_identifier("ckpt"))
    run_id: str
    seq: int
    node_id: str | None = None
    checkpoint_type: str
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NewsDocument(TimestampedDocument):
    """新闻文档（集合 `news_items`）。"""

    collection_name: ClassVar[str] = "news_items"
    primary_key: ClassVar[str] = "news_id"
    searchable_fields: ClassVar[tuple[str, ...]] = (
        "news_id",
        "source",
        "title",
        "summary",
        "market",
        "industry_tags",
        "concept_tags",
        "stock_tags",
        "tags",
        "dedupe_key",
    )
    json_fields: ClassVar[tuple[str, ...]] = (
        "industry_tags",
        "concept_tags",
        "stock_tags",
        "tags",
        "raw_payload",
    )
    editable_fields: ClassVar[tuple[str, ...]] = (
        "summary",
        "industry_tags",
        "concept_tags",
        "stock_tags",
        "tags",
        "credibility",
        "updated_at",
    )

    news_id: str = Field(default_factory=lambda: _new_identifier("news"))
    title: str
    content: str = ""
    summary: str = ""
    source: str
    source_url: str | None = None
    published_at: datetime | None = None
    market: str = "unknown"
    industry_tags: list[str] = Field(default_factory=list)
    concept_tags: list[str] = Field(default_factory=list)
    stock_tags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    credibility: float = Field(default=0.5, ge=0.0, le=1.0)
    dedupe_key: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class SourcePriorityRouteDocument(TimestampedDocument):
    """数据源路由优先级配置文档。"""

    collection_name: ClassVar[str] = "source_priority_routes"
    primary_key: ClassVar[str] = "route_id"
    searchable_fields: ClassVar[tuple[str, ...]] = (
        "route_id",
        "capability",
        "market",
        "interval",
        "enabled",
    )
    json_fields: ClassVar[tuple[str, ...]] = ("priorities", "metadata")
    editable_fields: ClassVar[tuple[str, ...]] = (
        "priorities",
        "enabled",
        "metadata",
        "updated_at",
    )

    route_id: str
    capability: str
    market: str | None = None
    interval: str | None = None
    priorities: list[str] = Field(default_factory=list)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
