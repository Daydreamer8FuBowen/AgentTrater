from __future__ import annotations

from datetime import datetime
from collections.abc import Callable
from typing import Any

from agent_trader.application.data_access.gateway import (
    BasicInfoSourceFetchOutcome,
    DataAccessGateway,
)
from agent_trader.domain.models import ExchangeKind
from agent_trader.ingestion.models import BasicInfoRecord
from agent_trader.storage.base import UnitOfWork
from agent_trader.storage.mongo.documents import BasicInfoDocument

_MERGE_FIELDS: tuple[str, ...] = (
    "name",
    "industry",
    "area",
    "market",
    "list_date",
    "status",
    "delist_date",
    "security_type",
)


class BasicInfoAggregationService:
    """聚合全源 basic_info 并按 symbol 快照落库。"""

    def __init__(
        self,
        *,
        gateway: DataAccessGateway,
        uow_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._gateway = gateway
        self._uow_factory = uow_factory

    async def sync_basic_info_snapshot(
        self,
        market: ExchangeKind | None = None,
    ) -> dict[str, Any]:
        outcomes = await self._gateway.fetch_basic_info_from_all_sources(market=market)
        merged, primary_source, source_trace, conflict_fields = self._merge_outcomes(outcomes, market)

        now = datetime.utcnow()
        docs = [
            BasicInfoDocument(
                symbol=record.symbol,
                name=record.name,
                industry=record.industry,
                area=record.area,
                market=record.market,
                list_date=record.list_date,
                status=_to_optional_str(record.status),
                delist_date=record.delist_date,
                security_type=_to_optional_str(record.security_type),
                primary_source=primary_source.get(record.symbol),
                source_trace=source_trace.get(record.symbol, []),
                conflict_fields=sorted(conflict_fields.get(record.symbol, set())),
                metadata={
                    "merged_sources": len(source_trace.get(record.symbol, [])),
                },
                updated_at=now,
            )
            for record in merged.values()
        ]

        async with self._uow_factory() as uow:
            persist_stats = await uow.basic_infos.upsert_many_by_symbol(docs)

        source_errors = [
            {"source": item.source_name, "error": item.error}
            for item in outcomes
            if item.error is not None
        ]

        return {
            "requested_sources": len(outcomes),
            "input_count": sum(len(item.result.payload) for item in outcomes if item.result is not None),
            "dedup_count": len(merged),
            "persisted": persist_stats,
            "failed_sources": source_errors,
        }

    def _merge_outcomes(
        self,
        outcomes: list[BasicInfoSourceFetchOutcome],
        market: ExchangeKind | None,
    ) -> tuple[
        dict[str, BasicInfoRecord],
        dict[str, str],
        dict[str, list[str]],
        dict[str, set[str]],
    ]:
        merged: dict[str, BasicInfoRecord] = {}
        primary_source: dict[str, str] = {}
        source_trace: dict[str, list[str]] = {}
        conflict_fields: dict[str, set[str]] = {}

        for outcome in outcomes:
            if outcome.result is None:
                continue

            for raw_record in outcome.result.payload:
                normalized_record = _normalize_record(raw_record, market)
                if not normalized_record.symbol:
                    continue

                if normalized_record.symbol not in merged:
                    merged[normalized_record.symbol] = normalized_record
                    primary_source[normalized_record.symbol] = outcome.source_name
                    source_trace[normalized_record.symbol] = [outcome.source_name]
                    conflict_fields[normalized_record.symbol] = set()
                    continue

                if outcome.source_name not in source_trace[normalized_record.symbol]:
                    source_trace[normalized_record.symbol].append(outcome.source_name)

                target = merged[normalized_record.symbol]
                for field_name in _MERGE_FIELDS:
                    current_value = getattr(target, field_name)
                    incoming_value = getattr(normalized_record, field_name)
                    if _is_empty(current_value) and not _is_empty(incoming_value):
                        setattr(target, field_name, incoming_value)
                        continue

                    if (not _is_empty(current_value) and not _is_empty(incoming_value) and current_value != incoming_value):
                        conflict_fields[normalized_record.symbol].add(field_name)

        return merged, primary_source, source_trace, conflict_fields


def _normalize_record(
    record: BasicInfoRecord,
    market_hint: ExchangeKind | None,
) -> BasicInfoRecord:
    symbol = _normalize_symbol(record.symbol, record.market, market_hint)
    market = _normalize_market(record.market, symbol, market_hint)

    return BasicInfoRecord(
        symbol=symbol,
        name=record.name,
        industry=record.industry,
        area=record.area,
        market=market,
        list_date=record.list_date,
        status=_to_optional_str(record.status),
        delist_date=record.delist_date,
        security_type=_to_optional_str(record.security_type),
    )


def _normalize_symbol(symbol: str, market: str | None, market_hint: ExchangeKind | None) -> str:
    text = symbol.strip()
    if not text:
        return ""

    lower = text.lower()
    if lower.startswith(("sh.", "sz.")):
        prefix = lower[:2]
        code = text.split(".", maxsplit=1)[1]
        return f"{code}.{prefix.upper()}"

    if "." in text:
        code, suffix = text.split(".", maxsplit=1)
        suffix = suffix.upper()
        if suffix in {"SH", "SZ"}:
            return f"{code}.{suffix}"

    suffix = _infer_symbol_suffix(text, market, market_hint)
    return f"{text}.{suffix}" if suffix else text


def _infer_symbol_suffix(symbol: str, market: str | None, market_hint: ExchangeKind | None) -> str | None:
    market_value = (market or "").strip().lower()
    if market_value in {"sh", "sse"}:
        return "SH"
    if market_value in {"sz", "szse"}:
        return "SZ"

    if market_hint == ExchangeKind.SSE:
        return "SH"
    if market_hint == ExchangeKind.SZSE:
        return "SZ"

    if symbol.startswith(("6", "9")):
        return "SH"
    if symbol.startswith(("0", "2", "3")):
        return "SZ"
    return None


def _normalize_market(market: str | None, symbol: str, market_hint: ExchangeKind | None) -> str | None:
    market_value = (market or "").strip().lower()
    if market_value in {"sh", "sz"}:
        return market_value
    if market_value == "sse":
        return "sh"
    if market_value == "szse":
        return "sz"

    if symbol.endswith(".SH"):
        return "sh"
    if symbol.endswith(".SZ"):
        return "sz"

    if market_hint == ExchangeKind.SSE:
        return "sh"
    if market_hint == ExchangeKind.SZSE:
        return "sz"
    return None


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
