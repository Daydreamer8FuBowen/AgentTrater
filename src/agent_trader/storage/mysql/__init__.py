"""MySQL adapters.

当前模块对外暴露两类能力：
- 连接与 session 管理
- 与 domain / storage protocol 对齐的 repository / unit of work 实现
"""

from agent_trader.application.services.mysql_trigger_service import MySQLUnitOfWork
from agent_trader.storage.mysql.client import MySQLConnectionManager, create_mysql_connection_manager
from agent_trader.storage.mysql.repository import MySQLOpportunityRepository, MySQLResearchTaskRepository

__all__ = [
	"MySQLConnectionManager",
	"MySQLUnitOfWork",
	"MySQLOpportunityRepository",
	"MySQLResearchTaskRepository",
	"create_mysql_connection_manager",
]