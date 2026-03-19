"""
TuShare 数据源适配器

提供从 TuShare 获取中国股票市场数据的接口。
TuShare 是一个提供 A 股、港股、期货等多市场数据的数据库。

支持的数据类型：
- K线数据（日线、周线、月线等）
- 财报数据
- 行业信息
- 股票基本信息
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import tushare as ts

from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import RawEvent

logger = logging.getLogger(__name__)


class TuShareSource:
    """
    TuShare 数据源适配器，负责从 TuShare API 获取原始股票数据。

    Attributes:
        token (str): TuShare API token，用于认证请求
        pro (tushare.TushareAPI): TuShare Pro API 客户端实例
        http_url (str): TuShare 数据源 URL（通常是国内加速节点）
    """

    def __init__(self, token: str, http_url: str = "http://lianghua.nanyangqiankun.top"):
        """
        初始化 TuShare 数据源。

        Args:
            token: TuShare API token（从 https://tushare.pro 获取）
            http_url: TuShare HTTP 数据源 URL，默认为国内加速节点
        """
        if not token:
            raise ValueError("TuShare token 不能为空，请在环境变量或配置中设置 TUSHARE_TOKEN")

        self.token = token
        self.http_url = http_url
        self.pro = ts.pro_api(token)
        # 关键配置：确保 token 和 HTTP URL 正确设置
        # 这两行代码保证能正常获取数据（特别是通过国内代理的情况）
        self.pro._DataApi__token = token
        self.pro._DataApi__http_url = http_url
        self.name = "tushare"

    @classmethod
    def from_settings(cls, settings: Any) -> TuShareSource:
        """
        从统一配置系统创建 TuShareSource 实例。

        Args:
            settings: 从 get_settings() 获取的 Settings 实例

        Returns:
            TuShareSource 实例

        Raises:
            ValueError: 如果配置中没有提供有效的 token
        """
        tushare_config = settings.tushare
        return cls(token=tushare_config.token, http_url=tushare_config.http_url)

    async def fetch_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        freq: str = "D",
    ) -> list[RawEvent]:
        """
        异步获取 K 线数据。

        Args:
            symbol: 股票代码（如 '000001.SZ' 表示平安银行）
            start_date: 开始日期（格式：YYYYMMDD）
            end_date: 结束日期（格式：YYYYMMDD）
            freq: 数据频率（D=日线，W=周线，M=月线）

        Returns:
            RawEvent 列表，每条 K 线数据包装为一个事件

        Examples:
            >>> source = TuShareSource(token="your_token")
            >>> events = await source.fetch_klines("000001.SZ", "20240101", "20240131")
        """
        try:
            # 在线程池中运行同步操作以避免阻塞事件循环
            df = await asyncio.to_thread(
                self.pro.daily,
                ts_code=symbol,
                start_date=start_date,
                end_date=end_date,
                freq=freq,
            )

            if df is None or df.empty:
                logger.warning(f"No kline data found for {symbol}")
                return []

            # 将每行数据转换为 RawEvent
            events = []
            for _, row in df.iterrows():
                payload = row.to_dict()
                # 转换日期格式为 datetime
                payload["trade_date"] = datetime.strptime(
                    str(payload["trade_date"]), "%Y%m%d"
                )
                event = RawEvent(
                    source=self.name,
                    payload=payload,
                )
                events.append(event)

            logger.info(f"Fetched {len(events)} klines for {symbol}")
            return events

        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            return []

    async def fetch_basic_info(self) -> list[RawEvent]:
        """
        异步获取股票基本信息。

        Returns:
            RawEvent 列表，每条股票信息作为一个事件
        """
        try:
            df = await asyncio.to_thread(self.pro.stock_basic, exchange="", list_status="L")

            if df is None or df.empty:
                logger.warning("No stock basic info found")
                return []

            events = []
            for _, row in df.iterrows():
                event = RawEvent(
                    source=f"{self.name}:stock_basic",
                    payload=row.to_dict(),
                )
                events.append(event)

            logger.info(f"Fetched {len(events)} stock basic infos")
            return events

        except Exception as e:
            logger.error(f"Error fetching stock basic info: {e}")
            return []

    async def fetch_daily_basic(
        self,
        trade_date: str | None = None,
    ) -> list[RawEvent]:
        """
        异步获取每日基础信息（PE、PB 等）。

        Args:
            trade_date: 交易日期（格式：YYYYMMDD），若为 None，则取最近交易日

        Returns:
            RawEvent 列表
        """
        try:
            if trade_date is None:
                # 获取最近交易日
                trade_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

            df = await asyncio.to_thread(
                self.pro.daily_basic,
                trade_date=trade_date,
            )

            if df is None or df.empty:
                logger.warning(f"No daily basic data found for {trade_date}")
                return []

            events = []
            for _, row in df.iterrows():
                event = RawEvent(
                    source=f"{self.name}:daily_basic",
                    payload=row.to_dict(),
                )
                events.append(event)

            logger.info(f"Fetched {len(events)} daily basic records")
            return events

        except Exception as e:
            logger.error(f"Error fetching daily basic: {e}")
            return []

    async def fetch(self) -> list[RawEvent]:
        """
        默认的 fetch 方法，获取最近一个交易日的所有数据。

        实现 SourceAdapter 协议的要求方法。

        Returns:
            RawEvent 列表
        """
        try:
            # 并发获取多个数据源
            klines, basic = await asyncio.gather(
                self.fetch_klines(
                    symbol="000001.SZ",
                    start_date=(datetime.now() - timedelta(days=1)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                ),
                self.fetch_daily_basic(),
            )
            return klines + basic
        except Exception as e:
            logger.error(f"Error in default fetch: {e}")
            return []
