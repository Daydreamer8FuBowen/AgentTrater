import asyncio
from typing import Any
from pymongo import UpdateOne

from agent_trader.core.config import Settings
from agent_trader.storage.connection_manager import AppConnectionManager

async def migrate_status() -> None:
    settings = Settings(_env_file='.env.local')
    manager = AppConnectionManager.from_settings(settings)
    await manager.start()
    
    db = manager.mongo_manager.database
    collection = db["basic_infos"]
    
    # 查找所有 status 不是 "0" 或 "1" 的文档
    cursor = collection.find({"status": {"$nin": ["0", "1", None]}})
    docs = await cursor.to_list(length=None)
    
    print(f"Found {len(docs)} documents to migrate.")
    
    updates = []
    active_count = 0
    inactive_count = 0
    
    for doc in docs:
        symbol = doc["symbol"]
        old_status = doc.get("status")
        
        new_status = "0"
        
        if isinstance(old_status, str):
            val = old_status.lower().strip()
            if val in ["l", "listed", "active", "1"]:
                new_status = "1"
        elif old_status == 1 or old_status is True:
            new_status = "1"
            
        if new_status == "1":
            active_count += 1
        else:
            inactive_count += 1
            
        updates.append(
            UpdateOne(
                {"symbol": symbol},
                {"$set": {"status": new_status}}
            )
        )
        
    if updates:
        # 分批写入
        batch_size = 1000
        total_modified = 0
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            result = await collection.bulk_write(batch)
            total_modified += result.modified_count
        print(f"Migrated: {total_modified} documents updated.")
        print(f"Mapped to active ('1'): {active_count}")
        print(f"Mapped to inactive ('0'): {inactive_count}")
    else:
        print("No documents needed migration.")
        
    await manager.close()

if __name__ == "__main__":
    asyncio.run(migrate_status())
