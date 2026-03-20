<script setup lang="ts">
import { ref } from 'vue'

const editMode = ref<'visual' | 'code'>('code')
const strategyName = ref('多因子趋势策略')
const code = ref(`def strategy(context):
    signal = context.features['momentum_20']
    risk = context.features['volatility_10']
    if signal > 0.8 and risk < 0.3:
        return {'action': 'buy', 'weight': 0.2}
    return {'action': 'hold'}`)

const params = ref({
  symbolPool: '沪深300',
  rebalanceCycle: '1d',
  maxPosition: '20%',
  stopLoss: '-4%',
  maxDrawdown: '12%'
})
</script>

<template>
  <div class="module-panel">
    <div class="module-header">
      <div>
        <h2>策略编辑</h2>
        <p>支持可视化/代码双模式，参数配置与实时校验提示。</p>
      </div>
      <el-segmented v-model="editMode" :options="[{ label: '代码编辑', value: 'code' }, { label: '可视化拖拽', value: 'visual' }]" />
    </div>

    <div class="split-grid">
      <el-card>
        <template #header>
          <div class="card-title-with-icon"><span>策略逻辑编辑器</span></div>
        </template>
        <el-form label-width="88px">
          <el-form-item label="策略名称">
            <el-input v-model="strategyName" />
          </el-form-item>
        </el-form>

        <el-alert title="语法检查通过。可直接进行回测。" type="success" :closable="false" />

        <el-input
          v-if="editMode === 'code'"
          v-model="code"
          type="textarea"
          :rows="16"
          class="code-editor"
        />

        <div v-else class="visual-placeholder">
          <p>可视化拖拽面板（演示）</p>
          <p>信号节点 -> 过滤节点 -> 下单节点</p>
        </div>
      </el-card>

      <el-card>
        <template #header>
          <span>参数配置</span>
        </template>
        <el-form label-width="110px">
          <el-form-item label="股票池">
            <el-input v-model="params.symbolPool" />
          </el-form-item>
          <el-form-item label="调仓周期">
            <el-input v-model="params.rebalanceCycle" />
          </el-form-item>
          <el-form-item label="最大仓位">
            <el-input v-model="params.maxPosition" />
          </el-form-item>
          <el-form-item label="止损阈值">
            <el-input v-model="params.stopLoss" />
          </el-form-item>
          <el-form-item label="最大回撤">
            <el-input v-model="params.maxDrawdown" />
          </el-form-item>
        </el-form>

        <el-divider />
        <h4>模板库</h4>
        <el-space wrap>
          <el-tag>动量突破模板</el-tag>
          <el-tag>均值回归模板</el-tag>
          <el-tag>多因子打分模板</el-tag>
        </el-space>

        <el-divider />
        <h4>历史版本</h4>
        <el-timeline>
          <el-timeline-item timestamp="2026-03-20 14:12">v1.3 调整止损阈值</el-timeline-item>
          <el-timeline-item timestamp="2026-03-18 11:43">v1.2 新增波动率过滤</el-timeline-item>
          <el-timeline-item timestamp="2026-03-16 09:08">v1.1 初版发布</el-timeline-item>
        </el-timeline>
      </el-card>
    </div>

    <el-card>
      <div class="footer-actions">
        <el-button type="primary">保存策略</el-button>
        <el-button type="success">发布策略</el-button>
        <el-button>快速回测</el-button>
      </div>
    </el-card>
  </div>
</template>
