from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SystemConfig(BaseModel):
    """系统级配置，聚合应用标识、运行环境和 HTTP 服务参数。"""

    model_config = ConfigDict(frozen=True)

    name: str
    env: str
    host: str
    port: int
    log_level: str
    debug: bool


class MongoConfig(BaseModel):
    """MongoDB 连接配置。"""

    model_config = ConfigDict(frozen=True)

    dsn: str
    database: str
    app_name: str


class InfluxConfig(BaseModel):
    """InfluxDB 时序库配置。"""

    model_config = ConfigDict(frozen=True)

    url: str
    token: str
    org: str
    bucket: str
    timeout_ms: int


class WorkerConfig(BaseModel):
    """后台任务与调度器配置。"""

    model_config = ConfigDict(frozen=True)

    timezone: str
    ingestion_interval_seconds: int
    candidate_refresh_seconds: int
    backtest_interval_seconds: int


class AgentRuntimeConfig(BaseModel):
    """Agent 运行时配置。"""

    model_config = ConfigDict(frozen=True)

    max_concurrency: int
    default_timeout_seconds: int
    checkpoint_enabled: bool


class TuShareConfig(BaseModel):
    """TuShare 数据源配置。"""

    model_config = ConfigDict(frozen=True)

    token: str
    http_url: str


class Settings(BaseSettings):
    """统一配置入口。

    这里保留扁平环境变量定义，方便 `.env` 和部署平台直接注入；
    对内则通过分组属性暴露 system/mongo/influx/worker/agent 等子配置。
    """

    app_name: str = Field(default="AgentTrader", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")

    mongo_dsn: str = Field(default="mongodb://localhost:27017", alias="MONGO_DSN")
    mongo_database: str = Field(default="agent_trader", alias="MONGO_DATABASE")
    mongo_app_name: str = Field(default="agent-trader", alias="MONGO_APP_NAME")

    influx_url: str = Field(default="http://localhost:8086", alias="INFLUX_URL")
    influx_token: str = Field(default="change-me", alias="INFLUX_TOKEN")
    influx_org: str = Field(default="agent-trader", alias="INFLUX_ORG")
    influx_bucket: str = Field(default="market-data", alias="INFLUX_BUCKET")
    influx_timeout_ms: int = Field(default=10_000, alias="INFLUX_TIMEOUT_MS")

    worker_timezone: str = Field(default="Asia/Shanghai", alias="WORKER_TIMEZONE")
    worker_ingestion_interval_seconds: int = Field(default=300, alias="WORKER_INGESTION_INTERVAL_SECONDS")
    worker_candidate_refresh_seconds: int = Field(
        default=900,
        alias="WORKER_CANDIDATE_REFRESH_SECONDS",
    )
    worker_backtest_interval_seconds: int = Field(
        default=3600,
        alias="WORKER_BACKTEST_INTERVAL_SECONDS",
    )

    agent_max_concurrency: int = Field(default=4, alias="AGENT_MAX_CONCURRENCY")
    agent_default_timeout_seconds: int = Field(default=120, alias="AGENT_DEFAULT_TIMEOUT_SECONDS")
    agent_checkpoint_enabled: bool = Field(default=True, alias="AGENT_CHECKPOINT_ENABLED")

    tushare_token: str = Field(default="", alias="TUSHARE_TOKEN")

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def system(self) -> SystemConfig:
        return SystemConfig(
            name=self.app_name,
            env=self.app_env,
            host=self.app_host,
            port=self.app_port,
            log_level=self.log_level,
            debug=self.app_debug,
        )

    @property
    def mongo(self) -> MongoConfig:
        return MongoConfig(
            dsn=self.mongo_dsn,
            database=self.mongo_database,
            app_name=self.mongo_app_name,
        )

    @property
    def influx(self) -> InfluxConfig:
        return InfluxConfig(
            url=self.influx_url,
            token=self.influx_token,
            org=self.influx_org,
            bucket=self.influx_bucket,
            timeout_ms=self.influx_timeout_ms,
        )

    @property
    def worker(self) -> WorkerConfig:
        return WorkerConfig(
            timezone=self.worker_timezone,
            ingestion_interval_seconds=self.worker_ingestion_interval_seconds,
            candidate_refresh_seconds=self.worker_candidate_refresh_seconds,
            backtest_interval_seconds=self.worker_backtest_interval_seconds,
        )

    @property
    def agent(self) -> AgentRuntimeConfig:
        return AgentRuntimeConfig(
            max_concurrency=self.agent_max_concurrency,
            default_timeout_seconds=self.agent_default_timeout_seconds,
            checkpoint_enabled=self.agent_checkpoint_enabled,
        )

    @property
    def tushare(self) -> TuShareConfig:
        """返回 TuShare 数据源配置，包括认证 token 和国内加速节点 URL。"""
        return TuShareConfig(
            token=self.tushare_token,
            http_url="http://lianghua.nanyangqiankun.top",
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # 进程内复用同一个 Settings 实例，避免每次依赖注入都重复解析环境变量。
    return Settings()