import { API_BASE, getAccessToken, refreshAccessToken } from './client'

/** Server → client message on `WS /api/v1/ws` (PLAN §5.2). */
export interface WsMessage {
  type: string
  data?: unknown
  ts?: string
}

type Listener = (msg: WsMessage) => void

const PING_MS = 25_000
const MAX_BACKOFF_MS = 30_000
const UNAUTHORIZED = 4401

/**
 * Realtime client: connects with the current access token, pings every 25s, reconnects with exponential backoff.
 * On an auth close (4401) it refreshes the access token first.
 */
export function createRealtime() {
  let socket: WebSocket | null = null
  let ping: ReturnType<typeof setInterval> | undefined
  let retry: ReturnType<typeof setTimeout> | undefined
  let attempt = 0
  let wanted = false
  const listeners = new Set<Listener>()

  function url(token: string) {
    const base = new URL(API_BASE, window.location.href)
    base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
    base.pathname = `${base.pathname.replace(/\/$/, '')}/ws`
    base.search = `?token=${encodeURIComponent(token)}`
    return base.toString()
  }

  function schedule() {
    if (!wanted) return
    const delay = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempt++)
    retry = setTimeout(open, delay)
  }

  function open() {
    const token = getAccessToken()
    if (!wanted || !token) return
    socket = new WebSocket(url(token))
    socket.onopen = () => {
      attempt = 0
      ping = setInterval(() => socket?.send(JSON.stringify({ type: 'ping' })), PING_MS)
    }
    socket.onmessage = (e) => {
      try {
        const msg = JSON.parse(String(e.data)) as WsMessage
        listeners.forEach((l) => l(msg))
      } catch {
        /* ignore malformed frames */
      }
    }
    socket.onclose = async (e) => {
      clearInterval(ping)
      socket = null
      if (e.code === UNAUTHORIZED && !(await refreshAccessToken())) return
      schedule()
    }
  }

  return {
    connect() {
      wanted = true
      if (!socket) open()
    },
    disconnect() {
      wanted = false
      clearTimeout(retry)
      clearInterval(ping)
      socket?.close(1000)
      socket = null
    },
    on(listener: Listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

export const realtime = createRealtime()
