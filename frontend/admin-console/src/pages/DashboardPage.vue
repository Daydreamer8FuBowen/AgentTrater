<script setup lang="ts">
import { Plus, Promotion, TrendCharts } from '@element-plus/icons-vue'
import CandlestickChart from '../components/charts/CandlestickChart.vue'
import LineChart from '../components/charts/LineChart.vue'

const metrics = [
  { label: '实时收益率', value: '+12.84%', color: 'profit' },
  { label: '策略胜率', value: '63.2%', color: 'normal' },
  { label: '智能体在线数', value: '18 / 22', color: 'running' },
  { label: '当日告警', value: '3', color: 'warning' }
]

const candleDates = ['03-12', '03-13', '03-14', '03-15', '03-16', '03-17', '03-18', '03-19']
const candleValues: Array<[number, number, number, number]> = [
  [3210, 3260, 3302, 3190],
  [3260, 3242, 3280, 3221],
  [3242, 3308, 3322, 3239],
  [3308, 3344, 3368, 3299],
  [3344, 3320, 3360, 3314],
  [3320, 3362, 3388, 3318],
  [3362, 3405, 3418, 3359],
  [3405, 3381, 3412, 3376]
]

const pnlDates = ['09:30', '10:30', '11:30', '13:00', '14:00', '15:00']
const pnlValues = [0.2, 1.8, 1.2, 2.7, 3.4, 2.9]
</script>

<template>
  <div class="module-panel">
    <div class="module-header">
      <div>
        <h2>首页仪表盘</h2>
        <p>展示收益、胜率、在线智能体、行情趋势与快捷操作。</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus">新建策略</el-button>
        <el-button type="success" :icon="Promotion">启动智能体</el-button>
      </div>
    </div>

    <div class="metric-grid">
      <el-card v-for="metric in metrics" :key="metric.label" class="metric-card">
        <p class="metric-label">{{ metric.label }}</p>
        <p class="metric-value" :class="metric.color">{{ metric.value }}</p>
      </el-card>
    </div>

    <div class="dashboard-grid">
      <el-card>
        <CandlestickChart title="市场 K 线" :category-data="candleDates" :values="candleValues" />
      </el-card>
      <el-card>
        <LineChart title="当日收益曲线" :x-data="pnlDates" :y-data="pnlValues" color="#13c2c2" />
      </el-card>
    </div>

    <el-card>
      <template #header>
        <div class="card-title-with-icon">
          <el-icon><TrendCharts /></el-icon>
          <span>快速操作区</span>
        </div>
      </template>
      <div class="quick-actions">
        <el-button>查看运行日志</el-button>
        <el-button>切换回测环境</el-button>
        <el-button>导出今日分析报告</el-button>
        <el-button type="primary">进入表管理中心</el-button>
      </div>
    </el-card>
  </div>
</template>
