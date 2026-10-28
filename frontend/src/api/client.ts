/**
 * Fetch wrapper for the FastAPI backend (`/api/v1`).
 * - The bearer token is a 15-minute JWT from Better Auth (`GET /api/auth/token`, authorised by the httpOnly
 *   session cookie). It lives in memory only.
 * - A 401 fetches a new JWT once (single-flight) and retries once; if that fails the session is gone
 *   (signed out, revoked, password reset) and the session handler sends the user to /login.
 * - Errors are normalised to `ApiError {status, code, message, details}` from the backend's `{code, message, details}`.
 */
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'
export const AUTH_BASE = '/api/auth'

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
/** Called when no JWT can be obtained any more (session expired / signed out / revoked). */
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

/** GET /api/auth/token with the session cookie. Concurrent callers share one request. Resolves false on failure. */
export function refreshAccessToken(): Promise<boolean> {
  refreshing ??= fetch(`${AUTH_BASE}/token`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    .then(async (res) => {
      if (!res.ok) return false
      const data = (await res.json()) as { token?: string }
      if (!data.token) return false
      setAccessToken(data.token)
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
