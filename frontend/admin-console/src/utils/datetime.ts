const DISPLAY_LOCALE = 'zh-CN'

export function formatDateTime(value: string | null | undefined, fallback = '暂无'): string {
  if (!value) {
    return fallback
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return fallback
  }
  return new Intl.DateTimeFormat(DISPLAY_LOCALE, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatRelativeTime(value: string | null | undefined, fallback = '未同步'): string {
  if (!value) {
    return fallback
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return fallback
  }
  const deltaSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (deltaSeconds < 60) {
    return `${deltaSeconds}s 前`
  }
  if (deltaSeconds < 3600) {
    return `${Math.floor(deltaSeconds / 60)}m 前`
  }
  if (deltaSeconds < 86400) {
    return `${Math.floor(deltaSeconds / 3600)}h 前`
  }
  return `${Math.floor(deltaSeconds / 86400)}d 前`
}