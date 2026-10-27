export class ApiError extends Error {
  status: number
  code: string
  details: Record<string, unknown>
  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const e = body?.error ?? {}
    throw new ApiError(res.status, e.code ?? 'http_error', e.message ?? res.statusText, e.details ?? {})
  }
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>)
}

async function requestText(path: string): Promise<string> {
  const res = await fetch(path)
  if (!res.ok) throw new ApiError(res.status, 'http_error', res.statusText)
  return res.text()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  text: (path: string) => requestText(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }),
  postRaw: <T>(path: string, body: BodyInit, contentType: string) =>
    request<T>(path, { method: 'POST', headers: { 'content-type': contentType }, body }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form }),
}

/** Base URL of one published output version; the route takes the bare number (`/outputs/3/...`). */
export const outputsBase = (projectId: string, version: number | null) => `/api/projects/${projectId}/outputs/${version}`
