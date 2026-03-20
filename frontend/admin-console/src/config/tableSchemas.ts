import type { TableMetadata } from '../types'

export const fallbackTableSchemas: TableMetadata[] = [
  {
    name: 'agent_definitions',
    primary_key: 'agent_id',
    columns: ['agent_id', 'name', 'type', 'status', 'description', 'owner', 'skill_bindings', 'execution_policy', 'model_policy', 'tags', 'metadata', 'created_at', 'updated_at'],
    searchable_columns: ['agent_id', 'name', 'type', 'description', 'status'],
    json_columns: ['skill_bindings', 'execution_policy', 'model_policy', 'tags', 'metadata']
  },
  {
    name: 'skill_definitions',
    primary_key: 'skill_id',
    columns: ['skill_id', 'name', 'category', 'description', 'interfaces', 'tool_policy', 'status', 'created_at', 'updated_at'],
    searchable_columns: ['skill_id', 'name', 'category', 'description', 'status'],
    json_columns: ['interfaces', 'tool_policy']
  },
  {
    name: 'skill_versions',
    primary_key: 'skill_version_id',
    columns: ['skill_version_id', 'skill_id', 'version', 'status', 'change_log', 'prompt_spec', 'input_schema', 'output_schema', 'runtime_policy', 'tool_policy', 'implementation_ref', 'checksum', 'created_by', 'created_at', 'updated_at', 'published_at'],
    searchable_columns: ['skill_version_id', 'skill_id', 'version', 'status', 'created_by', 'change_log'],
    json_columns: ['prompt_spec', 'input_schema', 'output_schema', 'runtime_policy', 'tool_policy', 'implementation_ref']
  },
  {
    name: 'agent_releases',
    primary_key: 'agent_release_id',
    columns: ['agent_release_id', 'agent_id', 'version', 'status', 'graph_spec', 'execution_policy', 'created_by', 'created_at', 'updated_at', 'published_at'],
    searchable_columns: ['agent_release_id', 'agent_id', 'version', 'status'],
    json_columns: ['graph_spec', 'execution_policy']
  },
  {
    name: 'agent_release_pointers',
    primary_key: 'agent_id',
    columns: ['agent_id', 'current_release_id', 'previous_release_id', 'updated_by', 'created_at', 'updated_at'],
    searchable_columns: ['agent_id', 'current_release_id', 'previous_release_id'],
    json_columns: []
  },
  {
    name: 'task_runs',
    primary_key: 'run_id',
    columns: ['run_id', 'task_kind', 'status', 'trigger', 'context', 'agent', 'graph', 'execution', 'metrics', 'result', 'error', 'search_tags', 'created_at', 'updated_at'],
    searchable_columns: ['run_id', 'task_kind', 'status', 'context.symbol', 'trigger.kind', 'agent.agent_id', 'result.summary'],
    json_columns: ['trigger', 'context', 'agent', 'graph', 'execution', 'metrics', 'result', 'error', 'search_tags']
  },
  {
    name: 'task_events',
    primary_key: 'event_id',
    columns: ['event_id', 'run_id', 'seq', 'event_type', 'timestamp', 'node', 'agent', 'skill', 'payload', 'trace'],
    searchable_columns: ['event_id', 'run_id', 'event_type', 'node.node_id', 'skill.skill_version_id'],
    json_columns: ['node', 'agent', 'skill', 'payload', 'trace']
  },
  {
    name: 'task_artifacts',
    primary_key: 'artifact_id',
    columns: ['artifact_id', 'run_id', 'node_id', 'artifact_type', 'content_type', 'content', 'size_bytes', 'created_at'],
    searchable_columns: ['artifact_id', 'run_id', 'node_id', 'artifact_type', 'content_type'],
    json_columns: ['content']
  },
  {
    name: 'news_items',
    primary_key: 'news_id',
    columns: ['news_id', 'title', 'content', 'summary', 'source', 'source_url', 'published_at', 'market', 'industry_tags', 'concept_tags', 'stock_tags', 'tags', 'credibility', 'dedupe_key', 'raw_payload', 'created_at', 'updated_at'],
    searchable_columns: ['news_id', 'source', 'title', 'summary', 'market', 'industry_tags', 'concept_tags', 'stock_tags', 'tags', 'dedupe_key'],
    json_columns: ['industry_tags', 'concept_tags', 'stock_tags', 'tags', 'raw_payload']
  }
]

export const tableRouteConfig: Array<{ tableName: string; title: string; path: string }> = [
  { tableName: 'agent_definitions', title: '智能体定义集合', path: '/tables/agent-definitions' },
  { tableName: 'skill_definitions', title: '技能定义集合', path: '/tables/skill-definitions' },
  { tableName: 'skill_versions', title: '技能版本集合', path: '/tables/skill-versions' },
  { tableName: 'agent_releases', title: 'Agent 发布集合', path: '/tables/agent-releases' },
  { tableName: 'agent_release_pointers', title: 'Agent 发布指针集合', path: '/tables/agent-release-pointers' },
  { tableName: 'task_runs', title: '任务运行集合', path: '/tables/task-runs' },
  { tableName: 'task_events', title: '任务事件集合', path: '/tables/task-events' },
  { tableName: 'task_artifacts', title: '任务产物集合', path: '/tables/task-artifacts' },
  { tableName: 'news_items', title: '新闻集合', path: '/tables/news-items' }
]
