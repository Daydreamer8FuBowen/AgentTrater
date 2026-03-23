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

### 10jqka 新闻源（TuShare 驱动）

```py
from agent_trader.data_fetch import NewsFetcher
from agent_trader.data_fetch.sources import _10jqka

# 需要在环境变量中设置 TUSHARE_TOKEN
fetcher = NewsFetcher()
fetcher.register_source("10jqka", _10jqka.fetch_news)
news = fetcher.fetch_from_source("10jqka", query="银行", limit=20)
```

> `fetch_news` 支持 `keywords`, `symbol`, `start_time`, `end_time`, `token` 等参数，
> 实现逻辑与 `ingestion/sources/tushare_source.py` 中的新闻拉取一致。

后续建议：
- 为每个适配器实现重试、限速和错误处理
- 将 IO 密集操作改为异步（`aiohttp`）以提高吞吐
- 为敏感/受限来源加入合规许可检查
