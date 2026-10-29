import { API_BASE, ApiError, api, authedFetch } from './client'
import type { Dec } from './accounts'

export type Timeframe = 'M1' | 'M5' | 'M15' | 'M30' | 'H1' | 'H4' | 'D1' | 'W1'
export type SessionName = 'asia' | 'london' | 'new_york'
export const TIMEFRAMES: Timeframe[] = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1']
export const SESSIONS: SessionName[] = ['asia', 'london', 'new_york']

export interface ManagementRules {
  partial: { pct: Dec; at_r: Dec } | null
  break_even: { at_r: Dec } | null
  trailing: { method: string } | null
}

export interface ChecklistItem {
  id: string
  text: string
  is_required: boolean
}

/** F-04 AC3 — null until Phase 7 fills them from trades. */
export interface SetupStats {
  trades: number
  win_rate: Dec | null
  expectancy_r: Dec | null
  avg_adherence: Dec | null
  avg_quality: Dec | null
  avg_quality_grade: 'A' | 'B' | 'C' | 'D' | null
}

export interface SetupSummary {
  id: string
  name: string
  timeframes: Timeframe[]
  sessions: SessionName[]
  default_risk_pct: Dec
  is_archived: boolean
  checklist_count: number
  stats: SetupStats
}

export interface SetupExample {
  id: string
  attachment_id: string
  /** Same-origin API path; needs the bearer token — load with `loadImage`. */
  url: string
  note: string
}

export interface Setup extends SetupSummary {
  description: string
  management_rules: ManagementRules
  checklist: ChecklistItem[]
  examples: SetupExample[]
  created_at: string
  updated_at: string
}

export interface SetupInput {
  name: string
  description?: string
  timeframes?: Timeframe[]
  sessions?: SessionName[]
  default_risk_pct?: Dec
  management_rules?: Partial<ManagementRules>
  checklist?: { text: string; is_required: boolean }[]
}

export interface ChecklistInput {
  id?: string
  text: string
  is_required: boolean
}

export interface Attachment {
  id: string
  content_type: string
  size_bytes: number
  filename: string | null
  url: string
  created_at: string
}

export const MAX_UPLOAD_MB = 10
export const UPLOAD_TYPES = ['image/png', 'image/jpeg', 'image/webp']

const s = (id: string) => `/setups/${id}`

export const playbookApi = {
  list: (archived = false) =>
    api<{ items: SetupSummary[]; counts: { active: number; archived: number } }>(`/setups${archived ? '?archived=true' : ''}`),
  get: (id: string) => api<Setup>(s(id)),
  create: (body: SetupInput) => api<Setup>('/setups', { method: 'POST', body }),
  update: (id: string, body: Omit<SetupInput, 'checklist'>) => api<Setup>(s(id), { method: 'PATCH', body }),
  remove: (id: string) => api<void>(s(id), { method: 'DELETE' }),
  archive: (id: string) => api<Setup>(`${s(id)}/archive`, { method: 'POST' }),
  unarchive: (id: string) => api<Setup>(`${s(id)}/unarchive`, { method: 'POST' }),
  saveChecklist: (id: string, items: ChecklistInput[]) => api<Setup>(`${s(id)}/checklist`, { method: 'PUT', body: items }),
  addExample: (id: string, attachmentId: string, note = '') =>
    api<Setup>(`${s(id)}/examples`, { method: 'POST', body: { attachment_id: attachmentId, note } }),
  removeExample: (id: string, exampleId: string) => api<Setup>(`${s(id)}/examples/${exampleId}`, { method: 'DELETE' }),
}

/** Multipart upload (`api()` only sends JSON). Server checks type from the bytes and size ≤ 10 MB. */
export async function uploadAttachment(file: File): Promise<Attachment> {
  const form = new FormData()
  form.append('file', file)
  const res = await authedFetch(`${API_BASE}/attachments`, { method: 'POST', body: form })
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { code?: string; message?: string; details?: unknown }
    throw new ApiError(res.status, body.code ?? `http_${res.status}`, body.message ?? res.statusText, body.details ?? null)
  }
  return (await res.json()) as Attachment
}

/** Attachment URLs need the bearer token, so `<img src>` cannot load them directly: fetch → object URL. */
export async function loadImage(url: string): Promise<string> {
  const res = await authedFetch(url)
  if (!res.ok) throw new ApiError(res.status, `http_${res.status}`, res.statusText)
  return URL.createObjectURL(await res.blob())
}
