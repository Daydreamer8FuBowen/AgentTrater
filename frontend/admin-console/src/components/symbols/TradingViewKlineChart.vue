<script setup lang="ts">
import { RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { createChart, type CandlestickData, type IChartApi, type ISeriesApi } from 'lightweight-charts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fetchChartHistory, type ChartResolution } from '../../api/chartApi'

const props = defineProps<{
  symbol: string
}>()

const resolutions: ChartResolution[] = ['1', '5', '15', '60', 'D']
const activeResolution = ref<ChartResolution>('D')
const loading = ref(false)
const pointCount = ref(0)
const latestTimeText = ref('--')
const hasData = ref(true)
const chartRootRef = ref<HTMLElement | null>(null)
let chart: IChartApi | null = null
let candleSeries: ISeriesApi<'Candlestick'> | null = null
let resizeObserver: ResizeObserver | null = null

const title = computed(() => `${props.symbol} K 线 (${activeResolution.value})`)
const densityText = computed(() => `Bars: ${pointCount.value}`)

function buildRange(resolution: ChartResolution): { from: number; to: number } {
  const now = Math.floor(Date.now() / 1000)
  const days = resolution === '1' ? 7 : resolution === '5' ? 20 : resolution === '15' ? 45 : resolution === '60' ? 120 : 365
  return { from: now - days * 24 * 60 * 60, to: now }
}

async function loadData() {
  if (!props.symbol || candleSeries === null) {
    return
  }
  loading.value = true
  try {
    const { from, to } = buildRange(activeResolution.value)
    const response = await fetchChartHistory({
      symbol: props.symbol,
      resolution: activeResolution.value,
      from,
      to,
      countback: 1500,
    })
    if (response.s !== 'ok' || !response.t || !response.o || !response.h || !response.l || !response.c) {
      candleSeries.setData([])
      pointCount.value = 0
      latestTimeText.value = '--'
      hasData.value = false
      return
    }
    const data: CandlestickData[] = response.t.map((timestamp, index) => ({
      time: timestamp,
      open: response.o?.[index] ?? 0,
      high: response.h?.[index] ?? 0,
      low: response.l?.[index] ?? 0,
      close: response.c?.[index] ?? 0,
    }))
    candleSeries.setData(data)
    pointCount.value = data.length
    hasData.value = data.length > 0
    if (data.length > 0) {
      const ts = Number(data[data.length - 1].time)
      latestTimeText.value = Number.isNaN(ts) ? '--' : new Date(ts * 1000).toLocaleString()
    } else {
      latestTimeText.value = '--'
    }
    chart?.timeScale().fitContent()
  } catch (error) {
    ElMessage.error(`加载 K 线失败: ${String(error)}`)
  } finally {
    loading.value = false
  }
}

function initChart() {
  const root = chartRootRef.value
  if (!root) {
    return
  }
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
    crosshair: {
      mode: 1,
    },
    rightPriceScale: {
      borderColor: '#dbe2ea',
    },
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

  resizeObserver = new ResizeObserver(() => {
    const width = root.clientWidth
    const height = root.clientHeight
    chart?.resize(width, height)
  })
  resizeObserver.observe(root)
}

function refreshNow() {
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
})

watch(
  () => props.symbol,
  async () => {
    await loadData()
  }
)

watch(activeResolution, async () => {
  await loadData()
})
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
    </div>

    <div v-loading="loading" class="chart-root" ref="chartRootRef" />
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
