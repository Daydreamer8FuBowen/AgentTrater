"""MongoDB adapters."""

from agent_trader.storage.mongo.client import MongoConnectionManager, create_mongo_connection_manager
from agent_trader.storage.mongo.documents import (
	AgentDefinitionDocument,
	AgentReleaseDocument,
	AgentReleasePointerDocument,
	SkillDefinitionDocument,
	SkillVersionDocument,
	TaskArtifactDocument,
	TaskCheckpointDocument,
	TaskEventDocument,
	TaskRunDocument,
)
from agent_trader.storage.mongo.repository import (
	MongoTaskArtifactRepository,
	MongoTaskEventRepository,
	MongoTaskRunRepository,
)
from agent_trader.storage.mongo.unit_of_work import MongoUnitOfWork

__all__ = [
	"AgentDefinitionDocument",
	"AgentReleaseDocument",
	"AgentReleasePointerDocument",
	"MongoConnectionManager",
	"MongoTaskArtifactRepository",
	"MongoTaskEventRepository",
	"MongoTaskRunRepository",
	"MongoUnitOfWork",
	"SkillDefinitionDocument",
	"SkillVersionDocument",
	"TaskArtifactDocument",
	"TaskCheckpointDocument",
	"TaskEventDocument",
	"TaskRunDocument",
	"create_mongo_connection_manager",
]