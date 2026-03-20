<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  title: string
  categoryData: string[]
  values: Array<[number, number, number, number]>
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
    grid: { left: 40, right: 12, top: 40, bottom: 28 },
    title: { text: props.title, textStyle: { fontSize: 14 } },
    xAxis: {
      type: 'category',
      data: props.categoryData,
      boundaryGap: true,
      axisLine: { lineStyle: { color: '#8a919e' } }
    },
    yAxis: {
      scale: true,
      splitLine: { lineStyle: { color: '#ebedf3' } }
    },
    series: [
      {
        type: 'candlestick',
        data: props.values,
        itemStyle: {
          color: '#f5222d',
          color0: '#52c41a',
          borderColor: '#f5222d',
          borderColor0: '#52c41a'
        }
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

watch(() => [props.categoryData, props.values], render)

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="chartEl" class="chart-box"></div>
</template>
