from __future__ import annotations

import os
import json

import pytest

from agent_trader.agents.news_preprocess_agent import NewsPreprocessAgent
from agent_trader.agents.models import get_agent_model_registry
from agent_trader.data_fetch.models import CleanedNewsItem


@pytest.mark.skipif(os.getenv("REAL_AGENT_TEST") != "1", reason="Real agent tests disabled, set REAL_AGENT_TEST=1 to enable")
def test_real_news_preprocess_agent_runs_and_returns_cleaned_item() -> None:
    """调用真实 Agent 并验证返回类型与基础字段（默认跳过，需设置 REAL_AGENT_TEST=1）。"""
    agent = NewsPreprocessAgent(agent_name="news_preprocess", model_registry=get_agent_model_registry())
    payload = {
        "title": "000001.SZ 银行板块走强",
        "content": "银行板块走强，000001.SZ 盘中拉升。",
        "published_at": "2026-03-20 09:30:00",
    }
    item = agent.clean(source="eastmoney", payload=payload)
    # 打印以便手动查看（测试输出），并进行基本断言保证形状正确
    print(json.dumps(item.__dict__, default=str, ensure_ascii=False, indent=2))
    assert isinstance(item, CleanedNewsItem)
    assert item.title
