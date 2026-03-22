"""MongoDB adapters."""

from agent_trader.storage.mongo.client import MongoConnectionManager, create_mongo_connection_manager
from agent_trader.storage.mongo.documents import (
	AgentDefinitionDocument,
	AgentReleaseDocument,
	AgentReleasePointerDocument,
	NewsDocument,
	SkillDefinitionDocument,
	SkillVersionDocument,
	SourcePriorityRouteDocument,
	SourceRouteHealthDocument,
	TaskArtifactDocument,
	TaskCheckpointDocument,
	TaskEventDocument,
	TaskRunDocument,
)
from agent_trader.storage.mongo.repository import (
	MongoNewsRepository,
	MongoSourcePriorityRepository,
	MongoSourceRouteHealthRepository,
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
	"MongoSourcePriorityRepository",
	"MongoSourceRouteHealthRepository",
	"MongoUnitOfWork",
	"NewsDocument",
	"SkillDefinitionDocument",
	"SkillVersionDocument",
	"SourcePriorityRouteDocument",
	"SourceRouteHealthDocument",
	"TaskArtifactDocument",
	"TaskCheckpointDocument",
	"TaskEventDocument",
	"TaskRunDocument",
	"create_mongo_connection_manager",
]