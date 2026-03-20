import type { TableMetadata, TableRowsResponse } from '../types'
import { httpRequest } from './http'

function buildQuery(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== '')
  const search = new URLSearchParams(entries.map(([key, value]) => [key, String(value)]))
  return search.toString() ? `?${search.toString()}` : ''
}

export async function fetchManageableTables(): Promise<TableMetadata[]> {
  return httpRequest<TableMetadata[]>('/api/v1/admin/tables')
}

export async function fetchTableRows(args: {
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
  return httpRequest<TableRowsResponse>(`/api/v1/admin/tables/${tableName}/rows${query}`)
}

export async function updateTableRow(tableName: string, rowId: string, updates: Record<string, unknown>) {
  return httpRequest<Record<string, unknown>>(`/api/v1/admin/tables/${tableName}/rows/${rowId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ updates })
  })
}
