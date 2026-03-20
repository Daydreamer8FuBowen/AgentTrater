<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  title: string
  xData: string[]
  yData: number[]
  color?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!chartEl.value) {
    return
  }

  if (!chart) {
    chart = echarts.init(chartEl.value)
  }

  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 12, top: 40, bottom: 28 },
    title: { text: props.title, textStyle: { fontSize: 14 } },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: props.xData
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#ebedf3' } }
    },
    series: [
      {
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.12 },
        lineStyle: { width: 2, color: props.color ?? '#1890ff' },
        itemStyle: { color: props.color ?? '#1890ff' },
        data: props.yData
      }
    ]
  })
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})

watch(() => [props.xData, props.yData], render)

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="chartEl" class="chart-box"></div>
</template>
