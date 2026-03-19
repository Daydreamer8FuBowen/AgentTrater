# TuShare Token 配置和使用指南

## 配置概览

TuShareSource 在初始化时会自动配置以下关键参数：

```python
self.pro._DataApi__token = token
self.pro._DataApi__http_url = "http://lianghua.nanyangqiankun.top"
```

这些配置确保：
1. ✅ Token 被正确认证
2. ✅ 使用国内加速节点获取数据
3. ✅ 避免 API 连接问题

## 使用方式

### 方式 1: 直接在代码中使用 Token

```python
from agent_trader.ingestion.sources import TuShareSource

token = "6588e45307d18e78fc1725898b2ec1dfdad28cb085145d1c47e9f4ee6d12"
source = TuShareSource(token=token)

# 获取数据
events = await source.fetch_klines("000001.SZ", "20240101", "20240131")
```

### 方式 2: 通过环境变量

```bash
# 在 shell 设置环境变量
export TUSHARE_TOKEN="6588e45307d18e78fc1725898b2ec1dfdad28cb085145d1c47e9f4ee6d12"

# Python 代码
import os
token = os.getenv("TUSHARE_TOKEN")
source = TuShareSource(token=token)
```

### 方式 3: 从文件读取

创建 `.env.example` 或 `config.toml`:

```ini
TUSHARE_TOKEN=6588e45307d18e78fc1725898b2ec1dfdad28cb085145d1c47e9f4ee6d12
```

## 运行快速测试

### 方式 A: 运行单元测试（推荐）

单元测试无需真实 Token，使用 mock 数据：

```bash
uv run pytest tests/test_tushare_ingestion.py -v
```

**结果:**
- ✅ 18 passed（包括配置验证）

### 方式 B: 运行实时集成测试

使用真实 Token 连接到 TuShare API：

```bash
TUSHARE_TOKEN="6588e45307d18e78fc1725898b2ec1dfdad28cb085145d1c47e9f4ee6d12" \
TUSHARE_INTEGRATION_TEST=1 \
uv run pytest tests/test_tushare_integration_live.py -v
```

这将测试：
- K 线数据获取
- 股票基本信息获取
- 每日基础面数据获取
- 完整的数据流处理

### 方式 C: 运行快速测试脚本

```bash
python examples/tushare_quick_test.py
```

此脚本将：
1. 初始化数据源
2. 获取实际数据
3. 规范化处理
4. 展示完整的数据流

## 常见问题

### Q: Token 有过期时间吗？
A: TuShare Token 通常不过期（取决于账户状态）。但如果账户被禁用或配额用尽会无法使用。

### Q: 如何验证 Token 是否有效？
A: 运行以下代码测试连接：

```python
from agent_trader.ingestion.sources import TuShareSource

source = TuShareSource(token="your_token")
# 如果初始化成功，Token 通常是有效的
```

### Q: API 调用有限制吗？
A: 是的，TuShare 有调用频率限制：

- **免费版本**: 可能有每分钟请求数限制
- **付费版本**: 高级计划有更高的限额

建议：
- 添加请求延迟
- 实现本地缓存
- 考虑升级到付费计划

### Q: 无法连接到 API 怎么办？

检查清单：
1. ✓ Token 是否正确
2. ✓ HTTP URL 是否可访问：`http://lianghua.nanyangqiankun.top`
3. ✓ 网络连接是否正常
4. ✓ 防火墙是否允许出站连接

## 数据源 URL

TuShareSource 使用以下 URL：

```
http://lianghua.nanyangqiankun.top
```

这是 TuShare 的国内加速节点。如果需要使用其他节点，可以修改源代码中的 URL。

## 支持的数据类型

| 方法 | 用途 | 参数 | 返回值 |
|-----|------|------|--------|
| `fetch_klines()` | K 线数据 | symbol, start_date, end_date, freq | RawEvent 列表 |
| `fetch_basic_info()` | 股票基本信息 | 无 | RawEvent 列表 |
| `fetch_daily_basic()` | 每日基础面 | trade_date (可选) | RawEvent 列表 |
| `fetch()` | 默认并发获取 | 无 | RawEvent 列表 |

## 集成到系统

完整的数据流集成：

```python
from agent_trader.ingestion.sources import TuShareSource
from agent_trader.ingestion.normalizers import TuShareNormalizer
from agent_trader.application.services.trigger_service import TriggerService

# 1. 获取数据
source = TuShareSource(token="your_token")
events = await source.fetch_klines("000001.SZ", "20240101", "20240131")

# 2. 规范化
normalizer = TuShareNormalizer()
normalized_events = []
for raw_event in events:
    normalized = await normalizer.normalize(raw_event)
    if normalized:
        normalized_events.append(normalized)

# 3. 转换为研究触发
triggers = []
for normalized in normalized_events:
    trigger = await normalizer.to_trigger(normalized)
    triggers.append(trigger)

# 4. 提交到系统
trigger_service = TriggerService(unit_of_work=...)
for trigger in triggers:
    await trigger_service.submit_trigger(trigger)
```

## 安全建议

1. **不要在代码中硬编码 Token**:
   ```python
   # ❌ 不好
   token = "6588e45307d18e78fc1725898b2ec1dfdad28cb085145d1c47e9f4ee6d12"
   ```

2. **使用环境变量或配置文件**:
   ```python
   # ✅ 好
   token = os.getenv("TUSHARE_TOKEN")
   ```

3. **不要提交包含 Token 的文件到 Git**:
   ```bash
   # 添加到 .gitignore
   echo ".env" >> .gitignore
   echo "config.local.toml" >> .gitignore
   ```

4. **定期检查账户安全**:
   - 访问 TuShare 官网检查账户状态
   - 定期更换密码
   - 建议使用专用的数据获取账户

## 故障排除

### 问题: "API 连接超时"

**解决方案**:
- 检查网络连接
- 验证 HTTP URL 是否可访问
- 在代码中添加重试机制

### 问题: "Token 无效"

**解决方案**:
- 再次验证 Token 字符串
- 检查账户是否被锁定或禁用
- 尝试重新生成 Token（访问 TuShare 官网）

### 问题: "请求过于频繁"

**解决方案**:
- 减少请求频率
- 添加请求延迟
- 考虑实现请求队列和缓存

## 相关文档

- [TuShare 官网](https://tushare.pro)
- [Ingestion 系统架构](../README.md#ingestion-layer)
- [源适配器协议](../src/agent_trader/ingestion/sources/base.py)
- [规范化器协议](../src/agent_trader/ingestion/normalizers/base.py)
