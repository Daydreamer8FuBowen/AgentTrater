export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }

export interface TableMetadata {
  name: string
  primary_key: string
  columns: string[]
  searchable_columns: string[]
  json_columns: string[]
}

export interface TableRowsResponse {
  table: string
  page: number
  page_size: number
  total: number
  items: Record<string, JsonValue>[]
}
