from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def create_mongo_client(dsn: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(dsn)


def create_mongo_database(client: AsyncIOMotorClient, database_name: str) -> AsyncIOMotorDatabase:
    return client[database_name]