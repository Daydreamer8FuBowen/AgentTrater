"""MongoDB adapters."""

from agent_trader.storage.mongo.client import (
    MongoConnectionManager,
    create_mongo_connection_manager,
)
from agent_trader.storage.mongo.documents import (
    AgentDefinitionDocument,
    AgentReleaseDocument,
    AgentReleasePointerDocument,
    BasicInfoDocument,
    NewsDocument,
    SkillDefinitionDocument,
    SkillVersionDocument,
    SourcePriorityRouteDocument,
    TaskArtifactDocument,
    TaskCheckpointDocument,
    TaskEventDocument,
    TaskRunDocument,
)
from agent_trader.storage.mongo.repository import (
    MongoBasicInfoRepository,
    MongoNewsRepository,
    MongoSourcePriorityRepository,
    MongoTaskArtifactRepository,
    MongoTaskEventRepository,
    MongoTaskRunRepository,
)
from agent_trader.storage.mongo.unit_of_work import MongoUnitOfWork

__all__ = [
    "AgentDefinitionDocument",
    "AgentReleaseDocument",
    "AgentReleasePointerDocument",
    "BasicInfoDocument",
    "MongoConnectionManager",
    "MongoBasicInfoRepository",
    "MongoNewsRepository",
    "MongoTaskArtifactRepository",
    "MongoTaskEventRepository",
    "MongoTaskRunRepository",
    "MongoSourcePriorityRepository",
    "MongoUnitOfWork",
    "NewsDocument",
    "SkillDefinitionDocument",
    "SkillVersionDocument",
    "SourcePriorityRouteDocument",
    "TaskArtifactDocument",
    "TaskCheckpointDocument",
    "TaskEventDocument",
    "TaskRunDocument",
    "create_mongo_connection_manager",
]
