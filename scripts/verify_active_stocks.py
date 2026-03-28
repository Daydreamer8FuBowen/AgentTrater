import asyncio
from agent_trader.core.config import Settings
from agent_trader.storage.connection_manager import AppConnectionManager
from agent_trader.domain.models import ExchangeKind

async def main():
    settings = Settings(_env_file='.env.local')
    manager = AppConnectionManager.from_settings(settings)
    await manager.start()
    
    db = manager.mongo_manager.database
    from agent_trader.storage.mongo.repository import MongoBasicInfoRepository
    repo = MongoBasicInfoRepository(db)
    
    sse_symbols = await repo.get_active_stock_symbols(ExchangeKind.SSE)
    szse_symbols = await repo.get_active_stock_symbols(ExchangeKind.SZSE)
    
    print(f"SSE active stocks: {len(sse_symbols)}")
    if sse_symbols:
        print(f"Sample SSE: {sse_symbols[:5]}")
        
    print(f"SZSE active stocks: {len(szse_symbols)}")
    if szse_symbols:
        print(f"Sample SZSE: {szse_symbols[:5]}")
        
    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())