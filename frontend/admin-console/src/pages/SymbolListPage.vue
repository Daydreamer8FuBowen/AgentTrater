<script setup lang="ts">
import { RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { fetchSymbolMonitor, type SymbolMonitorItem } from '../api/symbolsApi'

const router = useRouter()
const loading = ref(false)
const rows = ref<SymbolMonitorItem[]>([])
const total = ref(0)

const filters = reactive({
  keyword: '',
  market: '',
  status: '',
  security_type: '',
  page: 1,
  page_size: 20,
})

let filterTimer: ReturnType<typeof setTimeout> | null = null

const marketOptions = [
  { label: '全部市场', value: '' },
  { label: '上交所 (sh)', value: 'sh' },
  { label: '深交所 (sz)', value: 'sz' },
]

const securityTypeOptions = [
  { label: '全部类型', value: '' },
  { label: '股票', value: 'stock' },
  { label: '指数', value: 'index' },
  { label: '基金', value: 'fund' },
]

const statusOptions = [
  { label: '全部状态', value: '' },
  { label: '上市', value: '1' },
  { label: '停牌/退市', value: '0' },
]

const summaryText = computed(() => `共 ${total.value} 个标的`) 
const activeFilterCount = computed(() => {
  return [filters.keyword, filters.market, filters.status, filters.security_type].filter((item) => String(item).trim() !== '').length
})

const quickKeywords = ['银行', '医药', '新能源', '芯片', '消费']

function formatPercent(ratio: number): number {
  return Math.max(0, Math.min(100, Math.round((ratio || 0) * 100)))
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return '暂无'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '暂无'
  }
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'ok') {
    return 'success'
  }
  if (status === 'lagging') {
    return 'warning'
  }
  if (status === 'failed') {
    return 'danger'
  }
  return 'info'
}

function progressStatusType(status: string): 'success' | 'warning' | 'exception' {
  if (status === 'completed') {
    return 'success'
  }
  if (status === 'failed') {
    return 'exception'
  }
  return 'warning'
}

function formatRelative(value: string | null): string {
  if (!value) {
    return '未同步'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '未同步'
  }
  const deltaSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (deltaSeconds < 60) {
    return `${deltaSeconds}s 前`
  }
  if (deltaSeconds < 3600) {
    return `${Math.floor(deltaSeconds / 60)}m 前`
  }
  if (deltaSeconds < 86400) {
    return `${Math.floor(deltaSeconds / 3600)}h 前`
  }
  return `${Math.floor(deltaSeconds / 86400)}d 前`
}

async function loadData() {
  loading.value = true
  try {
    const payload = await fetchSymbolMonitor({
      keyword: filters.keyword,
      market: filters.market,
      status: filters.status,
      security_type: filters.security_type,
      page: filters.page,
      page_size: filters.page_size,
    })
    rows.value = payload.items
    total.value = payload.total
  } catch (error) {
    ElMessage.error(`加载 symbol 列表失败: ${String(error)}`)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.market = ''
  filters.status = ''
  filters.security_type = ''
  filters.page = 1
  void loadData()
}

function applyQuickKeyword(keyword: string) {
  filters.keyword = keyword
  filters.page = 1
  void loadData()
}

function goDetail(symbol: string) {
  void router.push(`/symbols/${encodeURIComponent(symbol)}`)
}

function onSearch() {
  filters.page = 1
  void loadData()
}

function onPageChange(page: number) {
  filters.page = page
  void loadData()
}

function onPageSizeChange(size: number) {
  filters.page_size = size
  filters.page = 1
  void loadData()
}

onMounted(async () => {
  await loadData()
})

watch(
  () => [filters.market, filters.status, filters.security_type],
  () => {
    if (filterTimer) {
      clearTimeout(filterTimer)
    }
    filterTimer = setTimeout(() => {
      filters.page = 1
      void loadData()
    }, 240)
  }
)
</script>

<template>
  <div class="symbol-page module-panel">
    <section class="symbol-hero">
      <div>
        <h2>Symbol 同步监控中心</h2>
        <p>支持条件筛选、模糊查询、同步进度追踪与详情钻取</p>
      </div>
      <div class="hero-tags">
        <el-tag type="success" effect="dark">{{ summaryText }}</el-tag>
        <el-tag type="info" effect="plain">筛选条件 {{ activeFilterCount }}</el-tag>
      </div>
    </section>

    <el-card shadow="never" class="symbol-filter-card">
      <div class="symbol-filter-grid">
        <el-input v-model="filters.keyword" placeholder="按 symbol 或公司名模糊搜索" clearable @keyup.enter="onSearch">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="filters.market" placeholder="市场">
          <el-option v-for="option in marketOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态">
          <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-select v-model="filters.security_type" placeholder="证券类型">
          <el-option v-for="option in securityTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <div class="symbol-filter-actions">
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
      </div>
      <div class="quick-keywords">
        <span>快速筛选:</span>
        <el-tag
          v-for="keyword in quickKeywords"
          :key="keyword"
          class="keyword-tag"
          effect="plain"
          @click="applyQuickKeyword(keyword)"
        >
          {{ keyword }}
        </el-tag>
      </div>
    </el-card>

    <el-card shadow="never" class="symbol-table-card">
      <el-table v-loading="loading" :data="rows" stripe :row-class-name="() => 'symbol-row'" @row-click="(row) => goDetail(row.symbol)">
        <el-table-column prop="symbol" label="Symbol" min-width="120" />
        <el-table-column prop="name" label="公司名称" min-width="180" />
        <el-table-column prop="market" label="市场" width="100" />
        <el-table-column prop="industry" label="行业" min-width="140" show-overflow-tooltip />
        <el-table-column label="1D 回补进度" width="150">
          <template #default="scope">
            <div class="progress-cell">
              <el-progress
                type="circle"
                :width="44"
                :stroke-width="7"
                :percentage="formatPercent(scope.row.d1_completion_ratio)"
                :status="progressStatusType(scope.row.d1_progress_status)"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最新数据时间" min-width="220">
          <template #default="scope">
            <div class="latest-cell">
              <span>{{ formatDateTime(scope.row.latest_bar_time) }}</span>
              <small>{{ formatRelative(scope.row.latest_bar_time) }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="statusTagType(scope.row.sync_status)">
              {{ scope.row.sync_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click.stop="goDetail(scope.row.symbol)">详情</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无匹配的 symbol，试试调整筛选条件" />
        </template>
      </el-table>

      <div class="table-pager">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :current-page="filters.page"
          :page-size="filters.page_size"
          :page-sizes="[20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>

      <div class="table-foot-note">
        <el-icon><RefreshRight /></el-icon>
        <span>提示：行点击可直接进入详情页；最新时间优先显示 5m，同步状态来自后台同步状态表。</span>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.symbol-page {
  gap: 14px;
}

.symbol-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  border-radius: 16px;
  background: linear-gradient(110deg, #fff8ef 0%, #f3fbff 70%, #ffffff 100%);
  border: 1px solid #e7edf6;
  box-shadow: 0 8px 24px rgba(29, 78, 216, 0.08);
}

.symbol-hero h2 {
  margin: 0;
  font-size: 24px;
}

.symbol-hero p {
  margin: 8px 0 0;
  color: #64748b;
}

.symbol-filter-card,
.symbol-table-card {
  border: 1px solid #e6ecf3;
  border-radius: 16px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.symbol-filter-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr auto;
  gap: 10px;
}

.symbol-filter-actions {
  display: flex;
  gap: 8px;
}

.hero-tags {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.quick-keywords {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  color: #64748b;
  flex-wrap: wrap;
}

.keyword-tag {
  cursor: pointer;
  user-select: none;
}

.keyword-tag:hover {
  border-color: #1d4ed8;
  color: #1d4ed8;
}

.progress-cell {
  display: flex;
  justify-content: center;
}

.latest-cell {
  display: grid;
  gap: 2px;
}

.latest-cell small {
  color: #64748b;
}

.table-foot-note {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

@media (max-width: 980px) {
  .symbol-filter-grid {
    grid-template-columns: 1fr;
  }

  .symbol-filter-actions {
    justify-content: flex-end;
  }

  .symbol-hero {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>

<style>
.symbol-row {
  cursor: pointer;
}

.symbol-row:hover > td {
  background: #f8fbff !important;
}
</style>
