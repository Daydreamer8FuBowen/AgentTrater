"""文档注册与索引定义。

该模块通过 `DocumentConfig` 将 Pydantic 文档模型与集合名称、主键、可搜索/可编辑/JSON 字段等元信息关联，
并在 `DOCUMENT_REGISTRY` 中集中声明每个集合应创建的索引（用于 `MongoConnectionManager.ensure_indexes()`）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel

from agent_trader.storage.mongo.documents import (
    AgentDefinitionDocument,
    AgentReleaseDocument,
    AgentReleasePointerDocument,
    BasicInfoDocument,
    CandidateDocument,
    KlineSyncStateDocument,
    MongoDocument,
    NewsDocument,
    PositionDocument,
    SkillDefinitionDocument,
    SkillVersionDocument,
    SourcePriorityRouteDocument,
    TaskArtifactDocument,
    TaskCheckpointDocument,
    TaskEventDocument,
    TaskRunDocument,
)


@dataclass(frozen=True)
class DocumentConfig:
    """描述一个文档对应的元信息（用于注册和索引创建）。

    字段：
      - `name`: 集合名
      - `model`: 对应的 Pydantic 模型类
      - `primary_key`: 主键字段名
      - `searchable_columns`: 建议用于搜索/过滤的字段路径
      - `json_columns`: 需要序列化为 JSON 的字段
      - `editable_columns`: 可通过 API 编辑的字段
      - `indexes`: 此集合应创建的 IndexModel 列表
    """

    name: str
    model: type[MongoDocument]
    primary_key: str
    searchable_columns: tuple[str, ...]
    json_columns: tuple[str, ...]
    editable_columns: tuple[str, ...]
    indexes: tuple[IndexModel, ...] = ()

    @property
    def columns(self) -> tuple[str, ...]:
        """返回模型声明的字段名元组（Pydantic 的 model_fields）。"""
        return tuple(self.model.model_fields.keys())


def _document_config(
    model: type[MongoDocument], *, indexes: tuple[IndexModel, ...] = ()
) -> DocumentConfig:
    return DocumentConfig(
        name=model.collection_name,
        model=model,
        primary_key=model.primary_key,
        searchable_columns=model.searchable_fields,
        json_columns=model.json_fields,
        editable_columns=model.editable_fields,
        indexes=indexes,
    )


DOCUMENT_REGISTRY: dict[str, DocumentConfig] = {
    config.name: config
    for config in (
        _document_config(
            AgentDefinitionDocument,
            indexes=(
                IndexModel([(AgentDefinitionDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("type", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("updated_at", DESCENDING)]),
            ),
        ),
        _document_config(
            SkillDefinitionDocument,
            indexes=(
                IndexModel([(SkillDefinitionDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("category", ASCENDING), ("status", ASCENDING)]),
            ),
        ),
        _document_config(
            SkillVersionDocument,
            indexes=(
                IndexModel([(SkillVersionDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("skill_id", ASCENDING), ("version", ASCENDING)], unique=True),
                IndexModel(
                    [("skill_id", ASCENDING), ("status", ASCENDING), ("published_at", DESCENDING)]
                ),
                IndexModel([("checksum", ASCENDING)]),
            ),
        ),
        _document_config(
            AgentReleaseDocument,
            indexes=(
                IndexModel([(AgentReleaseDocument.primary_key, ASCENDING)], unique=True),
                IndexModel(
                    [("agent_id", ASCENDING), ("status", ASCENDING), ("published_at", DESCENDING)]
                ),
            ),
        ),
        _document_config(
            AgentReleasePointerDocument,
            indexes=(
                IndexModel([(AgentReleasePointerDocument.primary_key, ASCENDING)], unique=True),
            ),
        ),
        _document_config(
            TaskRunDocument,
            indexes=(
                IndexModel([(TaskRunDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]),
                IndexModel([("context.symbol", ASCENDING), ("created_at", DESCENDING)]),
                IndexModel([("trigger.kind", ASCENDING), ("created_at", DESCENDING)]),
                IndexModel([("agent.agent_id", ASCENDING), ("created_at", DESCENDING)]),
            ),
        ),
        _document_config(
            TaskEventDocument,
            indexes=(
                IndexModel([(TaskEventDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("run_id", ASCENDING), ("seq", ASCENDING)], unique=True),
                IndexModel([("run_id", ASCENDING), ("timestamp", ASCENDING)]),
                IndexModel([("event_type", ASCENDING), ("timestamp", DESCENDING)]),
            ),
        ),
        _document_config(
            TaskArtifactDocument,
            indexes=(
                IndexModel([(TaskArtifactDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("run_id", ASCENDING), ("created_at", ASCENDING)]),
                IndexModel([("run_id", ASCENDING), ("artifact_type", ASCENDING)]),
            ),
        ),
        _document_config(
            TaskCheckpointDocument,
            indexes=(
                IndexModel([(TaskCheckpointDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("run_id", ASCENDING), ("seq", ASCENDING)]),
                IndexModel(
                    [("run_id", ASCENDING), ("node_id", ASCENDING), ("created_at", DESCENDING)]
                ),
            ),
        ),
        _document_config(
            NewsDocument,
            indexes=(
                IndexModel([(NewsDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("dedupe_key", ASCENDING)], unique=True),
                IndexModel([("source", ASCENDING), ("published_at", DESCENDING)]),
                IndexModel([("market", ASCENDING), ("published_at", DESCENDING)]),
                IndexModel([("stock_tags", ASCENDING), ("published_at", DESCENDING)]),
                IndexModel([("concept_tags", ASCENDING), ("published_at", DESCENDING)]),
                IndexModel([("credibility", DESCENDING), ("published_at", DESCENDING)]),
            ),
        ),
        _document_config(
            BasicInfoDocument,
            indexes=(
                IndexModel([(BasicInfoDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("market", ASCENDING), ("updated_at", DESCENDING)]),
                IndexModel([("primary_source", ASCENDING), ("updated_at", DESCENDING)]),
            ),
        ),
        _document_config(
            SourcePriorityRouteDocument,
            indexes=(
                IndexModel([(SourcePriorityRouteDocument.primary_key, ASCENDING)], unique=True),
                IndexModel(
                    [
                        ("capability", ASCENDING),
                        ("market", ASCENDING),
                        ("interval", ASCENDING),
                    ],
                    unique=True,
                ),
                IndexModel([("enabled", ASCENDING), ("updated_at", DESCENDING)]),
            ),
        ),
        _document_config(
            CandidateDocument,
            indexes=(
                IndexModel([(CandidateDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("symbol_id", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]),
                IndexModel([("deprecated_at", ASCENDING)]),
            ),
        ),
        _document_config(
            PositionDocument,
            indexes=(
                IndexModel([(PositionDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("symbol_id", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]),
                IndexModel([("deprecated_at", ASCENDING)]),
            ),
        ),
        _document_config(
            KlineSyncStateDocument,
            indexes=(
                IndexModel([(KlineSyncStateDocument.primary_key, ASCENDING)], unique=True),
                IndexModel(
                    [("symbol", ASCENDING), ("market", ASCENDING), ("interval", ASCENDING)],
                    unique=True,
                ),
                IndexModel([("market", ASCENDING), ("interval", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("last_bar_time", ASCENDING)]),
            ),
        ),
    )
}


def serialize_document(value: Any) -> Any:
    """将 Pydantic/原生对象序列化为可以写入 JSON 的结构。

    主要处理 datetime（调用 `isoformat()`）、list、dict 的递归序列化。
    """
    if isinstance(value, list):
        return [serialize_document(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_document(item) for key, item in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
