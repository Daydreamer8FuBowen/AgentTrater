"""MongoDB adapters."""

from agent_trader.storage.mongo.client import MongoConnectionManager, create_mongo_connection_manager
from agent_trader.storage.mongo.documents import (
	AgentDefinitionDocument,
	AgentReleaseDocument,
	AgentReleasePointerDocument,
	NewsDocument,
	SkillDefinitionDocument,
	SkillVersionDocument,
	TaskArtifactDocument,
	TaskCheckpointDocument,
	TaskEventDocument,
	TaskRunDocument,
)
from agent_trader.storage.mongo.repository import (
	MongoNewsRepository,
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
	"MongoNewsRepository",
	"MongoTaskArtifactRepository",
	"MongoTaskEventRepository",
	"MongoTaskRunRepository",
	"MongoUnitOfWork",
	"NewsDocument",
	"SkillDefinitionDocument",
	"SkillVersionDocument",
	"TaskArtifactDocument",
	"TaskCheckpointDocument",
	"TaskEventDocument",
	"TaskRunDocument",
	"create_mongo_connection_manager",
]