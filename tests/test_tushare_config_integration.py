"""测试 TuShare 配置集成"""
import pytest

from agent_trader.core.config import Settings, TuShareConfig, get_settings
from agent_trader.ingestion.sources.tushare_source import TuShareSource


def test_tushare_config_loads_from_settings():
    """测试 TuShare 配置从 Settings 加载"""
    settings = get_settings()
    tushare_config = settings.tushare

    assert isinstance(tushare_config, TuShareConfig)
    # 验证 http_url 总是正确的
    assert tushare_config.http_url == "http://lianghua.nanyangqiankun.top"
    # Token 可能为空（如果没有在 .env 中设置），但应该是字符串类型
    assert isinstance(tushare_config.token, str)


def test_tushare_source_can_be_created_from_settings():
    """测试 TuShareSource 可以从配置中创建"""
    settings = get_settings()

    # 如果 token 存在，应该能创建实例
    if settings.tushare.token:
        source = TuShareSource.from_settings(settings)

        assert source.token == settings.tushare.token
        assert source.http_url == settings.tushare.http_url
        assert source.name == "tushare"


def test_tushare_source_requires_token():
    """测试 TuShareSource 没有 token 时会抛出异常"""
    with pytest.raises(ValueError, match="TuShare token 不能为空"):
        TuShareSource(token="")


def test_tushare_config_properties_are_frozen():
    """测试 TuShare 配置对象是不可变的"""
    settings = get_settings()
    tushare_config = settings.tushare

    with pytest.raises(Exception):  # frozen dataclass 会抛出 FrozenInstanceError
        tushare_config.token = "new_token"  # type: ignore
