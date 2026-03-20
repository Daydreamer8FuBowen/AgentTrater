"""同花顺（10jqka）数据源适配器示例。"""

from typing import List, Dict, Any

from ..utils import get_json


def fetch_news(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """占位实现：返回空列表，实际实现应解析目标站点页面或 API。"""
    # TODO: 实现同花顺的抓取逻辑
    return []
