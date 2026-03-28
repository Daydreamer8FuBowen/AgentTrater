from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_trader.application.data_access.gateway import (
    BasicInfoSourceFetchOutcome,
    DataAccessGateway,
)
from agent_trader.core.time import utc_now
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
        """从所有已注册数据源拉取 basic_info，合并去重后快照写入 MongoDB。

        这是 K 线同步的前置依赖：`KlineSync` 通过 `basic_infos` 集合获取
        可参与 Tier 分层的 symbol 列表。若本函数从未执行，`basic_infos` 为空，
        worker 的 `symbols=0` 将导致无任何 K 线数据被采集。

        执行步骤：
          1. 并发向所有已注册源发起 basic_info 请求（通过 gateway）。
          2. 以"主源优先，缺失字段回填，冲突记录"的策略跨源合并。
          3. 将合并结果批量 upsert 到 MongoDB `basic_infos` 集合（以 symbol 为键）。
          4. 返回执行摘要，含成功/失败源、去重数量、落库统计。

        Args:
            market: 可选市场过滤（如 ExchangeKind.SSE）。为 None 时拉取所有市场。

        Returns:
            执行摘要 dict，包含以下字段：
            - requested_sources: 参与请求的数据源数量
            - input_count: 所有源返回的原始记录总数（合并前）
            - dedup_count: 按 symbol 去重后的唯一记录数
            - persisted: MongoDB upsert 统计（matched/modified/upserted）
            - failed_sources: 请求失败的源列表及错误信息
        """
        # 步骤 1：向所有源并发拉取，每个 outcome 包含源名称、结果或错误
        outcomes = await self._gateway.fetch_basic_info_from_all_sources(market=market)

        # 步骤 2：跨源合并——主源数据优先，其他源仅补充空缺字段，字段冲突会被记录但不覆盖
        merged, primary_source, source_trace, conflict_fields = self._merge_outcomes(
            outcomes, market
        )

        # 步骤 3：将合并结果转换为 MongoDB 文档，记录来源溯源与冲突字段
        now = utc_now()
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
                act_ent_type=_to_optional_str(record.act_ent_type),
                pe_ttm=record.pe_ttm,
                pe=record.pe,
                pb=record.pb,
                grossprofit_margin=record.grossprofit_margin,
                netprofit_margin=record.netprofit_margin,
                roe=record.roe,
                debt_to_assets=record.debt_to_assets,
                revenue=record.revenue,
                net_profit=record.net_profit,
                primary_source=primary_source.get(record.symbol),  # 提供该 symbol 主数据的源
                source_trace=source_trace.get(record.symbol, []),  # 贡献过该 symbol 的所有源
                conflict_fields=sorted(
                    conflict_fields.get(record.symbol, set())
                ),  # 跨源存在分歧的字段
                metadata={
                    "merged_sources": len(source_trace.get(record.symbol, [])),
                },
                updated_at=now,
            )
            for record in merged.values()
        ]

        # 步骤 4：批量 upsert，以 symbol 为唯一键，已存在则更新，不存在则插入
        async with self._uow_factory() as uow:
            persist_stats = await uow.basic_infos.upsert_many_by_symbol(docs)

        # 汇总失败源信息，便于调用方感知数据质量
        source_errors = [
            {"source": item.source_name, "error": item.error}
            for item in outcomes
            if item.error is not None
        ]

        return {
            "requested_sources": len(outcomes),
            "input_count": sum(
                len(item.result.payload) for item in outcomes if item.result is not None
            ),
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

                    if (
                        not _is_empty(current_value)
                        and not _is_empty(incoming_value)
                        and current_value != incoming_value
                    ):
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
        act_ent_type=_to_optional_str(record.act_ent_type),
        pe_ttm=record.pe_ttm,
        pe=record.pe,
        pb=record.pb,
        grossprofit_margin=record.grossprofit_margin,
        netprofit_margin=record.netprofit_margin,
        roe=record.roe,
        debt_to_assets=record.debt_to_assets,
        revenue=record.revenue,
        net_profit=record.net_profit,
    )


def _normalize_symbol(symbol: str, market: ExchangeKind | str | None, market_hint: ExchangeKind | None) -> str:
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


def _infer_symbol_suffix(
    symbol: str, market: ExchangeKind | str | None, market_hint: ExchangeKind | None
) -> str | None:
    if isinstance(market, ExchangeKind):
        market_value = market.value
    else:
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


def _normalize_market(
    market: ExchangeKind | str | None, symbol: str, market_hint: ExchangeKind | None
) -> ExchangeKind | None:
    if isinstance(market, ExchangeKind):
        market_value = market.value
    else:
        market_value = (market or "").strip().lower()
    if market_value in {"sh", "sse"}:
        return ExchangeKind.SSE
    if market_value in {"sz", "szse"}:
        return ExchangeKind.SZSE

    if symbol.endswith(".SH"):
        return ExchangeKind.SSE
    if symbol.endswith(".SZ"):
        return ExchangeKind.SZSE

    if market_hint == ExchangeKind.SSE:
        return ExchangeKind.SSE
    if market_hint == ExchangeKind.SZSE:
        return ExchangeKind.SZSE
    return None


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
