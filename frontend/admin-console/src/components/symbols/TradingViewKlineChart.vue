<script setup lang="ts">
import { RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type Range,
  type Time,
} from 'lightweight-charts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fetchChartHistory, type ChartResolution } from '../../api/chartApi'
import { formatDateTime } from '../../utils/datetime'

const props = defineProps<{
  symbol: string
}>()

// ─── 常量 ──────────────────────────────────────────────────────────────────
/** 5 年上限（秒） */
const FIVE_YEARS_SECS = 5 * 365 * 24 * 60 * 60
/** 距左侧边界不足 N 根 bar 时触发历史加载 */
const EDGE_TRIGGER_BARS = 10

// ─── 响应式状态 ─────────────────────────────────────────────────────────────
const resolutions: ChartResolution[] = ['1', '5', '15', '60', 'D']
const activeResolution = ref<ChartResolution>('D')
const loading = ref(false)
const loadingMore = ref(false)
const pointCount = ref(0)
const latestTimeText = ref('--')
const hasData = ref(true)
const reachedMaxHistory = ref(false)
const chartRootRef = ref<HTMLElement | null>(null)

// ─── 图表实例（非响应式） ────────────────────────────────────────────────────
let chart: IChartApi | null = null
let candleSeries: ISeriesApi<'Candlestick'> | null = null
let resizeObserver: ResizeObserver | null = null

// ─── 数据缓存 ────────────────────────────────────────────────────────────────
/** 已加载的全部 bar（按时间升序） */
let allBars: CandlestickData[] = []
/** 已加载数据中最早的 UNIX 秒时间戳 */
let earliestLoadedTs = 0
/** 是否已无更多历史可拉 */
let noMoreHistory = false
/** 防止并发请求 */
let isFetchingMore = false

// ─── computed ───────────────────────────────────────────────────────────────
const title = computed(() => `${props.symbol} K 线 (${activeResolution.value})`)
const densityText = computed(() => `Bars: ${pointCount.value}`)

// ─── 辅助函数 ────────────────────────────────────────────────────────────────
function maxHistoryTs(): number {
  return Math.floor(Date.now() / 1000) - FIVE_YEARS_SECS
}

function initialChunkDays(resolution: ChartResolution): number {
  return resolution === '1' ? 7
    : resolution === '5' ? 20
    : resolution === '15' ? 45
    : resolution === '60' ? 120
    : 365
}

/**
 * 合并两批 bar，以 time 为 key 去重。
 * close > 0 的真实数据优先于零填充数据。
 */
function mergeBars(a: CandlestickData[], b: CandlestickData[]): CandlestickData[] {
  const map = new Map<number, CandlestickData>()
  for (const bar of [...a, ...b]) {
    const t = Number(bar.time)
    const prev = map.get(t)
    if (!prev || (Number(bar.close) > 0 && Number(prev.close) === 0)) {
      map.set(t, bar)
    }
  }
  return Array.from(map.values()).sort((x, y) => Number(x.time) - Number(y.time))
}

/**
 * 将 bars 写入 series。
 * preserveViewport=true 时保存并还原可见时间范围，防止 prepend 数据后视口跳动。
 */
function updateSeries(bars: CandlestickData[], preserveViewport = false): void {
  if (!candleSeries || !chart) return
  let savedRange: Range<Time> | null = null
  if (preserveViewport) {
    savedRange = chart.timeScale().getVisibleRange()
  }
  candleSeries.setData(bars)
  if (preserveViewport && savedRange) {
    chart.timeScale().setVisibleRange(savedRange)
  }
}

// ─── 初始加载 ────────────────────────────────────────────────────────────────
async function loadData(): Promise<void> {
  if (!props.symbol || candleSeries === null) return

  // 切换 symbol / resolution 时重置所有状态
  allBars = []
  earliestLoadedTs = 0
  noMoreHistory = false
  isFetchingMore = false
  reachedMaxHistory.value = false

  loading.value = true
  try {
    const now = Math.floor(Date.now() / 1000)
    const chunkSecs = initialChunkDays(activeResolution.value) * 24 * 60 * 60
    const from = now - chunkSecs
    const to = now

    const response = await fetchChartHistory({
      symbol: props.symbol,
      resolution: activeResolution.value,
      from,
      to,
      countback: 1500,
    })

    if (response.s !== 'ok' || !response.t?.length) {
      candleSeries.setData([])
      pointCount.value = 0
      latestTimeText.value = '--'
      hasData.value = false
      return
    }

    allBars = response.t.map((ts, i) => ({
      time: ts as Time,
      open: response.o![i] ?? 0,
      high: response.h![i] ?? 0,
      low: response.l![i] ?? 0,
      close: response.c![i] ?? 0,
    }))

    updateSeries(allBars)
    earliestLoadedTs = Number(allBars[0].time)
    pointCount.value = allBars.length
    hasData.value = true

    const lastTs = Number(allBars[allBars.length - 1].time)
    latestTimeText.value = formatDateTime(new Date(lastTs * 1000).toISOString(), '--')

    chart?.timeScale().fitContent()

    if (from <= maxHistoryTs()) {
      noMoreHistory = true
      reachedMaxHistory.value = true
    }
  } catch (error) {
    ElMessage.error(`加载 K 线失败: ${String(error)}`)
    hasData.value = false
  } finally {
    loading.value = false
  }
}

// ─── 向左滚动时动态补历史 ─────────────────────────────────────────────────────
async function loadMoreHistory(): Promise<void> {
  if (isFetchingMore || noMoreHistory || !candleSeries || !props.symbol) return

  const boundary = maxHistoryTs()
  if (earliestLoadedTs <= boundary) {
    noMoreHistory = true
    reachedMaxHistory.value = true
    return
  }

  isFetchingMore = true
  loadingMore.value = true

  const chunkSecs = initialChunkDays(activeResolution.value) * 24 * 60 * 60
  const to = earliestLoadedTs - 1
  const from = Math.max(to - chunkSecs, boundary)

  try {
    const response = await fetchChartHistory({
      symbol: props.symbol,
      resolution: activeResolution.value,
      from,
      to,
      countback: 1500,
    })

    if (response.s !== 'ok' || !response.t?.length) {
      noMoreHistory = true
      reachedMaxHistory.value = true
      return
    }

    const newBars: CandlestickData[] = response.t.map((ts, i) => ({
      time: ts as Time,
      open: response.o![i] ?? 0,
      high: response.h![i] ?? 0,
      low: response.l![i] ?? 0,
      close: response.c![i] ?? 0,
    }))

    allBars = mergeBars(newBars, allBars)
    updateSeries(allBars, true)   // 保持视口不跳动

    earliestLoadedTs = Number(allBars[0].time)
    pointCount.value = allBars.length

    if (from <= boundary) {
      noMoreHistory = true
      reachedMaxHistory.value = true
    }
  } catch (error) {
    ElMessage.error(`加载历史数据失败: ${String(error)}`)
  } finally {
    isFetchingMore = false
    loadingMore.value = false
  }
}

// ─── 可见范围变化回调 ─────────────────────────────────────────────────────────
function onVisibleLogicalRangeChange(range: LogicalRange | null): void {
  if (!range) return
  // 当用户滚动到距左侧边界不足 EDGE_TRIGGER_BARS 根 bar 时，触发历史加载
  if (range.from < EDGE_TRIGGER_BARS) {
    void loadMoreHistory()
  }
}

// ─── 图表初始化 ──────────────────────────────────────────────────────────────
function initChart(): void {
  const root = chartRootRef.value
  if (!root) return

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
    crosshair: { mode: 1 },
    rightPriceScale: { borderColor: '#dbe2ea' },
    timeScale: {
      borderColor: '#dbe2ea',
      timeVisible: true,
      secondsVisible: false,
    },
  })

  candleSeries = chart.addCandlestickSeries({
    upColor: '#16a34a',
    downColor: '#ef4444',
    borderVisible: false,
    wickUpColor: '#16a34a',
    wickDownColor: '#ef4444',
  })

  // 订阅逻辑范围变化 —— 触发左滑历史加载
  chart.timeScale().subscribeVisibleLogicalRangeChange(onVisibleLogicalRangeChange)

  resizeObserver = new ResizeObserver(() => {
    chart?.resize(root.clientWidth, root.clientHeight)
  })
  resizeObserver.observe(root)
}

function refreshNow(): void {
  void loadData()
}

onMounted(async () => {
  initChart()
  await loadData()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  chart?.remove()
  chart = null
  candleSeries = null
  allBars = []
})

watch(() => props.symbol, async () => { await loadData() })
watch(activeResolution, async () => { await loadData() })
</script>

<template>
  <el-card class="tv-chart-card" shadow="never">
    <template #header>
      <div class="tv-chart-header">
        <div>
          <h3>{{ title }}</h3>
          <p>TradingView lightweight-charts</p>
        </div>
        <div class="chart-controls">
          <el-segmented v-model="activeResolution" :options="resolutions" />
          <el-button text :icon="RefreshRight" @click="refreshNow">刷新</el-button>
        </div>
      </div>
    </template>

    <div class="chart-meta">
      <el-tag size="small" effect="plain">{{ densityText }}</el-tag>
      <el-tag size="small" type="info" effect="plain">最新: {{ latestTimeText }}</el-tag>
      <el-tag v-if="loadingMore" size="small" type="warning" effect="plain">
        <el-icon class="is-loading" style="margin-right:4px"><RefreshRight /></el-icon>加载历史数据…
      </el-tag>
      <el-tag v-if="reachedMaxHistory" size="small" type="danger" effect="plain">已到5年最远历史</el-tag>
    </div>

    <div class="chart-wrapper">
      <div v-loading="loading" class="chart-root" ref="chartRootRef" />
      <transition name="fade">
        <div v-if="loadingMore" class="history-loading-overlay">
          <el-icon class="is-loading"><RefreshRight /></el-icon>
          <span>加载更早数据…</span>
        </div>
      </transition>
    </div>
    <el-empty v-if="!loading && !hasData" description="该时间区间暂无 K 线数据" :image-size="72" />
  </el-card>
</template>

<style scoped>
.tv-chart-card {
  border: 1px solid #e6ecf3;
  border-radius: 16px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}

.tv-chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.tv-chart-header h3 {
  margin: 0;
  font-size: 18px;
}

.tv-chart-header p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.chart-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

  .chart-root {
    width: 100%;
    height: 460px;
  }

  .chart-wrapper {
    position: relative;
  }

  .history-loading-overlay {
    position: absolute;
    bottom: 12px;
    left: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid #e0a830;
    border-radius: 6px;
    color: #b45309;
    font-size: 12px;
    pointer-events: none;
    z-index: 10;
    backdrop-filter: blur(4px);
  }

  .fade-enter-active,
  .fade-leave-active {
    transition: opacity 0.25s ease;
  }

  .fade-enter-from,
  .fade-leave-to {
    opacity: 0;
  }

@media (max-width: 768px) {
  .chart-root {
    height: 320px;
  }

  .tv-chart-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .chart-controls {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
