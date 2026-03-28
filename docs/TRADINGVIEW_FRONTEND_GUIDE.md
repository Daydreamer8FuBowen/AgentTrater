# TradingView 前端开发文档

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [工程结构](#3-工程结构)
4. [开发环境搭建](#4-开发环境搭建)
5. [路由与页面](#5-路由与页面)
6. [K 线图组件](#6-k-线图组件)
7. [API 数据规范](#7-api-数据规范)
8. [状态与错误处理](#8-状态与错误处理)
9. [样式规范](#9-样式规范)
10. [扩展指南](#10-扩展指南)

---

## 1. 项目概述

`frontend/admin-console` 是 AgentTrader 管理控制台的前端工程，承载行情监控、K 线展示、回测分析、Agent 管理等功能。其中 K 线图模块基于 **TradingView lightweight-charts** 实现，通过自有后端 `/api/v1/charts/history` 接口提供数据。

---

## 2. 技术栈

| 依赖 | 版本 | 用途 |
|---|---|---|
| Vue | ^3.5 | 响应式 UI 框架 |
| Vue Router | ^4.5 | 前端路由 |
| Element Plus | ^2.11 | UI 组件库 |
| lightweight-charts | **^4.2** | TradingView K 线图渲染 |
| ECharts | ^5.6 | 辅助图表（非 K 线） |
| TypeScript | ^5.7 | 类型检查 |
| Vite | ^6.0 | 开发服务器 & 构建 |

---

## 3. 工程结构

```
frontend/admin-console/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts          # 开发代理配置
└── src/
    ├── main.ts             # 应用入口
    ├── App.vue             # 根组件
    ├── types.ts            # 全局 TS 类型
    ├── styles.css          # 全局样式
    ├── router/
    │   └── index.ts        # 路由定义
    ├── api/
    │   ├── http.ts         # 基础 fetch 封装
    │   ├── chartApi.ts     # K 线历史数据接口
    │   ├── symbolsApi.ts   # 标的列表 & 详情接口
    │   └── tableApi.ts     # 通用表格数据接口
    ├── components/
    │   ├── charts/
    │   │   ├── CandlestickChart.vue   # ECharts 蜡烛图（辅助用）
    │   │   └── LineChart.vue          # ECharts 折线图（辅助用）
    │   ├── layout/
    │   │   └── AdminLayout.vue        # 侧边栏 + 顶栏布局
    │   ├── symbols/
    │   │   └── TradingViewKlineChart.vue  # ★ 主 K 线图组件
    │   └── tables/
    ├── pages/
    │   ├── SymbolDetailPage.vue       # ★ 标的详情页（含 K 线图）
    │   ├── SymbolListPage.vue
    │   ├── DashboardPage.vue
    │   └── ...
    └── utils/
        ├── datetime.ts     # 日期格式化工具
        └── format.ts       # 数值格式化工具
```

---

## 4. 开发环境搭建

```bash
# 安装依赖
cd frontend/admin-console
npm install

# 启动开发服务器 (端口 5174)
npm run dev

# 构建生产包
npm run build
```

**后端联调代理**（`vite.config.ts`）：

```ts
server: {
  port: 5174,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',  // FastAPI 后端
      changeOrigin: true
    }
  }
}
```

开发时所有以 `/api` 开头的请求自动转发到 `http://127.0.0.1:8000`，无需跨域配置。

---

## 5. 路由与页面

| 路径 | 组件 | 说明 |
|---|---|---|
| `/dashboard` | `DashboardPage` | 系统总览 |
| `/symbols` | `SymbolListPage` | 标的监控列表 |
| `/symbols/:symbol` | `SymbolDetailPage` | 标的详情 + **K 线图** |
| `/agents` | `AgentManagementPage` | Agent 管理 |
| `/strategy-editor` | `StrategyEditorPage` | 策略编辑器 |
| `/backtest-analysis` | `BacktestAnalysisPage` | 回测分析 |
| `/system-config` | `SystemConfigPage` | 系统配置 |

K 线图在 **`/symbols/:symbol`** 页面的底部独立渲染，组件接受路由参数 `symbol` 作为 prop。

---

## 6. K 线图组件

### 6.1 组件位置

```
src/components/symbols/TradingViewKlineChart.vue
```

### 6.2 Props

```ts
defineProps<{
  symbol: string   // 标的代码，例如 "000066.SZ"
}>()
```

### 6.3 功能说明

| 功能 | 实现方式 |
|---|---|
| 支持周期切换 | `el-segmented` 切换 `1 / 5 / 15 / 60 / D` |
| 自动加载数据 | `onMounted` + `watch(symbol)` + `watch(resolution)` |
| 响应式布局 | `ResizeObserver` 监听容器尺寸，调用 `chart.resize()` |
| 手动刷新 | 点击刷新按钮重新调用 `loadData()` |
| 无数据提示 | `el-empty`，当 `response.s !== 'ok'` 时显示 |
| 移动端适配 | 媒体查询将图表高度从 460px 降为 320px |

### 6.4 图表初始化

```ts
import {
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi
} from 'lightweight-charts'

chart = createChart(root, {
  autoSize: true,
  layout: {
    background: { color: '#ffffff' },
    textColor: '#1f2937',
    fontFamily: 'Noto Sans SC, sans-serif',
  },
  grid: {
    vertLines: { color: '#eef2f7' },
    horzLines: { color: '#eef2f7' },
  },
  crosshair: { mode: 1 },  // CrosshairMode.Magnet
  rightPriceScale: { borderColor: '#dbe2ea' },
  timeScale: {
    borderColor: '#dbe2ea',
    timeVisible: true,
    secondsVisible: false,
  },
})

candleSeries = chart.addCandlestickSeries({
  upColor:     '#16a34a',   // 阳线 绿
  downColor:   '#ef4444',   // 阴线 红
  borderVisible: false,
  wickUpColor:   '#16a34a',
  wickDownColor: '#ef4444',
})
```

### 6.5 数据加载时间窗口

各周期的默认时间窗口（`from = now - N days`）：

| 周期参数 | 默认天数 |
|---|---|
| `1`（1min）| 7 天 |
| `5`（5min）| 20 天 |
| `15`（15min）| 45 天 |
| `60`（1h）| 120 天 |
| `D`（日线）| 365 天 |

所有请求固定带 `countback=1500`，后端最多返回该数量的 bar。

### 6.6 数据写入图表

```ts
const data: CandlestickData[] = response.t.map((timestamp, index) => ({
  time: timestamp,           // UNIX 秒级时间戳，必须严格升序
  open:  response.o[index],
  high:  response.h[index],
  low:   response.l[index],
  close: response.c[index],
}))
candleSeries.setData(data)
chart.timeScale().fitContent()
```

> **重要约束**：`lightweight-charts` 要求 `time` 数组严格递增（不允许相等），否则会抛出  
> `Assertion failed: data must be asc ordered by time`

---

## 7. API 数据规范

### 7.1 K 线历史接口

#### 请求

```
GET /api/v1/charts/history
```

| 参数 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| `symbol` | `string` | ✅ | 标的代码，如 `000066.SZ`、`600000.SH` |
| `resolution` | `string` | ✅ | 周期，见下表 |
| `from` | `number` | ✅ | 开始时间，UNIX 秒级时间戳 |
| `to` | `number` | ✅ | 结束时间，UNIX 秒级时间戳，须 ≥ `from` |
| `countback` | `number` | ❌ | 最多返回的 bar 数量，默认 5000，最大建议 1500 |

#### Resolution 映射表

| `resolution` 值 | 周期 | 说明 |
|---|---|---|
| `1` | 1 分钟 | |
| `3` | 3 分钟 | |
| `5` | 5 分钟 | |
| `15` | 15 分钟 | |
| `30` | 30 分钟 | |
| `60` | 1 小时 | |
| `240` | 4 小时 | |
| `D` | 日线 | |
| `W` | 周线 | |
| `M` | 月线 | |

#### Symbol 编码规范

| 市场 | 后缀 | 示例 |
|---|---|---|
| 上交所（SSE）| `.SH` | `600000.SH` |
| 深交所（SZSE）| `.SZ` | `000001.SZ` |

symbol 在传入前会统一转大写（`symbol.strip().upper()`）。

#### 响应（成功）

```jsonc
{
  "s": "ok",
  "t": [1742979426, 1743065826, ...],   // UNIX 秒级时间戳，严格升序
  "o": [12.50, 12.60, ...],              // 开盘价
  "h": [12.80, 12.90, ...],              // 最高价
  "l": [12.30, 12.40, ...],              // 最低价
  "c": [12.70, 12.85, ...],              // 收盘价
  "v": [1234567.0, 2345678.0, ...]       // 成交量
}
```

#### 响应（无数据）

```json
{ "s": "no_data" }
```

#### 响应（参数错误）

```json
{ "detail": "invalid time range" }
```

HTTP 状态码 `400`。

### 7.2 API 调用封装

```ts
// src/api/chartApi.ts

export type ChartResolution = '1' | '3' | '5' | '15' | '30' | '60' | '240' | 'D' | 'W' | 'M'

export interface TradingViewHistoryResponse {
  s: 'ok' | 'no_data' | 'error'
  t?: number[]
  o?: number[]
  h?: number[]
  l?: number[]
  c?: number[]
  v?: number[]
  errmsg?: string
}

export async function fetchChartHistory(params: {
  symbol: string
  resolution: ChartResolution
  from: number
  to: number
  countback?: number
}): Promise<TradingViewHistoryResponse>
```

### 7.3 后端行为说明

| 场景 | 行为 |
|---|---|
| InfluxDB 有完整数据 | 直接返回，不调用外部数据源 |
| InfluxDB 数据缺失/不完整 | 自动通过 DataAccessGateway 向 BaoStock/TuShare 补数，写入 InfluxDB 后返回 |
| 单次 gateway 请求超过 1000 bars | 自动分段拉取（按 `MAX_KLINE_BARS=1000` 切割），全部写入后一并返回 |
| 相同时间戳存在多行（不同数据源写入） | 仓储层和服务层双重去重，保留 close > 0 的真实数据 |

### 7.4 基础 HTTP 封装

```ts
// src/api/http.ts
export async function httpRequest<T>(url: string, init?: RequestInit): Promise<T>
```

- 非 2xx 响应时抛出携带 `status` 字段的 `ApiError`
- 所有 API 函数均为 async，调用方用 `try/catch` 处理错误后展示 `ElMessage.error`

---

## 8. 状态与错误处理

### 8.1 加载状态

使用 `v-loading="loading"` 指令包裹图表容器：

```vue
<div v-loading="loading" class="chart-root" ref="chartRootRef" />
```

### 8.2 无数据状态

```vue
<el-empty v-if="!loading && !hasData" description="该时间区间暂无 K 线数据" :image-size="72" />
```

```ts
if (response.s !== 'ok' || !response.t) {
  candleSeries.setData([])
  hasData.value = false
  return
}
```

### 8.3 错误提示

```ts
catch (error) {
  ElMessage.error(`加载 K 线失败: ${String(error)}`)
}
```

---

## 9. 样式规范

### 9.1 图表容器

```css
.chart-root {
  width: 100%;
  height: 460px;   /* 桌面端固定高度 */
}

@media (max-width: 768px) {
  .chart-root {
    height: 320px;
  }
}
```

`autoSize: true` 使 lightweight-charts 随容器宽度自动适配；`ResizeObserver` 在容器尺寸变化时手动调用 `chart.resize()` 同步高度。

### 9.2 配色

| 用途 | 色值 |
|---|---|
| 阳线 / 上涨 | `#16a34a`（绿） |
| 阴线 / 下跌 | `#ef4444`（红） |
| 图表背景 | `#ffffff` |
| 文字 | `#1f2937` |
| 网格线 | `#eef2f7` |
| 坐标轴边框 | `#dbe2ea` |

### 9.3 字体

```ts
fontFamily: 'Noto Sans SC, sans-serif'
```

---

## 10. 扩展指南

### 10.1 新增周期

在 `TradingViewKlineChart.vue` 中：

```ts
// 1. 扩展 resolutions 数组
const resolutions: ChartResolution[] = ['1', '5', '15', '60', 'D', 'W']

// 2. 在 buildRange 里补充对应默认天数
const days = resolution === 'W' ? 730 : ...
```

在 `chartApi.ts` 的类型声明里同步添加新值：

```ts
export type ChartResolution = '1' | '5' | '15' | '60' | 'D' | 'W'
```

### 10.2 新增指标叠加

使用 `chart.addLineSeries()` 在蜡烛图上叠加均线：

```ts
const maSeries = chart.addLineSeries({
  color: '#f59e0b',
  lineWidth: 1,
})
maSeries.setData(maData)  // { time: number, value: number }[]
```

### 10.3 新增图表页面

1. 在 `src/pages/` 创建新页面组件。
2. 在 `src/router/index.ts` 中注册路由。
3. 在 `src/api/` 中对应添加 API 函数。
4. 在 `AdminLayout` 的侧边栏菜单中添加导航项。

### 10.4 与 TradingView UDF 协议的关系

当前后端 `/api/v1/charts/history` 遵循 TradingView UDF（Universal Data Feed）协议的 **History** 端点规范。未来若需接入完整 TradingView Charting Library（商业版），只需将该端点注册为 UDF Provider 的 `history` 方法，不需要修改数据格式。

关键合规点：

- `t` 数组必须**严格升序**，相同时间戳会触发 `data must be asc ordered by time` 断言。
- `s` 字段必须是 `"ok"` | `"no_data"` | `"error"` 之一。
- 所有时间戳使用 **UNIX 秒**，不是毫秒。
