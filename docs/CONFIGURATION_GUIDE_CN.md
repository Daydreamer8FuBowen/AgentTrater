# AgentTrader 配置完全指南

> 为从 Java 转向 Python 开发者编写的配置系统说明

## 概览

AgentTrader 使用 **Pydantic Settings** 进行配置管理，就像 Java 的 Spring Boot `@ConfigurationProperties` 或环境变量注入。

所有配置都集中在一个地方，通过环境变量驱动，避免硬编码。

---

## 1. 配置层级

```
┌─────────────────────────────────────────────────────┐
│ 环境变量 (.env 文件)                                │
│ MYSQL_HOST=localhost                                │
│ TUSHARE_TOKEN=6588e45307d18e...                     │
│ WORKER_INGESTION_INTERVAL_SECONDS=300               │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│ Pydantic Settings (config.py)                       │
│ - MySQLConfig                                       │
│ - TuShareConfig                                     │
│ - WorkerConfig                                      │
│ - Settings (主配置类)                               │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│ 应用代码 (API / Worker / Services)                 │
│ settings = get_settings()                           │
│ mysql_config = settings.mysql                       │
│ worker_config = settings.worker                     │
└─────────────────────────────────────────────────────┘
```

---

## 2. 环境变量设置

### .env 文件

位置：项目根目录 `.env`

```bash
# =====================================================
# 日志配置
# =====================================================
LOG_LEVEL=INFO

# =====================================================
# 系统配置
# =====================================================
SYSTEM_NAME=AgentTrader
SYSTEM_VERSION=0.1.0
SYSTEM_ENV=development

# =====================================================
# MySQL 数据库配置
# =====================================================
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=agent_trader
MYSQL_POOL_SIZE=5
MYSQL_ECHO=false

# =====================================================
# MongoDB 配置
# =====================================================
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE=agent_trader_db

# =====================================================
# InfluxDB 时序数据库配置
# =====================================================
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=your_influx_token
INFLUX_ORG=agent_trader
INFLUX_BUCKET=stock_data

# =====================================================
# TuShare 金融数据源配置
# =====================================================
TUSHARE_TOKEN=6588e45307d18e78fc1725898b2ec1dfdad28cb085145d1c47e9f4ee6d12

# =====================================================
# Worker 定时任务配置
# =====================================================
# 摄入 K 线数据的间隔（秒）
WORKER_INGESTION_INTERVAL_SECONDS=300

# 刷新候选池的间隔（秒）
WORKER_CANDIDATE_REFRESH_SECONDS=900

# 运行回测的间隔（秒）
WORKER_BACKTEST_INTERVAL_SECONDS=3600

# 时区设置
WORKER_TIMEZONE=UTC

# =====================================================
# Agent 配置
# =====================================================
AGENT_MODEL=gpt-4
AGENT_TEMPERATURE=0.7
AGENT_MAX_TOKENS=2048

# =====================================================
# 运行时配置
# =====================================================
AGENT_RUNTIME_MAX_RETRIES=3
AGENT_RUNTIME_TIMEOUT_SECONDS=300
```

### 对应的 config.py

请参考：[src/agent_trader/core/config.py](../src/agent_trader/core/config.py)

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# ════════════════════════════════════════════════════
# 1. 数据库配置
# ════════════════════════════════════════════════════

class MySQLConfig(BaseModel):
    """MySQL 配置"""
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str
    database: str = "agent_trader"
    pool_size: int = 5
    echo: bool = False


class MongoConfig(BaseModel):
    """MongoDB 配置"""
    uri: str = "mongodb://localhost:27017"
    database: str = "agent_trader_db"


class InfluxConfig(BaseModel):
    """InfluxDB 配置"""
    url: str = "http://localhost:8086"
    token: str
    org: str = "agent_trader"
    bucket: str = "stock_data"


# ════════════════════════════════════════════════════
# 2. 外部服务配置
# ════════════════════════════════════════════════════

class TuShareConfig(BaseModel):
    """TuShare 数据源配置"""
    token: str
    http_url: str = "http://lianghua.nanyangqiankun.top"


# ════════════════════════════════════════════════════
# 3. Worker 定时任务配置
# ════════════════════════════════════════════════════

class WorkerConfig(BaseModel):
    """定时任务调度器配置"""
    ingestion_interval_seconds: int = 300      # 5分钟
    candidate_refresh_seconds: int = 900       # 15分钟
    backtest_interval_seconds: int = 3600      # 1小时
    timezone: str = "UTC"


# ════════════════════════════════════════════════════
# 4. Agent 配置
# ════════════════════════════════════════════════════

class AgentConfig(BaseModel):
    """智能体配置"""
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2048


class AgentRuntimeConfig(BaseModel):
    """Agent 运行时配置"""
    max_retries: int = 3
    timeout_seconds: int = 300


# ════════════════════════════════════════════════════
# 5. 系统级别配置
# ════════════════════════════════════════════════════

class SystemConfig(BaseModel):
    """系统配置"""
    name: str = "AgentTrader"
    version: str = "0.1.0"
    env: str = "development"


# ════════════════════════════════════════════════════
# 6. 主配置类（Pydantic Settings）
# ════════════════════════════════════════════════════

class Settings(BaseSettings):
    """应用配置（从环境变量加载）"""
    
    # 元数据
    log_level: str = "INFO"
    
    # MySQL 配置
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str
    mysql_database: str = "agent_trader"
    mysql_pool_size: int = 5
    mysql_echo: bool = False
    
    # MongoDB 配置
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "agent_trader_db"
    
    # InfluxDB 配置
    influx_url: str = "http://localhost:8086"
    influx_token: str
    influx_org: str = "agent_trader"
    influx_bucket: str = "stock_data"
    
    # TuShare 配置
    tushare_token: str = Field(alias="TUSHARE_TOKEN")
    
    # Worker 配置
    worker_ingestion_interval_seconds: int = 300
    worker_candidate_refresh_seconds: int = 900
    worker_backtest_interval_seconds: int = 3600
    worker_timezone: str = "UTC"
    
    # Agent 配置
    agent_model: str = "gpt-4"
    agent_temperature: float = 0.7
    agent_max_tokens: int = 2048
    
    # Runtime 配置
    agent_runtime_max_retries: int = 3
    agent_runtime_timeout_seconds: int = 300
    
    # 系统配置
    system_name: str = "AgentTrader"
    system_version: str = "0.1.0"
    system_env: str = "development"
    
    # ═══════════════════════════════════════════════════
    # 属性：分组访问配置
    # ═══════════════════════════════════════════════════
    
    @property
    def mysql(self) -> MySQLConfig:
        """获取 MySQL 配置组"""
        return MySQLConfig(
            host=self.mysql_host,
            port=self.mysql_port,
            user=self.mysql_user,
            password=self.mysql_password,
            database=self.mysql_database,
            pool_size=self.mysql_pool_size,
            echo=self.mysql_echo,
        )
    
    @property
    def mongo(self) -> MongoConfig:
        """获取 MongoDB 配置组"""
        return MongoConfig(
            uri=self.mongo_uri,
            database=self.mongo_database,
        )
    
    @property
    def influx(self) -> InfluxConfig:
        """获取 InfluxDB 配置组"""
        return InfluxConfig(
            url=self.influx_url,
            token=self.influx_token,
            org=self.influx_org,
            bucket=self.influx_bucket,
        )
    
    @property
    def tushare(self) -> TuShareConfig:
        """获取 TuShare 配置组"""
        return TuShareConfig(token=self.tushare_token)
    
    @property
    def worker(self) -> WorkerConfig:
        """获取 Worker 配置组"""
        return WorkerConfig(
            ingestion_interval_seconds=self.worker_ingestion_interval_seconds,
            candidate_refresh_seconds=self.worker_candidate_refresh_seconds,
            backtest_interval_seconds=self.worker_backtest_interval_seconds,
            timezone=self.worker_timezone,
        )
    
    @property
    def agent(self) -> AgentConfig:
        """获取 Agent 配置组"""
        return AgentConfig(
            model=self.agent_model,
            temperature=self.agent_temperature,
            max_tokens=self.agent_max_tokens,
        )
    
    @property
    def runtime(self) -> AgentRuntimeConfig:
        """获取运行时配置组"""
        return AgentRuntimeConfig(
            max_retries=self.agent_runtime_max_retries,
            timeout_seconds=self.agent_runtime_timeout_seconds,
        )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# ════════════════════════════════════════════════════
# 7. 全局单例（LRU 缓存）
# ════════════════════════════════════════════════════

from functools import lru_cache

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    获取应用配置（单例）
    
    使用 @lru_cache 确保配置在整个应用生命周期中只加载一次
    """
    return Settings()
```

---

## 3. 配置使用示例

### 示例 1：在 API 中使用配置

```python
# src/agent_trader/api/main.py
from agent_trader.core.config import get_settings

def get_app_info():
    """获取应用信息"""
    settings = get_settings()
    
    return {
        "name": settings.system_name,
        "version": settings.system_version,
        "environment": settings.system_env,
    }
```

### 示例 2：在数据库连接中使用

```python
# src/agent_trader/storage/mysql/client.py
from agent_trader.core.config import get_settings
from sqlalchemy.ext.asyncio import create_async_engine

def create_db_engine():
    """创建异步数据库引擎"""
    settings = get_settings()
    mysql_config = settings.mysql  # 获取 MySQL 配置组
    
    dsn = (
        f"mysql+aiomysql://"
        f"{mysql_config.user}:{mysql_config.password}@"
        f"{mysql_config.host}:{mysql_config.port}/"
        f"{mysql_config.database}"
    )
    
    return create_async_engine(
        dsn,
        pool_size=mysql_config.pool_size,
        echo=mysql_config.echo,
    )
```

### 示例 3：在定时任务中使用

```python
# src/agent_trader/worker/scheduler.py
from agent_trader.core.config import get_settings
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def setup_scheduler() -> AsyncIOScheduler:
    """设置定时任务调度器"""
    settings = get_settings()
    worker_config = settings.worker  # 获取 Worker 配置组
    
    scheduler = AsyncIOScheduler(timezone=worker_config.timezone)
    
    # 使用配置的间隔
    scheduler.add_job(
        ingest_kline_data,
        trigger="interval",
        seconds=worker_config.ingestion_interval_seconds,  # 从配置读取
        id="ingest_kline_data",
    )
    
    return scheduler
```

### 示例 4：在数据源中使用

```python
# src/agent_trader/ingestion/sources/tushare_source.py
from agent_trader.core.config import get_settings

class TuShareSource:
    @classmethod
    def from_settings(cls, settings=None):
        """从配置创建数据源实例"""
        if settings is None:
            settings = get_settings()
        
        tushare_config = settings.tushare  # 获取 TuShare 配置组
        
        return cls(
            token=tushare_config.token,
            http_url=tushare_config.http_url,
        )
```

---

## 4. 与 Java 配置的对比

### Java Spring Boot 方式

```java
// application.properties
spring.datasource.url=jdbc:mysql://localhost:3306/agent_trader
spring.datasource.username=root
spring.datasource.password=password

// 配置类
@Configuration
@ConfigurationProperties(prefix = "spring")
public class DatabaseProperties {
    private Datasource datasource;
    // ...
}

// 使用
@Service
public class UserService {
    @Autowired
    private DatabaseProperties dbProps;
}
```

### Python Pydantic 方式

```python
# .env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password

# 配置类
class MySQLConfig(BaseModel):
    host: str
    port: int
    user: str
    password: str

class Settings(BaseSettings):
    mysql_host: str
    # ...
    
    @property
    def mysql(self) -> MySQLConfig:
        return MySQLConfig(host=self.mysql_host, ...)

# 使用
settings = get_settings()
mysql_config = settings.mysql
```

**主要差异**：
- ✅ Python 更灵活：可以在运行时动态访问配置
- ✅ Pydantic 提供更强的类型验证
- ❌ Python 需要手动处理单例（Java 框架自动管理）

---

## 5. 环境特定配置

### 开发环境 (.env.development)

```bash
LOG_LEVEL=DEBUG
SYSTEM_ENV=development
MYSQL_ECHO=true
WORKER_INGESTION_INTERVAL_SECONDS=60  # 1分钟，快速测试
```

### 生产环境 (.env.production)

```bash
LOG_LEVEL=INFO
SYSTEM_ENV=production
MYSQL_ECHO=false
WORKER_INGESTION_INTERVAL_SECONDS=300  # 5分钟
```

### 加载指定环境配置

```python
import os
from dotenv import load_dotenv

# 根据运行模式加载不同的 .env 文件
env = os.getenv("AGENT_ENV", "development")
load_dotenv(f".env.{env}")
```

---

## 6. 配置验证

Pydantic 自动验证配置值：

```python
import pytest
from agent_trader.core.config import Settings

def test_settings_validation():
    """测试配置验证"""
    with pytest.raises(ValueError):
        # token 不能为空
        Settings(
            tushare_token="",  # ❌ 会报错
            influx_token="valid",
        )
```

---

## 总结

**配置最佳实践**：

1. ✅ 所有配置都来自环境变量（.env 文件）
2. ✅ 使用 Pydantic 进行类型验证和转换
3. ✅ 用 `@property` 分组相关配置
4. ✅ 用 `@lru_cache` 实现单例模式
5. ✅ 文档中明确说明各配置项的含义
6. ✅ 不同环境使用不同的 .env 文件
7. ✅ 为配置编写单元测试

这样就能像 Java/Spring Boot 一样管理配置，同时充分利用 Python 的灵活性。
