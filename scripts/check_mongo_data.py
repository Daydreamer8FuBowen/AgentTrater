import asyncio
from agent_trader.core.config import Settings
from agent_trader.storage.connection_manager import AppConnectionManager

async def main():
    settings = Settings(_env_file='.env.local')
    manager = AppConnectionManager.from_settings(settings)
    await manager.start()
    
    db = manager.mongo_manager.database
    docs = await db.basic_infos.find().limit(3).to_list(length=3)
    for doc in docs:
        print(f"symbol: {doc.get('symbol')}, market: {doc.get('market')}, status: {doc.get('status')}, security_type: {doc.get('security_type')}")
        
    print("\nDistinct values in basic_infos:")
    markets = await db.basic_infos.distinct("market")
    statuses = await db.basic_infos.distinct("status")
    security_types = await db.basic_infos.distinct("security_type")
    
    print(f"markets: {markets}")
    print(f"statuses: {statuses}")
    print(f"security_types: {security_types}")
    
    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())