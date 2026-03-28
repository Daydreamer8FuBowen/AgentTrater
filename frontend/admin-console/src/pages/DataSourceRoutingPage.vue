<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import {
  fetchDataSourceRoutesOverview,
  type RoutePriorityPayload,
  updateRoutePriorities
} from '../api/dataSourceApi'

const loading = ref(false)
const saving = ref(false)
const capabilityFilter = ref('')
const marketFilter = ref('')
const routeData = ref<{ sources: { name: string; capabilities: { capability: string; markets: string[]; intervals: string[] }[] }[]; routes: RoutePriorityPayload[] }>({
  sources: [],
  routes: []
})

const selectedRouteId = ref('')
const editingPriorities = ref<string[]>([])
const editingEnabled = ref(true)

const capabilityOptions = computed(() => {
  return Array.from(new Set(routeData.value.routes.map((item) => item.capability))).sort()
})

const marketOptions = computed(() => {
  return Array.from(new Set(routeData.value.routes.map((item) => item.market).filter(Boolean) as string[])).sort()
})

const filteredRoutes = computed(() => {
  return routeData.value.routes.filter((item) => {
    if (capabilityFilter.value && item.capability !== capabilityFilter.value) {
      return false
    }
    if (marketFilter.value && item.market !== marketFilter.value) {
      return false
    }
    return true
  })
})

const selectedRoute = computed(() => {
  return routeData.value.routes.find((item) => item.route_id === selectedRouteId.value) ?? null
})

const sourceCount = computed(() => routeData.value.sources.length)
const routeCount = computed(() => routeData.value.routes.length)
const enabledRouteCount = computed(() => routeData.value.routes.filter((item) => item.enabled).length)

function formatDimension(value: string | null): string {
  return value || '*'
}

function formatCapabilities(source: { capabilities: { capability: string; markets: string[]; intervals: string[] }[] }): string {
  if (source.capabilities.length === 0) {
    return '-'
  }
  return source.capabilities
    .map((item) => `${item.capability} [market:${item.markets.join(',') || '*'} interval:${item.intervals.join(',') || '*'}]`)
    .join(' | ')
}

function startEditing(route: RoutePriorityPayload) {
  selectedRouteId.value = route.route_id
  editingPriorities.value = [...route.priorities]
  editingEnabled.value = route.enabled
}

function movePriority(index: number, offset: -1 | 1) {
  const target = index + offset
  if (target < 0 || target >= editingPriorities.value.length) {
    return
  }
  const next = [...editingPriorities.value]
  const current = next[index]
  next[index] = next[target]
  next[target] = current
  editingPriorities.value = next
}

function resetPriorities() {
  if (!selectedRoute.value) {
    return
  }
  editingPriorities.value = [...selectedRoute.value.supported_sources]
}

async function loadRoutes() {
  loading.value = true
  try {
    const payload = await fetchDataSourceRoutesOverview()
    routeData.value = payload
    if (selectedRouteId.value) {
      const latest = payload.routes.find((item) => item.route_id === selectedRouteId.value)
      if (latest) {
        editingPriorities.value = [...latest.priorities]
        editingEnabled.value = latest.enabled
      } else {
        selectedRouteId.value = ''
        editingPriorities.value = []
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    ElMessage.error(`加载失败: ${message}`)
  } finally {
    loading.value = false
  }
}

async function saveCurrentRoute() {
  if (!selectedRoute.value) {
    return
  }
  saving.value = true
  try {
    await updateRoutePriorities(selectedRoute.value.route_id, {
      priorities: editingPriorities.value,
      enabled: editingEnabled.value
    })
    ElMessage.success('优先级已更新')
    await loadRoutes()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    ElMessage.error(`保存失败: ${message}`)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadRoutes()
})
</script>

<template>
  <div class="module-panel">
    <div class="module-header">
      <div>
        <h2>数据源路由管理</h2>
        <p>展示数据源能力、路由维度与优先级，并支持在线调整优先级顺序。</p>
      </div>
      <div class="header-actions">
        <el-tag type="info">数据源 {{ sourceCount }}</el-tag>
        <el-tag type="success">路由 {{ routeCount }}</el-tag>
        <el-tag>启用 {{ enabledRouteCount }}</el-tag>
        <el-button :loading="loading" @click="loadRoutes">刷新</el-button>
      </div>
    </div>

    <el-card>
      <template #header>
        <span>数据源能力</span>
      </template>
      <el-table :data="routeData.sources" v-loading="loading">
        <el-table-column prop="name" label="数据源" min-width="140" />
        <el-table-column label="支持能力">
          <template #default="{ row }">
            {{ formatCapabilities(row) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div class="data-source-grid">
      <el-card>
        <template #header>
          <div class="route-filter-header">
            <span>路由优先级</span>
            <div class="route-filters">
              <el-select v-model="capabilityFilter" clearable placeholder="能力" style="width: 130px">
                <el-option v-for="item in capabilityOptions" :key="item" :label="item" :value="item" />
              </el-select>
              <el-select v-model="marketFilter" clearable placeholder="市场" style="width: 130px">
                <el-option v-for="item in marketOptions" :key="item" :label="item" :value="item" />
              </el-select>
            </div>
          </div>
        </template>
        <el-table :data="filteredRoutes" v-loading="loading" height="520">
          <el-table-column prop="capability" label="能力" width="120" />
          <el-table-column label="市场" width="100">
            <template #default="{ row }">{{ formatDimension(row.market) }}</template>
          </el-table-column>
          <el-table-column label="周期" width="100">
            <template #default="{ row }">{{ formatDimension(row.interval) }}</template>
          </el-table-column>
          <el-table-column label="优先级" min-width="280">
            <template #default="{ row }">
              <el-space wrap>
                <el-tag v-for="source in row.priorities" :key="`${row.route_id}-${source}`">{{ source }}</el-tag>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" text @click="startEditing(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card>
        <template #header>
          <span>优先级编辑器</span>
        </template>
        <div v-if="selectedRoute" class="priority-editor">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="路由">{{ selectedRoute.route_id }}</el-descriptions-item>
            <el-descriptions-item label="支持源">
              {{ selectedRoute.supported_sources.join(', ') }}
            </el-descriptions-item>
          </el-descriptions>

          <div class="priority-list">
            <div v-for="(source, index) in editingPriorities" :key="`${source}-${index}`" class="priority-item">
              <el-tag size="large">{{ index + 1 }}. {{ source }}</el-tag>
              <div class="priority-item-actions">
                <el-button :disabled="index === 0" @click="movePriority(index, -1)">上移</el-button>
                <el-button :disabled="index === editingPriorities.length - 1" @click="movePriority(index, 1)">下移</el-button>
              </div>
            </div>
          </div>

          <div class="route-status">
            <span>路由状态</span>
            <el-switch v-model="editingEnabled" />
          </div>

          <div class="footer-actions">
            <el-button @click="resetPriorities">重置为默认顺序</el-button>
            <el-button type="primary" :loading="saving" @click="saveCurrentRoute">保存</el-button>
          </div>
        </div>
        <el-empty v-else description="请先在左侧选择一个路由进行编辑" />
      </el-card>
    </div>
  </div>
</template>
