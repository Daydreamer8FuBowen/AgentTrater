import asyncio
import json
import logging
import os
from datetime import datetime

from agent_trader.ingestion.sources.baostock_source import BaoStockSource
from agent_trader.ingestion.models import FinancialReportQuery

logging.basicConfig(level=logging.INFO)


def _parse_opt_date(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d")


async def main():
    # Credentials and params can be provided via environment variables:
    # BAOSTOCK_USER, BAOSTOCK_PASS, BAOSTOCK_SYMBOL, BAOSTOCK_REPORT_TYPES,
    # BAOSTOCK_START, BAOSTOCK_END
    # Fixed test parameters (edit here to change test inputs)
    user = "anonymous"
    password = "123456"
    symbol = "sh.600000"
    report_types = ["profit", "growth"]
    start_dt = datetime(2022, 1, 1)
    end_dt = datetime(2023, 12, 31)

    source = BaoStockSource(user_id=user, password=password)

    query = FinancialReportQuery(
        symbol=symbol,
        market=None,
        start_time=start_dt,
        end_time=end_dt,
        extra={"report_types": report_types},
    )

    try:
        result = await source.fetch_financial_reports_unified(query)
    except Exception as exc:  # pragma: no cover - runtime test helper
        logging.exception("fetch_financial_reports_unified failed")
        raise

    print(json.dumps({
        "source": result.source,
        "route_key": {
            "capability": getattr(result.route_key, "capability", None),
            "market": str(getattr(result.route_key, "market", None)),
        },
        "count": len(result.payload) if result.payload is not None else 0,
        "metadata": result.metadata,
    }, ensure_ascii=False, indent=2))

    if result.payload:
        print("First record:")
        print(json.dumps(result.payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
