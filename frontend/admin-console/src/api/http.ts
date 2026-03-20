export interface ApiError extends Error {
  status?: number
}

export async function httpRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const message = await response.text()
    const error = new Error(message || `Request failed: ${response.status}`) as ApiError
    error.status = response.status
    throw error
  }
  return response.json() as Promise<T>
}
