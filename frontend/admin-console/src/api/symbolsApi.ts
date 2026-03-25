import { httpRequest } from './http'

export interface SymbolMonitorItem {
  symbol: string
  name: string | null
  market: string | null
  status: string | null
  security_type: string | null
  industry: string | null
  area: string | null
  updated_at: string | null
  d1_completion_ratio: number
  d1_progress_status: string
  latest_bar_time: string | null
  sync_status: string
  latest_interval: string | null
  lag_seconds: number
}

export interface SymbolMonitorResponse {
  total: number
  page: number
  page_size: number
  items: SymbolMonitorItem[]
}

export interface SymbolDetailResponse {
  symbol: string
  basic_info: Record<string, unknown>
  sync_market: string | null
  sync_states: Array<Record<string, unknown>>
  d1_progress: Record<string, unknown> | null
}

function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  })
  return search.toString()
}

export async function fetchSymbolMonitor(params: {
  keyword?: string
  market?: string
  status?: string
  security_type?: string
  page: number
  page_size: number
}): Promise<SymbolMonitorResponse> {
  const query = buildQuery(params)
  return httpRequest<SymbolMonitorResponse>(`/api/v1/symbols/monitor?${query}`)
}

export async function fetchSymbolDetail(symbol: string): Promise<SymbolDetailResponse> {
  return httpRequest<SymbolDetailResponse>(`/api/v1/symbols/${encodeURIComponent(symbol)}`)
}
