import asyncio
import json
import logging

from agent_trader.ingestion.sources.baostock_source import BaoStockSource

logging.basicConfig(level=logging.INFO)

async def main():
    source = BaoStockSource()
    result = await source.fetch_basic_info()
    # print summary
    print(json.dumps({
        "source": result.source,
        "route_key": {
            "capability": result.route_key.capability if hasattr(result.route_key, 'capability') else None,
            "market": str(result.route_key.market) if hasattr(result.route_key, 'market') else None,
            "interval": result.route_key.interval if hasattr(result.route_key, 'interval') else None,
        },
        "count": len(result.payload) if result.payload is not None else 0,
        "metadata": result.metadata,
    }, ensure_ascii=False, indent=2))
    if result.payload:
        # print first record
        print(result.payload)

if __name__ == '__main__':
    asyncio.run(main())
