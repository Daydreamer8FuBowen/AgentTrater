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


class DataRoutingConfig(BaseModel):
    """统一数据源路由配置。"""

    model_config = ConfigDict(frozen=True)

    enabled: bool
    health_check_interval_seconds: int
    rebalance_interval_seconds: int
    failure_threshold: int
    circuit_open_seconds: int
    promotion_step: int
    promote_on_success: bool


class AgentRuntimeConfig(BaseModel):
    """Agent 运行时配置。"""

    model_config = ConfigDict(frozen=True)

    max_concurrency: int
    default_timeout_seconds: int
    checkpoint_enabled: bool


class OpenAIConfig(BaseModel):
    """OpenAI 模型接入配置。"""

    model_config = ConfigDict(frozen=True)

    api_key: str
    base_url: str | None
    timeout_seconds: int
    temperature: float


class AgentModelConfig(BaseModel):
    """Agent 名称到模型名称的映射配置。"""

    model_config = ConfigDict(frozen=True)

    default_model: str
    model_map: dict[str, str]


class TuShareConfig(BaseModel):
    """TuShare 数据源配置。"""

    model_config = ConfigDict(frozen=True)

    token: str
    http_url: str


class BaoStockConfig(BaseModel):
    """BaoStock 数据源配置（用于构建 `BaoStockSource`）。"""

    model_config = ConfigDict(frozen=True)

    user_id: str
    password: str
    options: int


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

    data_routing_enabled: bool = Field(default=True, alias="DATA_ROUTING_ENABLED")
    data_routing_health_check_interval_seconds: int = Field(
        default=60,
        alias="DATA_ROUTING_HEALTH_CHECK_INTERVAL_SECONDS",
    )
    data_routing_rebalance_interval_seconds: int = Field(
        default=300,
        alias="DATA_ROUTING_REBALANCE_INTERVAL_SECONDS",
    )
    data_routing_failure_threshold: int = Field(default=3, alias="DATA_ROUTING_FAILURE_THRESHOLD")
    data_routing_circuit_open_seconds: int = Field(default=120, alias="DATA_ROUTING_CIRCUIT_OPEN_SECONDS")
    data_routing_promotion_step: int = Field(default=1, alias="DATA_ROUTING_PROMOTION_STEP")
    data_routing_promote_on_success: bool = Field(default=True, alias="DATA_ROUTING_PROMOTE_ON_SUCCESS")

    agent_max_concurrency: int = Field(default=4, alias="AGENT_MAX_CONCURRENCY")
    agent_default_timeout_seconds: int = Field(default=120, alias="AGENT_DEFAULT_TIMEOUT_SECONDS")
    agent_checkpoint_enabled: bool = Field(default=True, alias="AGENT_CHECKPOINT_ENABLED")
    agent_default_model: str = Field(default="gpt-4.1-mini", alias="AGENT_DEFAULT_MODEL")
    agent_model_map: dict[str, str] = Field(
        default_factory=lambda: {"news_preprocess": "gpt-4.1-mini"},
        alias="AGENT_MODEL_MAP",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_timeout_seconds: int = Field(default=60, alias="OPENAI_TIMEOUT_SECONDS")
    openai_temperature: float = Field(default=0.1, alias="OPENAI_TEMPERATURE")

    tushare_token: str = Field(default="", alias="TUSHARE_TOKEN")
    baostock_user_id: str = Field(default="anonymous", alias="BAOSTOCK_USER_ID")
    baostock_password: str = Field(default="123456", alias="BAOSTOCK_PASSWORD")
    baostock_options: int = Field(default=0, alias="BAOSTOCK_OPTIONS")

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
    def data_routing(self) -> DataRoutingConfig:
        return DataRoutingConfig(
            enabled=self.data_routing_enabled,
            health_check_interval_seconds=self.data_routing_health_check_interval_seconds,
            rebalance_interval_seconds=self.data_routing_rebalance_interval_seconds,
            failure_threshold=self.data_routing_failure_threshold,
            circuit_open_seconds=self.data_routing_circuit_open_seconds,
            promotion_step=self.data_routing_promotion_step,
            promote_on_success=self.data_routing_promote_on_success,
        )

    @property
    def agent(self) -> AgentRuntimeConfig:
        return AgentRuntimeConfig(
            max_concurrency=self.agent_max_concurrency,
            default_timeout_seconds=self.agent_default_timeout_seconds,
            checkpoint_enabled=self.agent_checkpoint_enabled,
        )

    @property
    def agent_models(self) -> AgentModelConfig:
        return AgentModelConfig(
            default_model=self.agent_default_model,
            model_map=self.agent_model_map,
        )

    @property
    def openai(self) -> OpenAIConfig:
        return OpenAIConfig(
            api_key=self.openai_api_key,
            base_url=self.openai_base_url,
            timeout_seconds=self.openai_timeout_seconds,
            temperature=self.openai_temperature,
        )

    @property
    def tushare(self) -> TuShareConfig:
        """返回 TuShare 数据源配置，包括认证 token 和国内加速节点 URL。"""
        return TuShareConfig(
            token=self.tushare_token,
            http_url="http://lianghua.nanyangqiankun.top",
        )

    @property
    def baostock(self) -> BaoStockConfig:
        """返回 BaoStock 配置，用于 `BaoStockSource.from_settings`。"""
        return BaoStockConfig(
            user_id=self.baostock_user_id,
            password=self.baostock_password,
            options=self.baostock_options,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # 进程内复用同一个 Settings 实例，避免每次依赖注入都重复解析环境变量。
    return Settings()