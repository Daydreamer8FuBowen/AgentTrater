import { httpRequest } from './http'

export interface SourceCapabilityPayload {
  capability: string
  markets: string[]
  intervals: string[]
}

export interface DataSourcePayload {
  name: string
  capabilities: SourceCapabilityPayload[]
}

export interface RoutePriorityPayload {
  route_id: string
  capability: string
  market: string | null
  interval: string | null
  supported_sources: string[]
  priorities: string[]
  enabled: boolean
}

export interface DataSourceRoutesOverviewPayload {
  sources: DataSourcePayload[]
  routes: RoutePriorityPayload[]
}

export async function fetchDataSourceRoutesOverview() {
  return httpRequest<DataSourceRoutesOverviewPayload>('/api/v1/data-sources/routes')
}

export async function updateRoutePriorities(
  routeId: string,
  payload: {
    priorities: string[]
    enabled?: boolean
  }
) {
  return httpRequest<RoutePriorityPayload>(`/api/v1/data-sources/routes/${encodeURIComponent(routeId)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
}
