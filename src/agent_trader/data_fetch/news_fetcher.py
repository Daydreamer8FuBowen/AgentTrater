"""新闻获取主文件：协调多个数据源适配器，并提供统一接口。"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Protocol

from agent_trader.data_fetch.cleaning import build_minimal_cleaned_news
from agent_trader.data_fetch.models import CleanedNewsItem


class NewsCleaner(Protocol):
    def clean(self, *, source: str, payload: dict[str, Any]) -> CleanedNewsItem: ...


class NewsFetcher:
    """协调多个新闻/数据源适配器的简单管理器。

    用法示例：
        nf = NewsFetcher()
        nf.register_source("eastmoney", eastmoney.fetch_news)
        nf.fetch_all(query="股票", limit=5)
    """

    def __init__(self, cleaner: NewsCleaner | None = None) -> None:
        self.sources: Dict[str, Callable[..., List[Dict[str, Any]]]] = {}
        self._cleaner = cleaner

    def set_cleaner(self, cleaner: NewsCleaner) -> None:
        """设置统一新闻清洗器。"""
        self._cleaner = cleaner

    def register_source(self, name: str, fetcher: Callable[..., List[Dict[str, Any]]]) -> None:
        """注册一个数据源适配器。"""
        self.sources[name] = fetcher

    def fetch_from_source_raw(self, name: str, *args, **kwargs) -> List[Dict[str, Any]]:
        """从指定数据源抓取原始条目列表。"""
        if name not in self.sources:
            raise KeyError(f"source not registered: {name}")
        return self.sources[name](*args, **kwargs)

    def fetch_from_source(self, name: str, *args, verbose: bool = False, **kwargs) -> List[CleanedNewsItem]:
        """从指定数据源抓取，并返回清洗后的条目列表。

        参数:
            verbose: 如果为 True，将打印每个清洗后的条目（用于调试/查看处理结果）。
        """
        items = self.fetch_from_source_raw(name, *args, **kwargs)
        cleaned = self._clean_items(name, items)
        if verbose:
            for c in cleaned:
                print(f"[NewsFetcher] source={name} cleaned={c}")
        return cleaned

    def fetch_all_raw(self, *args, **kwargs) -> Dict[str, Any]:
        """从所有注册源抓取原始结果，按来源分组返回。"""
        results: Dict[str, Any] = {}
        for name, fn in self.sources.items():
            try:
                results[name] = fn(*args, **kwargs)
            except Exception as e:  # pragma: no cover - adapter may raise
                results[name] = {"error": str(e)}
        return results

    def fetch_all(self, *args, verbose: bool = False, **kwargs) -> List[CleanedNewsItem]:
        """从所有注册源抓取，并默认返回清洗后的合并列表。

        参数:
            verbose: 如果为 True，将打印每个清洗后的条目（用于调试/查看处理结果）。
        """
        results = self.fetch_all_raw(*args, **kwargs)
        cleaned_items: List[CleanedNewsItem] = []
        for name, payload in results.items():
            if isinstance(payload, dict) and "error" in payload:
                continue
            if isinstance(payload, list):
                cleaned_items.extend(self._clean_items(name, payload))
                continue
            if isinstance(payload, dict):
                cleaned_items.extend(self._clean_items(name, [payload]))
        if verbose:
            for c in cleaned_items:
                print(f"[NewsFetcher] cleaned={c}")
        return cleaned_items

    def _clean_items(self, source: str, payloads: List[Dict[str, Any]]) -> List[CleanedNewsItem]:
        cleaned_items: List[CleanedNewsItem] = []
        for payload in payloads:
            if self._cleaner is not None:
                cleaned_items.append(self._cleaner.clean(source=source, payload=payload))
                continue
            cleaned_items.append(build_minimal_cleaned_news(source=source, payload=payload))
        return cleaned_items
