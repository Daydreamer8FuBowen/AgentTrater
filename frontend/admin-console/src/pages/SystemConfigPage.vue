<script setup lang="ts">
import { ElMessageBox } from 'element-plus'
import { ref } from 'vue'

const activeTab = ref('account')

const account = ref({
  broker: 'CTP-SIM',
  accountId: 'sim_trader_001',
  apiEndpoint: 'https://api.broker.example'
})

const risk = ref({
  maxPositionRatio: 0.25,
  dailyLossLimit: 0.06,
  singleOrderLimit: 0.05
})

const notify = ref({
  webhook: 'https://hooks.example/agenttrader',
  email: 'ops@example.com',
  notifyLevel: 'warning'
})

const system = ref({
  schedulerInterval: 30,
  maxConcurrency: 8,
  cacheTtlSeconds: 120
})

const configLogs = [
  '2026-03-20 12:30 管理员更新了 dailyLossLimit: 0.05 -> 0.06',
  '2026-03-19 18:22 管理员更新了 notifyLevel: error -> warning',
  '2026-03-18 09:05 管理员更新了 maxConcurrency: 6 -> 8'
]

async function saveConfig() {
  await ElMessageBox.confirm('配置即将生效，是否确认保存？', '二次确认', {
    confirmButtonText: '确认保存',
    cancelButtonText: '取消',
    type: 'warning'
  })
}
</script>

<template>
  <div class="module-panel">
    <div class="module-header">
      <div>
        <h2>系统配置</h2>
        <p>按标签页管理账户、风控、通知和系统参数，支持二次确认与变更日志。</p>
      </div>
      <el-tag type="info">当前角色：管理员</el-tag>
    </div>

    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane name="account" label="账户配置">
          <el-form label-width="140px" class="config-form">
            <el-form-item label="券商通道">
              <el-input v-model="account.broker" />
            </el-form-item>
            <el-form-item label="账户ID">
              <el-input v-model="account.accountId" />
            </el-form-item>
            <el-form-item label="API地址">
              <el-input v-model="account.apiEndpoint" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane name="risk" label="风控规则">
          <el-form label-width="140px" class="config-form">
            <el-form-item label="最大仓位占比">
              <el-input-number v-model="risk.maxPositionRatio" :step="0.01" :min="0.01" :max="1" />
            </el-form-item>
            <el-form-item label="日内亏损上限">
              <el-input-number v-model="risk.dailyLossLimit" :step="0.01" :min="0.01" :max="0.5" />
            </el-form-item>
            <el-form-item label="单笔下单上限">
              <el-input-number v-model="risk.singleOrderLimit" :step="0.01" :min="0.01" :max="0.5" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane name="notify" label="通知设置">
          <el-form label-width="140px" class="config-form">
            <el-form-item label="Webhook">
              <el-input v-model="notify.webhook" />
            </el-form-item>
            <el-form-item label="邮箱告警">
              <el-input v-model="notify.email" />
            </el-form-item>
            <el-form-item label="通知级别">
              <el-select v-model="notify.notifyLevel">
                <el-option label="warning" value="warning" />
                <el-option label="error" value="error" />
                <el-option label="critical" value="critical" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane name="system" label="系统参数">
          <el-form label-width="140px" class="config-form">
            <el-form-item label="调度间隔(秒)">
              <el-input-number v-model="system.schedulerInterval" :min="5" :max="300" />
            </el-form-item>
            <el-form-item label="最大并发数">
              <el-input-number v-model="system.maxConcurrency" :min="1" :max="64" />
            </el-form-item>
            <el-form-item label="缓存TTL(秒)">
              <el-input-number v-model="system.cacheTtlSeconds" :min="10" :max="600" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="footer-actions">
        <el-button type="primary" @click="saveConfig">保存配置</el-button>
      </div>
    </el-card>

    <el-card>
      <template #header>
        <span>配置变更日志</span>
      </template>
      <el-timeline>
        <el-timeline-item v-for="line in configLogs" :key="line" :timestamp="line.slice(0, 16)">
          {{ line.slice(17) }}
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>
