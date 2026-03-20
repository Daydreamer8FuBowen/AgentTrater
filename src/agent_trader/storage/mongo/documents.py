from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _new_identifier(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class MongoDocument(BaseModel):
    """Mongo 文档实体基类。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TimestampedDocument(MongoDocument):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentDefinitionDocument(TimestampedDocument):
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