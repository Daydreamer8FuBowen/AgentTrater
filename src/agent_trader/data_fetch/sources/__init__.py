"""数据源适配层包。将各个适配器放在此目录下并由 `NewsFetcher` 注册使用。"""

from . import eastmoney, _10jqka, bloomberg

__all__ = ["eastmoney", "_10jqka", "bloomberg"]
