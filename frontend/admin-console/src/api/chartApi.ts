import { httpRequest } from './http'

export type ChartResolution = '1' | '3' | '5' | '15' | '30' | '60' | '240' | 'D' | 'W' | 'M'

export interface TradingViewHistoryResponse {
  s: 'ok' | 'no_data' | 'error'
  t?: number[]
  o?: number[]
  h?: number[]
  l?: number[]
  c?: number[]
  v?: number[]
  errmsg?: string
}

export async function fetchChartHistory(params: {
  symbol: string
  resolution: ChartResolution
  from: number
  to: number
  countback?: number
}): Promise<TradingViewHistoryResponse> {
  const search = new URLSearchParams({
    symbol: params.symbol,
    resolution: params.resolution,
    from: String(params.from),
    to: String(params.to),
  })
  if (params.countback !== undefined) {
    search.set('countback', String(params.countback))
  }
  return httpRequest<TradingViewHistoryResponse>(`/api/v1/charts/history?${search.toString()}`)
}
