<script setup lang="ts">
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import TradingViewKlineChart from '../components/symbols/TradingViewKlineChart.vue'
import { fetchSymbolDetail, type SymbolDetailResponse } from '../api/symbolsApi'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<SymbolDetailResponse | null>(null)

const symbol = computed(() => String(route.params.symbol || '').toUpperCase())

const basicInfo = computed(() => detail.value?.basic_info ?? {})
const syncStates = computed(() => detail.value?.sync_states ?? [])
const d1Progress = computed(() => detail.value?.d1_progress ?? null)

const progressPercentage = computed(() => {
  const ratio = Number(d1Progress.value?.completion_ratio ?? 0)
  return Math.max(0, Math.min(100, Math.round(ratio * 100)))
})

function normalizeText(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '--'
  }
  return String(value)
}

function formatDate(value: unknown): string {
  if (!value) return '--'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return '--'
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
}

function statusType(status: unknown): 'success' | 'warning' | 'danger' | 'info' {
  const value = String(status || '').toLowerCase()
  if (value === 'ok' || value === 'completed') {
    return 'success'
  }
  if (value === 'lagging' || value === 'running') {
    return 'warning'
  }
  if (value === 'failed') {
    return 'danger'
  }
  return 'info'
}

async function loadDetail() {
  if (!symbol.value) {
    return
  }
  loading.value = true
  try {
    detail.value = await fetchSymbolDetail(symbol.value)
  } catch (error) {
    ElMessage.error(`加载详情失败: ${String(error)}`)
  } finally {
    loading.value = false
  }
}

function goBack() {
  void router.push('/symbols')
}

onMounted(async () => {
  await loadDetail()
})
</script>

<template>
  <div class="symbol-detail-page module-panel" v-loading="loading">
    <section class="detail-hero">
      <el-button :icon="ArrowLeft" @click="goBack">返回列表</el-button>
      <div>
        <h2>{{ symbol }}</h2>
        <p>公司基本面与同步状态总览</p>
      </div>
      <el-tag :type="statusType(d1Progress?.status)" effect="dark">D1 进度 {{ progressPercentage }}%</el-tag>
    </section>

    <section class="overview-metrics">
      <el-card shadow="never" class="metric-box">
        <p>市场</p>
        <h3>{{ normalizeText(basicInfo.market) }}</h3>
      </el-card>
      <el-card shadow="never" class="metric-box">
        <p>行业</p>
        <h3>{{ normalizeText(basicInfo.industry) }}</h3>
      </el-card>
      <el-card shadow="never" class="metric-box">
        <p>D1 回补状态</p>
        <h3>{{ normalizeText(d1Progress?.status) }}</h3>
      </el-card>
      <el-card shadow="never" class="metric-box">
        <p>D1 游标时间</p>
        <h3>{{ formatDate(d1Progress?.cursor) }}</h3>
      </el-card>
    </section>

    <div class="detail-grid">
      <el-card shadow="never" class="info-card">
        <template #header>
          <div class="card-header">公司基本面</div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Symbol">{{ normalizeText(basicInfo.symbol) }}</el-descriptions-item>
          <el-descriptions-item label="公司名称">{{ normalizeText(basicInfo.name) }}</el-descriptions-item>
          <el-descriptions-item label="市场">{{ normalizeText(basicInfo.market) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ normalizeText(basicInfo.status) }}</el-descriptions-item>
          <el-descriptions-item label="证券类型">{{ normalizeText(basicInfo.security_type) }}</el-descriptions-item>
          <el-descriptions-item label="行业">{{ normalizeText(basicInfo.industry) }}</el-descriptions-item>
          <el-descriptions-item label="地区">{{ normalizeText(basicInfo.area) }}</el-descriptions-item>
          <el-descriptions-item label="上市日期">{{ formatDate(basicInfo.list_date) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never" class="info-card">
        <template #header>
          <div class="card-header">同步状态</div>
        </template>
        <el-table :data="syncStates" size="small" stripe>
          <el-table-column prop="interval" label="周期" width="90" />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="scope">
              <el-tag size="small" :type="statusType(scope.row.status)">{{ scope.row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="last_bar_time" label="最新 Bar 时间" min-width="180">
            <template #default="scope">{{ formatDate(scope.row.last_bar_time) }}</template>
          </el-table-column>
          <el-table-column prop="lag_seconds" label="延迟(秒)" width="110" />
          <el-table-column prop="consecutive_failures" label="连续失败" width="110" />
        </el-table>
      </el-card>
    </div>

    <TradingViewKlineChart :symbol="symbol" />
  </div>
</template>

<style scoped>
.symbol-detail-page {
  gap: 14px;
}

.detail-hero {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid #e7edf6;
  background: linear-gradient(130deg, #f8fffb 0%, #f6fbff 100%);
  justify-content: space-between;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.detail-hero h2 {
  margin: 0;
  font-size: 26px;
}

.detail-hero p {
  margin: 6px 0 0;
  color: #64748b;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 14px;
}

.overview-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-box {
  border-radius: 14px;
  border: 1px solid #e6ecf3;
}

.metric-box p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.metric-box h3 {
  margin: 8px 0 0;
  font-size: 18px;
  line-height: 1.3;
}

.info-card {
  border-radius: 16px;
  border: 1px solid #e6ecf3;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
}

.card-header {
  font-weight: 600;
}

@media (max-width: 1024px) {
  .overview-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .overview-metrics {
    grid-template-columns: 1fr;
  }

  .detail-hero {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
