# 真实数据源测试说明

测试文件：`tests/integration/test_real_data_source_integration.py`

该测试用于验证：

- BaoStock/TuShare 真实 API 调用。
- 统一网关在真实 provider 下的行为。
- 统一字段结构与元数据一致性。

## 运行方式

仅运行真实源集成测试：

```bash
uv run pytest tests/integration/test_real_data_source_integration.py -q
```

运行全量测试：

```bash
uv run pytest -q
```

## TuShare 说明

TuShare 测试依赖 token。若 token 未设置或失效，相关测试会自动 skip，不影响其余测试。
支持两种创建模式：
- 标准模式：仅配置 `TUSHARE_TOKEN`，内部使用 `ts.set_token(token)`。
- 第三方 URL 模式：同时配置 `TUSHARE_TOKEN` 和 `TUSHARE_API_URL`，内部使用 `ts.pro_api(token)` 并设置 `_DataApi__http_url`。

Windows PowerShell 设置示例：

```powershell
$env:TUSHARE_TOKEN="your_token"
$env:TUSHARE_API_URL="https://your-third-party-url"
```

## 结果解释

- `passed`: 调用成功且字段契约满足断言。
- `skipped`: 环境缺少可用 token，或外部条件不满足。
- `failed`: 可能是网络、数据源接口变更、字段映射回归。

## 常见排查

1. BaoStock 返回为空
   - 检查查询时间窗口是否过窄。

2. TuShare `ERROR` / 无效 token
   - 检查 token 是否有效。
   - 确认环境变量生效。

3. 字段断言失败
   - 优先检查 source 层 mapping 是否仍满足统一规范。
   - 对照 `UNIFIED_SOURCE_PAYLOAD_SPEC.md` 修正。
