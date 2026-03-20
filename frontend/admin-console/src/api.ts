import type { TableMetadata, TableRowsResponse } from './types'

function buildQuery(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  const search = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))
  return search.toString() ? `?${search.toString()}` : ''
}

export async function fetchTables(): Promise<TableMetadata[]> {
  const response = await fetch('/api/v1/admin/tables')
  if (!response.ok) {
    throw new Error(`加载表列表失败: ${response.status}`)
  }
  return response.json() as Promise<TableMetadata[]>
}

export async function fetchRows(args: {
  tableName: string
  page: number
  pageSize: number
  keyword?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  filters?: Record<string, string>
}): Promise<TableRowsResponse> {
  const { tableName, page, pageSize, keyword, sortBy, sortOrder, filters } = args
  const query = buildQuery({
    page,
    page_size: pageSize,
    keyword,
    sort_by: sortBy,
    sort_order: sortOrder,
    filters: filters && Object.keys(filters).length > 0 ? JSON.stringify(filters) : undefined
  })
  const response = await fetch(`/api/v1/admin/tables/${tableName}/rows${query}`)
  if (!response.ok) {
    throw new Error(`加载数据失败: ${response.status}`)
  }
  return response.json() as Promise<TableRowsResponse>
}

export async function updateRow(tableName: string, rowId: string, updates: Record<string, unknown>) {
  const response = await fetch(`/api/v1/admin/tables/${tableName}/rows/${rowId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ updates })
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`更新失败: ${response.status} ${detail}`)
  }

  return response.json() as Promise<Record<string, unknown>>
}
