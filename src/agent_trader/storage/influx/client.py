from __future__ import annotations

from influxdb_client import InfluxDBClient

from agent_trader.core.config import InfluxConfig

def create_influx_client(config: InfluxConfig) -> InfluxDBClient:
    """根据统一配置创建 InfluxDB 客户端。"""

    return InfluxDBClient(
        url=config.url,
        token=config.token,
        org=config.org,
        timeout=config.timeout_ms,
    )


class InfluxConnectionManager:
    """InfluxDB 连接管理器。

    统一封装 client、本地 bucket/org 上下文，以及常用 query/write API 的获取方式。
    """

    def __init__(self, config: InfluxConfig) -> None:
        self._config = config
        self._client: InfluxDBClient | None = None

    @property
    def client(self) -> InfluxDBClient:
        if self._client is None:
            self._client = create_influx_client(self._config)
        return self._client

    @property
    def org(self) -> str:
        return self._config.org

    @property
    def bucket(self) -> str:
        return self._config.bucket

    def query_api(self):
        """返回 Influx 查询 API。"""

        return self.client.query_api()

    def write_api(self):
        """返回 Influx 写入 API。"""

        return self.client.write_api()

    def ping(self) -> bool:
        """验证 InfluxDB 服务是否可达。"""

        return bool(self.client.ping())

    def close(self) -> None:
        """关闭底层 HTTP 客户端连接。"""

        if self._client is not None:
            self._client.close()


def create_influx_connection_manager(config: InfluxConfig) -> InfluxConnectionManager:
    """创建 Influx 连接管理器的统一工厂方法。"""

    return InfluxConnectionManager(config)