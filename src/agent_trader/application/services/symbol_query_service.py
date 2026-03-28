from __future__ import annotations

import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.storage.mongo.documents import BasicInfoDocument, KlineSyncStateDocument


def _to_sync_market(market: str | None) -> str | None:
    normalized = str(market or "").strip().lower()
    if normalized in {"sh", "sse"}:
        return "sse"
    if normalized in {"sz", "szse"}:
        return "szse"
    return normalized or None


class SymbolQueryService:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._basic_infos = database[BasicInfoDocument.collection_name]
        self._sync_states = database[KlineSyncStateDocument.collection_name]

    async def list_symbols(
        self,
        *,
        keyword: str | None,
        market: str | None,
        status: str | None,
        security_type: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        query = self._build_query(
            keyword=keyword,
            market=market,
            status=status,
            security_type=security_type,
        )
        page_value = max(page, 1)
        page_size_value = max(min(page_size, 200), 1)
        skip = (page_value - 1) * page_size_value

        projection = {
            "_id": 0,
            "symbol": 1,
            "name": 1,
            "market": 1,
            "status": 1,
            "security_type": 1,
            "industry": 1,
            "area": 1,
            "updated_at": 1,
        }
        total = await self._basic_infos.count_documents(query)
        cursor = (
            self._basic_infos.find(query, projection)
            .sort("symbol", 1)
            .skip(skip)
            .limit(page_size_value)
        )
        items = await cursor.to_list(length=page_size_value)

        return {
            "total": total,
            "page": page_value,
            "page_size": page_size_value,
            "items": items,
        }

    async def list_symbols_with_monitor(
        self,
        *,
        keyword: str | None,
        market: str | None,
        status: str | None,
        security_type: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        payload = await self.list_symbols(
            keyword=keyword,
            market=market,
            status=status,
            security_type=security_type,
            page=page,
            page_size=page_size,
        )
        items = payload["items"]
        if not items:
            payload["items"] = []
            return payload

        symbols = [str(item.get("symbol", "")).upper() for item in items]
        sync_markets = {_to_sync_market(item.get("market")) for item in items}
        sync_markets.discard(None)

        state_cursor = self._sync_states.find(
            {
                "symbol": {"$in": symbols},
                "interval": {"$in": ["5m", "1d"]},
            },
            {
                "_id": 0,
                "symbol": 1,
                "interval": 1,
                "status": 1,
                "last_bar_time": 1,
            },
        )
        state_docs = await state_cursor.to_list(length=None)
        latest_state: dict[str, dict[str, Any]] = {}
        for doc in state_docs:
            symbol = str(doc.get("symbol", "")).upper()
            interval = str(doc.get("interval", ""))
            prev = latest_state.get(symbol)
            if prev is None:
                latest_state[symbol] = doc
                continue
            prev_interval = str(prev.get("interval", ""))
            if interval == "5m" and prev_interval != "5m":
                latest_state[symbol] = doc

        enriched_items: list[dict[str, Any]] = []
        for item in items:
            symbol = str(item.get("symbol", "")).upper()
            sync_market = _to_sync_market(item.get("market"))
            state = latest_state.get(symbol, {})
            enriched = dict(item)
            enriched["d1_completion_ratio"] = 0.0
            enriched["d1_progress_status"] = "not_tracked"
            enriched["latest_bar_time"] = state.get("last_bar_time")
            enriched["sync_status"] = str(state.get("status", "unknown"))
            enriched["latest_interval"] = state.get("interval")
            enriched["lag_seconds"] = 0.0
            enriched_items.append(enriched)

        payload["items"] = enriched_items
        return payload

    async def get_symbol_detail(self, symbol: str) -> dict[str, Any] | None:
        normalized_symbol = symbol.strip().upper()
        basic_info = await self._basic_infos.find_one({"symbol": normalized_symbol}, {"_id": 0})
        if basic_info is None:
            return None

        sync_market = _to_sync_market(basic_info.get("market"))
        state_cursor = self._sync_states.find(
            {
                "symbol": normalized_symbol,
                "market": sync_market,
            },
            {"_id": 0},
        ).sort("interval", 1)
        states = await state_cursor.to_list(length=None)

        return {
            "symbol": normalized_symbol,
            "basic_info": basic_info,
            "sync_market": sync_market,
            "sync_states": states,
            "d1_progress": None,
        }

    def _build_query(
        self,
        *,
        keyword: str | None,
        market: str | None,
        status: str | None,
        security_type: str | None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if market:
            query["market"] = market.strip().lower()
        if status:
            query["status"] = status.strip()
        if security_type:
            query["security_type"] = security_type.strip().lower()
        cleaned_keyword = (keyword or "").strip()
        if cleaned_keyword:
            escaped = re.escape(cleaned_keyword)
            query["$or"] = [
                {"symbol": {"$regex": escaped, "$options": "i"}},
                {"name": {"$regex": escaped, "$options": "i"}},
            ]
        return query
