import { createRouter, createWebHistory } from 'vue-router'

import AdminLayout from '../components/layout/AdminLayout.vue'
import AgentManagementPage from '../pages/AgentManagementPage.vue'
import BacktestAnalysisPage from '../pages/BacktestAnalysisPage.vue'
import DashboardPage from '../pages/DashboardPage.vue'
import DataSourceRoutingPage from '../pages/DataSourceRoutingPage.vue'
import SymbolDetailPage from '../pages/SymbolDetailPage.vue'
import SymbolListPage from '../pages/SymbolListPage.vue'
import StrategyEditorPage from '../pages/StrategyEditorPage.vue'
import SystemConfigPage from '../pages/SystemConfigPage.vue'
import AgentDefinitionsTablePage from '../pages/tables/AgentDefinitionsTablePage.vue'
import AgentSkillDefinitionsTablePage from '../pages/tables/AgentSkillDefinitionsTablePage.vue'
import AgentSkillVersionsTablePage from '../pages/tables/AgentSkillVersionsTablePage.vue'
import AgentTaskAnswersTablePage from '../pages/tables/AgentTaskAnswersTablePage.vue'
import AgentTaskRunStepsTablePage from '../pages/tables/AgentTaskRunStepsTablePage.vue'
import AgentTaskRunsTablePage from '../pages/tables/AgentTaskRunsTablePage.vue'
import OpportunitiesTablePage from '../pages/tables/OpportunitiesTablePage.vue'
import ResearchTasksTablePage from '../pages/tables/ResearchTasksTablePage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AdminLayout,
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: DashboardPage },
        { path: 'data-sources', component: DataSourceRoutingPage },
        { path: 'symbols', component: SymbolListPage },
        { path: 'symbols/:symbol', component: SymbolDetailPage },
        { path: 'agents', component: AgentManagementPage },
        { path: 'strategy-editor', component: StrategyEditorPage },
        { path: 'backtest-analysis', component: BacktestAnalysisPage },
        { path: 'system-config', component: SystemConfigPage },
        { path: 'tables/agent-definitions', component: AgentDefinitionsTablePage },
        { path: 'tables/skill-definitions', component: AgentSkillDefinitionsTablePage },
        { path: 'tables/skill-versions', component: AgentSkillVersionsTablePage },
        { path: 'tables/agent-releases', component: OpportunitiesTablePage },
        { path: 'tables/agent-release-pointers', component: ResearchTasksTablePage },
        { path: 'tables/task-runs', component: AgentTaskRunsTablePage },
        { path: 'tables/task-events', component: AgentTaskRunStepsTablePage },
        { path: 'tables/task-artifacts', component: AgentTaskAnswersTablePage }
      ]
    }
  ]
})

export default router
