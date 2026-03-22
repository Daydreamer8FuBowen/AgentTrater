"""测试 BaoStock 配置集成"""
import pytest

from agent_trader.core.config import BaoStockConfig, get_settings
from agent_trader.ingestion.sources.baostock_source import BaoStockSource


def test_baostock_config_loads_from_settings() -> None:
    """测试 BaoStock 配置从 Settings 加载。"""
    settings = get_settings()
    baostock_config = settings.baostock

    assert isinstance(baostock_config, BaoStockConfig)
    assert baostock_config.user_id == "anonymous"
    assert baostock_config.password == "123456"
    assert baostock_config.options == 0


def test_baostock_source_can_be_created_from_settings() -> None:
    """测试 BaoStockSource 可以从配置中创建。"""
    settings = get_settings()
    source = BaoStockSource.from_settings(settings)

    assert source.user_id == settings.baostock.user_id
    assert source.password == settings.baostock.password
    assert source.options == settings.baostock.options
    assert source.name == "baostock"


def test_baostock_config_properties_are_frozen() -> None:
    """测试 BaoStock 配置对象是不可变的。"""
    settings = get_settings()
    baostock_config = settings.baostock

    with pytest.raises(Exception):
        baostock_config.user_id = "custom-user"  # type: ignore[misc]