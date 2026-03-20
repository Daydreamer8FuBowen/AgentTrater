<script setup lang="ts">
import { computed, ref } from 'vue'

type AgentStatus = 'running' | 'paused' | 'error'

interface AgentItem {
  id: string
  name: string
  type: string
  strategy: string
  pnl: number
  status: AgentStatus
}

const viewMode = ref<'table' | 'card'>('table')
const typeFilter = ref('all')
const statusFilter = ref('all')
const keyword = ref('')

const rows = ref<AgentItem[]>([
  { id: 'A-001', name: 'Momentum Scout', type: 'alpha', strategy: '动量突破', pnl: 8.2, status: 'running' },
  { id: 'A-002', name: 'Mean Reverter', type: 'arbitrage', strategy: '均值回归', pnl: 2.1, status: 'paused' },
  { id: 'A-003', name: 'Risk Sentinel', type: 'risk', strategy: '风控监控', pnl: -0.7, status: 'error' },
  { id: 'A-004', name: 'Flow Hunter', type: 'alpha', strategy: '资金流择时', pnl: 4.4, status: 'running' }
])

const selectedAgent = ref<AgentItem | null>(null)
const drawerVisible = ref(false)

const filteredRows = computed(() => {
  return rows.value.filter((item) => {
    const byType = typeFilter.value === 'all' || item.type === typeFilter.value
    const byStatus = statusFilter.value === 'all' || item.status === statusFilter.value
    const byKeyword = !keyword.value || item.name.toLowerCase().includes(keyword.value.toLowerCase())
    return byType && byStatus && byKeyword
  })
})

function statusTag(status: AgentStatus): 'success' | 'warning' | 'danger' {
  if (status === 'running') {
    return 'success'
  }
  if (status === 'paused') {
    return 'warning'
  }
  return 'danger'
}

function statusLabel(status: AgentStatus): string {
  if (status === 'running') {
    return '运行中'
  }
  if (status === 'paused') {
    return '暂停'
  }
  return '异常'
}

function openDetails(agent: AgentItem) {
  selectedAgent.value = agent
  drawerVisible.value = true
}
</script>

<template>
  <div class="module-panel">
    <div class="module-header">
      <div>
        <h2>智能体管理</h2>
        <p>支持筛选、状态可视化、详情抽屉与批量运维操作。</p>
      </div>
      <div class="header-actions">
        <el-button type="primary">新建智能体</el-button>
        <el-button>批量启动</el-button>
        <el-button>批量停止</el-button>
      </div>
    </div>

    <el-card>
      <div class="filter-grid agent-filter-grid">
        <el-select v-model="typeFilter">
          <el-option label="全部类型" value="all" />
          <el-option label="Alpha" value="alpha" />
          <el-option label="Arbitrage" value="arbitrage" />
          <el-option label="Risk" value="risk" />
        </el-select>
        <el-select v-model="statusFilter">
          <el-option label="全部状态" value="all" />
          <el-option label="运行中" value="running" />
          <el-option label="暂停" value="paused" />
          <el-option label="异常" value="error" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索智能体名称" clearable />
        <el-segmented v-model="viewMode" :options="[{ label: '表格', value: 'table' }, { label: '卡片', value: 'card' }]" />
      </div>

      <el-table v-if="viewMode === 'table'" :data="filteredRows" border style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="name" label="智能体" min-width="160" />
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="strategy" label="策略" min-width="150" />
        <el-table-column label="收益" width="120">
          <template #default="scope">
            <span :class="scope.row.pnl >= 0 ? 'text-profit' : 'text-loss'">{{ scope.row.pnl.toFixed(2) }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="statusTag(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="openDetails(scope.row)">详情</el-button>
            <el-button link type="success">启动</el-button>
            <el-button link type="warning">停止</el-button>
            <el-button link type="danger">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="agent-card-grid">
        <el-card v-for="agent in filteredRows" :key="agent.id" shadow="hover">
          <div class="agent-card-head">
            <div>
              <h4>{{ agent.name }}</h4>
              <p>{{ agent.strategy }}</p>
            </div>
            <el-tag :type="statusTag(agent.status)">{{ statusLabel(agent.status) }}</el-tag>
          </div>
          <p>类型：{{ agent.type }}</p>
          <p>收益：<span :class="agent.pnl >= 0 ? 'text-profit' : 'text-loss'">{{ agent.pnl.toFixed(2) }}%</span></p>
          <el-button type="primary" plain @click="openDetails(agent)">查看详情</el-button>
        </el-card>
      </div>
    </el-card>

    <el-drawer v-model="drawerVisible" title="智能体详情" size="35%">
      <div v-if="selectedAgent" class="detail-lines">
        <p><strong>名称：</strong>{{ selectedAgent.name }}</p>
        <p><strong>类型：</strong>{{ selectedAgent.type }}</p>
        <p><strong>策略：</strong>{{ selectedAgent.strategy }}</p>
        <p><strong>运行状态：</strong>{{ statusLabel(selectedAgent.status) }}</p>
        <p><strong>当前收益：</strong>{{ selectedAgent.pnl.toFixed(2) }}%</p>
        <el-divider />
        <p><strong>运行日志：</strong></p>
        <el-alert title="09:35 已启动市场事件监听" type="success" :closable="false" />
        <el-alert title="10:12 动量阈值触发，执行加仓" type="info" :closable="false" style="margin-top: 8px" />
        <el-alert title="14:40 风险敞口接近上限" type="warning" :closable="false" style="margin-top: 8px" />
      </div>
    </el-drawer>
  </div>
</template>
