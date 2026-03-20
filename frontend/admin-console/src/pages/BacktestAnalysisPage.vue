<script setup lang="ts">
import CandlestickChart from '../components/charts/CandlestickChart.vue'
import LineChart from '../components/charts/LineChart.vue'

const dateRange = ['2025-12-01', '2026-03-20']

const summaryCards = [
  { label: '累计收益率', value: '18.4%' },
  { label: '最大回撤', value: '-7.8%' },
  { label: '夏普比率', value: '1.92' },
  { label: '胜率', value: '61.7%' }
]

const compareRows = [
  { strategy: '多因子趋势', ret: 18.4, drawdown: -7.8, sharpe: 1.92, winRate: 61.7 },
  { strategy: '均值回归A', ret: 12.2, drawdown: -5.1, sharpe: 1.55, winRate: 58.2 },
  { strategy: '动量强化B', ret: 22.9, drawdown: -12.4, sharpe: 1.61, winRate: 64.0 }
]

const lineX = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8']
const strategyCurve = [1.2, 2.1, 4.0, 5.2, 8.7, 11.3, 14.1, 18.4]
const benchmarkCurve = [0.8, 1.4, 2.0, 2.8, 4.1, 5.6, 6.1, 6.8]
const kDates = ['01-02', '01-09', '01-16', '01-23', '01-30', '02-06', '02-13', '02-20']
const kValues: Array<[number, number, number, number]> = [
  [3020, 3065, 3090, 3004],
  [3065, 3051, 3072, 3032],
  [3051, 3112, 3122, 3044],
  [3112, 3140, 3162, 3100],
  [3140, 3108, 3150, 3090],
  [3108, 3156, 3170, 3092],
  [3156, 3182, 3190, 3149],
  [3182, 3170, 3188, 3160]
]
</script>

<template>
  <div class="module-panel">
    <div class="module-header">
      <div>
        <h2>回测分析</h2>
        <p>收益曲线、最大回撤、夏普比率与策略对比分析。</p>
      </div>
      <div class="header-actions">
        <el-date-picker type="daterange" :model-value="dateRange" start-placeholder="开始日期" end-placeholder="结束日期" />
        <el-button>导出 Excel</el-button>
        <el-button>导出 PDF</el-button>
      </div>
    </div>

    <div class="metric-grid">
      <el-card v-for="item in summaryCards" :key="item.label" class="metric-card">
        <p class="metric-label">{{ item.label }}</p>
        <p class="metric-value normal">{{ item.value }}</p>
      </el-card>
    </div>

    <div class="dashboard-grid">
      <el-card>
        <LineChart title="策略收益曲线" :x-data="lineX" :y-data="strategyCurve" color="#52c41a" />
      </el-card>
      <el-card>
        <LineChart title="基准收益曲线" :x-data="lineX" :y-data="benchmarkCurve" color="#faad14" />
      </el-card>
    </div>

    <el-card>
      <CandlestickChart title="回测阶段市场 K 线" :category-data="kDates" :values="kValues" />
    </el-card>

    <el-card>
      <template #header>
        <span>多策略横向对比</span>
      </template>
      <el-table :data="compareRows" border>
        <el-table-column prop="strategy" label="策略名称" min-width="160" />
        <el-table-column prop="ret" label="收益率(%)" width="120" />
        <el-table-column prop="drawdown" label="最大回撤(%)" width="140" />
        <el-table-column prop="sharpe" label="夏普比率" width="120" />
        <el-table-column prop="winRate" label="胜率(%)" width="120" />
      </el-table>
    </el-card>
  </div>
</template>
