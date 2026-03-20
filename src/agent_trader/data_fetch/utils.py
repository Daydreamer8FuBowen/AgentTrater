"""抓取通用工具函数（HTTP 请求、简单解析）。

注意：生产环境可以替换为更健壮的实现（aiohttp、重试、代理、限速等）。
"""

from typing import Any, Dict, Optional

import requests


def http_get(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> requests.Response:
    """发起一个简单的 GET 请求并在非 2xx 时抛出异常。"""
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp


def get_json(url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
    """GET 并解析 JSON。"""
    resp = http_get(url, params=params, **kwargs)
    return resp.json()


def parse_text(resp: requests.Response, encoding: Optional[str] = None) -> str:
    """返回响应文本，必要时设置编码。"""
    if encoding:
        resp.encoding = encoding
    return resp.text
