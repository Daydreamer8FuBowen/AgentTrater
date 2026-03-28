from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict

from agent_trader.application.data_access.gateway import DataAccessGateway
from agent_trader.domain.models import ExchangeKind
from agent_trader.storage.base import UnitOfWork
from agent_trader.storage.mongo.documents import BasicInfoDocument

logger = logging.getLogger(__name__)


class CompanyDetailSyncService:
    """股票详细信息同步服务。

    每日定时拉取各市场的股票财务指标、利润表及估值数据，
    提取最新记录并写入 basic_infos 对应的嵌套 JSON 字段中。
    """

    def __init__(
        self,
        *,
        gateway: DataAccessGateway,
        uow_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._gateway = gateway
        self._uow_factory = uow_factory

    async def sync_market(self, market: ExchangeKind) -> None:
        """同步指定市场的股票详细信息。"""
        logger.info("开始同步市场 %s 的股票详细信息", market)

        async with self._uow_factory() as uow:
            symbols = await uow.basic_infos.get_active_stock_symbols(market)

        if not symbols:
            logger.info("市场 %s 没有活跃的股票需要同步", market)
            return

        success_count = 0
        failed_count = 0

        for symbol in symbols:
            try:
                await self._sync_symbol(symbol, market)
                success_count += 1
            except Exception as exc:  # noqa: BLE001
                # 根据需求：对于失败数据直接跳过，不记录同步进度
                logger.warning("同步股票 %s 的详细信息失败: %s", symbol, exc)
                failed_count += 1

        logger.info(
            "市场 %s 的股票详细信息同步完成，成功: %d，失败: %d",
            market,
            success_count,
            failed_count,
        )

    async def _sync_symbol(self, symbol: str, market: ExchangeKind) -> None:
        """同步单个股票的详细信息并更新到 MongoDB。"""
        # 并发获取可能会更好，但这里为了简单和稳定，顺序获取
        valuation_result = await self._gateway.fetch_company_valuation_unified(symbol, market)
        financial_result = await self._gateway.fetch_company_financial_indicators_unified(symbol, market)
        income_result = await self._gateway.fetch_company_income_statements_unified(symbol, market)

        latest_valuation = None
        if valuation_result and valuation_result.payload:
            # 假设返回结果已按时间排序（旧->新），取最后一条
            latest_valuation = asdict(valuation_result.payload[-1])

        latest_financial = None
        if financial_result and financial_result.payload:
            latest_financial = asdict(financial_result.payload[-1])

        latest_income = None
        if income_result and income_result.payload:
            latest_income = asdict(income_result.payload[-1])

        if not any([latest_valuation, latest_financial, latest_income]):
            logger.debug("股票 %s 没有新的详细信息数据", symbol)
            return

        update_fields = {}
        if latest_valuation:
            update_fields["latest_valuation"] = latest_valuation
            if "pe_ttm" in latest_valuation:
                update_fields["pe_ttm"] = latest_valuation["pe_ttm"]
            if "pe" in latest_valuation:
                update_fields["pe"] = latest_valuation["pe"]
            if "pb" in latest_valuation:
                update_fields["pb"] = latest_valuation["pb"]
        if latest_financial:
            update_fields["latest_financial_indicator"] = latest_financial
            if "grossprofit_margin" in latest_financial:
                update_fields["grossprofit_margin"] = latest_financial["grossprofit_margin"]
            if "netprofit_margin" in latest_financial:
                update_fields["netprofit_margin"] = latest_financial["netprofit_margin"]
            if "roe" in latest_financial:
                update_fields["roe"] = latest_financial["roe"]
            if "debt_to_assets" in latest_financial:
                update_fields["debt_to_assets"] = latest_financial["debt_to_assets"]
        if latest_income:
            update_fields["latest_income_statement"] = latest_income
            if "revenue" in latest_income:
                update_fields["revenue"] = latest_income["revenue"]
            if "net_profit" in latest_income:
                update_fields["net_profit"] = latest_income["net_profit"]
        
        logger.info("更新股票 %s 的详细信息: %s", symbol, update_fields)
        async with self._uow_factory() as uow:
            await uow.basic_infos.update_company_details(symbol, update_fields)
            await uow.commit()
