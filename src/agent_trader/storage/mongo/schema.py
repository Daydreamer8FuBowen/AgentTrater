from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel

from agent_trader.storage.mongo.documents import (
    AgentDefinitionDocument,
    AgentReleaseDocument,
    AgentReleasePointerDocument,
    MongoDocument,
    SkillDefinitionDocument,
    SkillVersionDocument,
    TaskArtifactDocument,
    TaskCheckpointDocument,
    TaskEventDocument,
    TaskRunDocument,
)


@dataclass(frozen=True)
class DocumentConfig:
    name: str
    model: type[MongoDocument]
    primary_key: str
    searchable_columns: tuple[str, ...]
    json_columns: tuple[str, ...]
    editable_columns: tuple[str, ...]
    indexes: tuple[IndexModel, ...] = ()

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(self.model.model_fields.keys())


def _document_config(model: type[MongoDocument], *, indexes: tuple[IndexModel, ...] = ()) -> DocumentConfig:
    return DocumentConfig(
        name=getattr(model, "collection_name"),
        model=model,
        primary_key=getattr(model, "primary_key"),
        searchable_columns=getattr(model, "searchable_fields"),
        json_columns=getattr(model, "json_fields"),
        editable_columns=getattr(model, "editable_fields"),
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
                IndexModel([("skill_id", ASCENDING), ("status", ASCENDING), ("published_at", DESCENDING)]),
                IndexModel([("checksum", ASCENDING)]),
            ),
        ),
        _document_config(
            AgentReleaseDocument,
            indexes=(
                IndexModel([(AgentReleaseDocument.primary_key, ASCENDING)], unique=True),
                IndexModel([("agent_id", ASCENDING), ("status", ASCENDING), ("published_at", DESCENDING)]),
            ),
        ),
        _document_config(
            AgentReleasePointerDocument,
            indexes=(IndexModel([(AgentReleasePointerDocument.primary_key, ASCENDING)], unique=True),),
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
                IndexModel([("run_id", ASCENDING), ("node_id", ASCENDING), ("created_at", DESCENDING)]),
            ),
        ),
    )
}


def serialize_document(value: Any) -> Any:
    if isinstance(value, list):
        return [serialize_document(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_document(item) for key, item in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value