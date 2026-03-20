<script setup lang="ts">
import {
  ArrowLeftBold,
  ArrowRightBold,
  ArrowDown,
  Coin,
  Cpu,
  DataAnalysis,
  DataBoard,
  Histogram,
  Monitor,
  SetUp,
  TrendCharts
} from '@element-plus/icons-vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const COLLAPSE_STORAGE_KEY = 'agent-trader-admin-sidebar-collapse'

const isCollapse = ref(localStorage.getItem(COLLAPSE_STORAGE_KEY) === '1')

const menuGroups = [
  {
    key: 'core',
    title: '核心模块',
    items: [
      { label: '仪表盘', icon: DataBoard, path: '/dashboard' },
      { label: '智能体管理', icon: Cpu, path: '/agents' },
      { label: '策略编辑', icon: TrendCharts, path: '/strategy-editor' },
      { label: '回测分析', icon: DataAnalysis, path: '/backtest-analysis' },
      { label: '系统配置', icon: SetUp, path: '/system-config' }
    ]
  },
  {
    key: 'tables',
    title: '表管理',
    items: [
      { label: '智能体定义集合', icon: Monitor, path: '/tables/agent-definitions' },
      { label: '技能定义集合', icon: Monitor, path: '/tables/skill-definitions' },
      { label: '技能版本集合', icon: Monitor, path: '/tables/skill-versions' },
      { label: 'Agent 发布集合', icon: Histogram, path: '/tables/agent-releases' },
      { label: '发布指针集合', icon: Histogram, path: '/tables/agent-release-pointers' },
      { label: '任务运行集合', icon: Coin, path: '/tables/task-runs' },
      { label: '任务事件集合', icon: Coin, path: '/tables/task-events' },
      { label: '任务产物集合', icon: ArrowDown, path: '/tables/task-artifacts' }
    ]
  }
]

const activePath = computed(() => route.path)
const activeGroup = computed(() => {
  const group = menuGroups.find((currentGroup) =>
    currentGroup.items.some((item) => item.path === route.path)
  )
  return group?.key ? [group.key] : ['core']
})

watch(
  isCollapse,
  (value) => {
    localStorage.setItem(COLLAPSE_STORAGE_KEY, value ? '1' : '0')
  },
  { immediate: true }
)

function go(path: string) {
  if (route.path !== path) {
    router.push(path)
  }
}

function toggleCollapse() {
  isCollapse.value = !isCollapse.value
}

function onMenuSelect(index: string) {
  go(index)
}
</script>

<template>
  <div class="admin-shell">
    <aside class="sidebar" :class="{ collapse: isCollapse }">
      <div class="brand" :class="{ compact: isCollapse }">
        <span v-if="!isCollapse">TradingAgents-CN</span>
        <span v-else>TA</span>
      </div>
      <el-scrollbar>
        <el-menu
          class="sidebar-menu"
          :default-active="activePath"
          :default-openeds="activeGroup"
          :collapse="isCollapse"
          :collapse-transition="true"
          unique-opened
          @select="onMenuSelect"
        >
          <el-sub-menu v-for="group in menuGroups" :key="group.key" :index="group.key">
            <template #title>
              <span>{{ group.title }}</span>
            </template>

            <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>{{ item.label }}</template>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>

      <div class="sidebar-toggle" :class="{ compact: isCollapse }">
        <el-button class="collapse-btn" text bg @click="toggleCollapse">
          <el-icon>
            <ArrowRightBold v-if="isCollapse" />
            <ArrowLeftBold v-else />
          </el-icon>
          <span v-if="!isCollapse">收起导航</span>
        </el-button>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <el-button class="topbar-collapse" circle @click="toggleCollapse">
          <el-icon>
            <ArrowRightBold v-if="isCollapse" />
            <ArrowLeftBold v-else />
          </el-icon>
        </el-button>
        <div>
          <h1>交易智能体后台控制台</h1>
          <p>策略、智能体、回测、配置与数据库管理一体化工作台</p>
        </div>
      </header>

      <section class="content-wrap">
        <router-view />
      </section>
    </div>
  </div>
</template>
