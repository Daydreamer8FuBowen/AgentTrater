数据抓取模块（data_fetch）

结构：

- `news_fetcher.py` - 抓取协调器（`NewsFetcher`）
- `sources/` - 各数据源适配器（示例：`eastmoney`, `10jqka`, `bloomberg`）
- `utils.py` - 简单的 HTTP 请求与解析工具

快速开始：

```py
from agent_trader.data_fetch import NewsFetcher
from agent_trader.data_fetch.sources import eastmoney

nf = NewsFetcher()
nf.register_source("eastmoney", eastmoney.fetch_news)
res = nf.fetch_all(query="股票", limit=5)
print(res)
```

后续建议：
- 为每个适配器实现重试、限速和错误处理
- 将 IO 密集操作改为异步（`aiohttp`）以提高吞吐
- 为敏感/受限来源加入合规许可检查
