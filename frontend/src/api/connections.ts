import { api, downloadFile, withQuery } from './client'

// Mirrors backend/app/modules/connections/schemas.py (F-08).

export type ConnectionKind = 'mt5_ea' | 'ctrader_oauth'
/** pending = waiting for the EA / first sync; offline = EA silent for 2 min. */
export type ConnectionStatus = 'pending' | 'connected' | 'offline' | 'error'

export interface Connection {
  id: string
  account_id: string
  kind: ConnectionKind
  status: ConnectionStatus
  /** "tt_live_9f2c••••••••a71b" — the full key is only returned when created. */
  key_hint: string | null
  external_account_id: string | null
  server: string | null
  ea_version: string | null
  last_seen_at: string | null
  last_sync_at: string | null
  last_error: string | null
  last_error_at: string | null
  history_synced_at: string | null
  stats: { deals_today: number; mods_today: number; history_days: number | null }
  created_at: string
}

export interface ApiKeyResult {
  connection: Connection
  api_key: string
}

export interface IngestionJob {
  id: string
  kind: 'sync' | 'history' | 'resync' | 'manual' | 'ocr'
  source: 'mt5' | 'ctrader' | 'manual' | 'ocr'
  status: 'running' | 'success' | 'warning' | 'error'
  stats: {
    deals?: number
    positions?: number
    new_positions?: number
    modifications?: number
    bars?: number
    duplicates?: number
    unknown_symbols?: string[]
    code?: string
  }
  error: string | null
  attempts: number
  started_at: string
  finished_at: string | null
}

const acc = (id: string) => `/accounts/${id}`

export const connectionsApi = {
  list: (accountId: string) => api<Connection[]>(`${acc(accountId)}/connections`),
  /** Creates or rotates the EA key; the response is the only time the full key is visible. */
  createMt5Key: (accountId: string) => api<ApiKeyResult>(`${acc(accountId)}/connections/mt5`, { method: 'POST' }),
  ctraderAuthorize: (accountId: string) =>
    api<{ authorize_url: string }>(`${acc(accountId)}/connections/ctrader/authorize`, { method: 'POST' }),
  sync: (connectionId: string) => api<Connection>(`/connections/${connectionId}/sync`, { method: 'POST' }),
  disconnect: (connectionId: string) => api<void>(`/connections/${connectionId}`, { method: 'DELETE' }),
  jobs: (accountId: string, limit = 20) => api<IngestionJob[]>(withQuery(`${acc(accountId)}/ingestion-jobs`, { limit })),
  downloadEa: () => downloadFile('/downloads/mt5-ea', 'TrackTrade-MT5-EA.zip'),
}
