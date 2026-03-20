<script setup lang="ts">
import { Edit, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { fetchManageableTables, fetchTableRows, updateTableRow } from '../../api/tableApi'
import { fallbackTableSchemas } from '../../config/tableSchemas'
import type { JsonValue, TableMetadata } from '../../types'
import { toDisplayText, toPrettyText } from '../../utils/format'

const props = defineProps<{
  tableName: string
  title: string
  description: string
}>()

const schema = ref<TableMetadata | null>(null)
const mode = ref<'online' | 'offline'>('online')
const rows = ref<Array<Record<string, JsonValue>>>([])
const page = ref(1)
const pageSize = ref(15)
const total = ref(0)
const keyword = ref('')
const filtersText = ref('')
const loading = ref(false)
const drawerVisible = ref(false)
const editRow = ref<Record<string, JsonValue> | null>(null)

const columns = computed(() => schema.value?.columns ?? [])
const primaryKey = computed(() => schema.value?.primary_key ?? 'id')

function parseFilters(): Record<string, string> {
  const source = filtersText.value.trim()
  if (!source) {
    return {}
  }

  const parsed = JSON.parse(source)
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new Error('过滤条件必须是 JSON 对象')
  }

  return parsed as Record<string, string>
}

async function loadSchema() {
  try {
    const tables = await fetchManageableTables()
    schema.value = tables.find((item) => item.name === props.tableName) ?? null
    mode.value = 'online'
  } catch {
    schema.value = fallbackTableSchemas.find((item) => item.name === props.tableName) ?? null
    mode.value = 'offline'
  }
}

async function loadRows() {
  if (!schema.value) {
    return
  }

  if (mode.value === 'offline') {
    rows.value = []
    total.value = 0
    return
  }

  try {
    loading.value = true
    const filters = parseFilters()
    const result = await fetchTableRows({
      tableName: props.tableName,
      page: page.value,
      pageSize: pageSize.value,
      keyword: keyword.value || undefined,
      filters
    })
    rows.value = result.items
    total.value = result.total
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

function openDrawer(row: Record<string, JsonValue>) {
  editRow.value = JSON.parse(JSON.stringify(row)) as Record<string, JsonValue>
  drawerVisible.value = true
}

function updateEditField(column: string, value: string) {
  if (!editRow.value || !schema.value) {
    return
  }

  if (schema.value.json_columns.includes(column)) {
    editRow.value[column] = value.trim() ? (JSON.parse(value) as JsonValue) : null
    return
  }

  editRow.value[column] = value
}

async function saveRow() {
  if (!schema.value || !editRow.value) {
    return
  }

  if (mode.value === 'offline') {
    ElMessage.warning('当前为离线演示模式，不执行真实写入。')
    return
  }

  const rowId = String(editRow.value[primaryKey.value] ?? '')
  const updates: Record<string, unknown> = {}

  for (const column of schema.value.columns) {
    if (column === primaryKey.value || column === 'created_at') {
      continue
    }
    updates[column] = editRow.value[column]
  }

  try {
    loading.value = true
    await updateTableRow(props.tableName, rowId, updates)
    drawerVisible.value = false
    ElMessage.success(`记录 ${rowId} 更新成功`)
    await loadRows()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadSchema()
  await loadRows()
})
</script>

<template>
  <div class="module-panel">
    <div class="module-header">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
      <div class="module-actions">
        <el-tag :type="mode === 'online' ? 'success' : 'warning'">{{ mode === 'online' ? '在线数据源' : '离线静态模式' }}</el-tag>
        <el-button type="primary" :icon="Refresh" @click="loadRows">刷新</el-button>
      </div>
    </div>

    <el-card>
      <div class="filter-grid">
        <el-input v-model="keyword" placeholder="输入关键字（按 searchable_columns 匹配）" clearable @keyup.enter="page = 1; loadRows()" />
        <el-input v-model="filtersText" placeholder='JSON过滤，例如 {"agent_id":1}' clearable @keyup.enter="page = 1; loadRows()" />
        <el-button type="primary" @click="page = 1; loadRows()">查询</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" style="width: 100%; margin-top: 16px" border>
        <el-table-column
          v-for="column in columns"
          :key="column"
          :prop="column"
          :label="column"
          min-width="140"
          show-overflow-tooltip
        >
          <template #default="scope">
            {{ toDisplayText(scope.row[column]) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="90">
          <template #default="scope">
            <el-button :icon="Edit" link type="primary" @click="openDrawer(scope.row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[15, 30, 50]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @size-change="loadRows"
          @current-change="loadRows"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawerVisible" size="45%" title="编辑记录">
      <div v-if="editRow && schema" class="edit-grid">
        <div v-for="column in schema.columns" :key="column" class="field-item">
          <label>{{ column }}</label>
          <el-input
            v-if="typeof editRow[column] !== 'object'"
            :model-value="toPrettyText(editRow[column])"
            :disabled="column === primaryKey || column === 'created_at'"
            @update:model-value="(value: string) => updateEditField(column, value)"
          />
          <el-input
            v-else
            type="textarea"
            :rows="6"
            :model-value="toPrettyText(editRow[column])"
            :disabled="column === primaryKey || column === 'created_at'"
            @update:model-value="(value: string) => updateEditField(column, value)"
          />
        </div>
      </div>
      <template #footer>
        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="saveRow">保存修改</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>
