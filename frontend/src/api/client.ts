/**
 * Fetch wrapper for the FastAPI backend (`/api/v1`).
 * - Access token lives in memory only; the refresh token is an httpOnly cookie scoped to `/api/v1/auth`.
 * - A 401 triggers one (single-flight) refresh and a single retry; if refresh fails the session handler logs out.
 * - Errors are normalised to `ApiError {status, code, message, details}` from the backend's `{code, message, details}`.
 */
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null
let onAuthLost: () => void = () => {}

export const getAccessToken = () => accessToken
export function setAccessToken(token: string | null) {
  accessToken = token
}
/** Called when the session can't be refreshed any more (expired / revoked / reused refresh token). */
export function onSessionLost(handler: () => void) {
  onAuthLost = handler
}

async function toError(res: Response): Promise<ApiError> {
  let body: { code?: string; message?: string; details?: unknown } = {}
  try {
    body = await res.json()
  } catch {
    /* non-JSON error (proxy, network) */
  }
  return new ApiError(res.status, body.code ?? `http_${res.status}`, body.message ?? res.statusText, body.details ?? null)
}

/** POST /auth/refresh with the cookie. Concurrent callers share one request. Resolves false on failure. */
export function refreshAccessToken(): Promise<boolean> {
  refreshing ??= fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'same-origin' })
    .then(async (res) => {
      if (!res.ok) return false
      const data = (await res.json()) as { access_token: string }
      setAccessToken(data.access_token)
      return true
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  /** Send the bearer token and refresh on 401 (default true). */
  auth?: boolean
  signal?: AbortSignal
}

export async function api<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const { method = 'GET', body, auth = true, signal } = opts
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
    signal,
  })

  if (res.status === 401 && auth && !retried) {
    if (await refreshAccessToken()) return api<T>(path, opts, true)
    setAccessToken(null)
    onAuthLost()
  }
  if (!res.ok) throw await toError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
