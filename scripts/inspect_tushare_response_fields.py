from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

import tushare as ts

from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import KlineQuery
from agent_trader.ingestion.sources.tushare_source import TuShareSource


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:  # noqa: BLE001
        return


def _inspect_stock_basic(api: object) -> None:
    default_fields = [
        "ts_code",
        "name",
        "industry",
        "area",
        "list_date",
        "list_status",
    ]
    candidate_extra = [
        "act_ent_type",
        "pe_ttm",
        "pe",
        "pb",
        "grossprofit_margin",
        "netprofit_margin",
        "roe",
        "debt_to_assets",
        "revenue",
        "net_profit",
        "market",
    ]

    requested = ",".join(default_fields + candidate_extra)
    print("== stock_basic ==")
    print(f"request.fields={requested}")
    try:
        df = api.stock_basic(exchange="", list_status="L", fields=requested)
    except Exception as exc:  # noqa: BLE001
        print(f"stock_basic failed with extended fields: {exc!r}")
        try:
            df = api.stock_basic(exchange="", list_status="L", fields=",".join(default_fields))
        except Exception as fallback_exc:  # noqa: BLE001
            print(f"stock_basic failed with default fields: {fallback_exc!r}")
            print()
            return

    columns = list(getattr(df, "columns", []))
    print(f"returned.columns({len(columns)})={columns}")
    present_extra = [name for name in candidate_extra if name in columns]
    print(f"present.extra({len(present_extra)})={present_extra}")
    print()


def _inspect_pro_bar(api: object) -> None:
    symbol = (os.getenv("TUSHARE_SAMPLE_SYMBOL") or "000001.SZ").strip()
    days = int((os.getenv("TUSHARE_SAMPLE_DAYS") or "10").strip())
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    print("== pro_bar ==")
    print(f"symbol={symbol} freq=D range=[{start_str},{end_str}]")
    try:
        df = ts.pro_bar(ts_code=symbol, start_date=start_str, end_date=end_str, freq="D", api=api)
    except Exception as exc:  # noqa: BLE001
        print(f"pro_bar failed: {exc!r}")
        print()
        return
    columns = list(getattr(df, "columns", []))
    print(f"returned.columns({len(columns)})={columns}")
    if df is not None and not getattr(df, "empty", True):
        row = df.iloc[0].to_dict()
        print(f"first.row.keys({len(row)})={sorted(row.keys())}")
    print()


async def _inspect_fetch_klines_unified() -> None:
    symbol = (os.getenv("TUSHARE_SAMPLE_SYMBOL") or "000001.SZ").strip()
    days = int((os.getenv("TUSHARE_SAMPLE_DAYS") or "10").strip())
    end_time = datetime.now().replace(second=0, microsecond=0)
    start_time = (end_time - timedelta(days=days)).replace(second=0, microsecond=0)
    market = ExchangeKind.SZSE if symbol.upper().endswith(".SZ") else ExchangeKind.SSE

    print("== fetch_klines_unified (TuShareSource) ==")
    print(
        "query="
        f"symbol={symbol} market={market.value} interval={BarInterval.D1.value} "
        f"range=[{start_time.isoformat()},{end_time.isoformat()}]"
    )
    try:
        source = TuShareSource(
            token=_require_env("TUSHARE_TOKEN"), http_url=os.getenv("TUSHARE_API_URL")
        )
        result = await source.fetch_klines_unified(
            KlineQuery(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                interval=BarInterval.D1,
                market=market,
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"fetch_klines_unified failed: {exc!r}")
        print()
        return

    print(f"result.source={result.source}")
    print(f"result.route_key={result.route_key.as_storage_key()}")
    print(f"result.metadata={result.metadata}")
    print(f"payload.count={len(result.payload)}")
    if result.payload:
        first = result.payload[0]
        last = result.payload[-1]
        print(f"payload.first.bar_time={first.bar_time.isoformat()}")
        print(f"payload.last.bar_time={last.bar_time.isoformat()}")
        print("payload.sample(3)=")
        for item in result.payload[:3]:
            print(
                {
                    "symbol": item.symbol,
                    "bar_time": item.bar_time.isoformat(),
                    "interval": item.interval,
                    "open": item.open,
                    "high": item.high,
                    "low": item.low,
                    "close": item.close,
                    "volume": item.volume,
                    "amount": item.amount,
                    "change_pct": item.change_pct,
                    "turnover_rate": item.turnover_rate,
                    "adjusted": item.adjusted,
                }
            )
    print()


def main() -> None:
    _load_env_file(".env.local")
    token = _require_env("TUSHARE_TOKEN")
    http_url = (os.getenv("TUSHARE_API_URL") or "").strip()

    if http_url:
        api = ts.pro_api(token)
        api._DataApi__token = token
        api._DataApi__http_url = http_url
    else:
        ts.set_token(token)
        api = ts.pro_api()

    _inspect_stock_basic(api)
    _inspect_pro_bar(api)
    asyncio.run(_inspect_fetch_klines_unified())


if __name__ == "__main__":
    main()
