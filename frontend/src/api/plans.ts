import { api, withQuery } from './client'
import type { Dec } from './accounts'

// Mirrors backend/app/modules/plans/schemas.py (F-06).

export type Direction = 'long' | 'short'
export type EntryType = 'market' | 'limit' | 'stop'
export type PlanStatus = 'draft' | 'locked' | 'triggered' | 'closed' | 'skipped' | 'missed' | 'invalidated' | 'expired'
export type ManualStatus = 'skipped' | 'missed' | 'invalidated'
export const PLAN_STATUSES: PlanStatus[] = ['draft', 'locked', 'triggered', 'closed', 'skipped', 'missed', 'invalidated', 'expired']
/** Which manual status changes are allowed from which state (backend MANUAL_TRANSITIONS). */
export const MANUAL_TRANSITIONS: Record<ManualStatus, PlanStatus[]> = {
  skipped: ['draft', 'locked'],
  invalidated: ['draft', 'locked'],
  missed: ['locked'],
}

export interface TakeProfitInput {
  price: Dec
  pct?: Dec
}
export interface TakeProfit {
  price: Dec
  pct: Dec
  rr: Dec | null
}

export interface ManagementPlan {
  partial: boolean
  break_even: boolean
  trailing: boolean
}

export interface ChecklistAnswerInput {
  checklist_item_id: string
  checked: boolean
  note?: string
}

export interface EmotionInput {
  mood?: number | null
  confidence?: number | null
  tags?: string[]
  note?: string
}
export interface Emotion {
  mood: number | null
  confidence: number | null
  tags: string[]
  note: string
  logged_at: string
}

export interface ChecklistStatus {
  done: number
  total: number
  required_done: number
  required_total: number
  /** Required items not ticked yet. */
  missing: string[]
}

export interface ChecklistItemState {
  id: string
  text: string
  is_required: boolean
  checked: boolean
  note: string
}

export interface CalcMeta {
  balance: Dec
  currency: string
  contract_size: Dec
  value_per_point: Dec
  tick_value_source: 'override' | 'standard'
}

export interface Revision {
  /** null for a preview. */
  id: string | null
  revision_no: number
  snapshot_hash: string
  /** { stop_loss: { from: "4366.78", to: "4360" }, take_profits: { from: [...], to: [...] } } */
  changes: Record<string, { from: unknown; to: unknown }>
  risk_delta_amount: Dec | null
  risk_delta_r: Dec | null
  reason: string | null
  changed_at: string
  changed_after_entry: boolean
}

export interface PlanBrief {
  id: string
  analysis_id: string | null
  account_id: string
  symbol_id: string
  symbol_code: string
  setup_id: string
  setup_name: string
  plan_date: string
  scenario_label: string
  direction: Direction
  entry_type: EntryType
  entry_price: Dec
  stop_loss: Dec
  take_profits: TakeProfit[]
  planned_risk_pct: Dec
  planned_risk_amount: Dec
  planned_lot: Dec
  planned_rr: Dec | null
  status: PlanStatus
  locked_at: string | null
  valid_until: string | null
  checklist: ChecklistStatus
}

export interface Plan extends PlanBrief {
  quote_to_account_rate: Dec | null
  management_plan: ManagementPlan
  invalidation: string
  status_reason: string | null
  status_changed_at: string | null
  /** sha256 of revision 1 (the lock). */
  lock_hash: string | null
  triggered_at: string | null
  current_revision: number
  /** sha256 of the latest revision. */
  current_hash: string | null
  currency: string
  /** Inputs behind the planned numbers; null if they can't be valued (missing FX rate). */
  calc: CalcMeta | null
  /** Live answers while draft; frozen as locked afterwards. */
  checklist_items: ChecklistItemState[]
  pre_emotion: Emotion | null
  revisions: Revision[]
  can_lock: boolean
  created_at: string
  updated_at: string
}

export interface PlanCreate {
  analysis_id?: string | null
  setup_id: string
  account_id: string
  symbol_id: string
  direction: Direction
  scenario_label?: string | null
  entry_type: EntryType
  entry_price: Dec
  stop_loss: Dec
  take_profits: TakeProfitInput[]
  planned_risk_pct: Dec
  quote_to_account_rate?: Dec | null
  management_plan?: ManagementPlan
  invalidation?: string
  /** ISO datetime; end of the plan day (user's timezone) when omitted. */
  valid_until?: string | null
  plan_date?: string | null
  checklist_answers?: ChecklistAnswerInput[]
  pre_emotion?: EmotionInput | null
}

export type PlanUpdate = Partial<Omit<PlanCreate, 'analysis_id' | 'account_id' | 'symbol_id' | 'plan_date' | 'pre_emotion'>>

/** What a revision may change; the checklist stays as locked. */
export interface RevisionChanges {
  entry_type?: EntryType
  entry_price?: Dec
  stop_loss?: Dec
  take_profits?: TakeProfitInput[]
  /** Rejected once the plan is triggered (422 risk_pct_after_entry). */
  planned_risk_pct?: Dec
  management_plan?: ManagementPlan
  invalidation?: string
  valid_until?: string | null
}

export interface PlanListQuery {
  date?: string
  status?: PlanStatus
  analysis_id?: string
  account_id?: string
}

/**
 * Errors worth handling in the UI (ApiError.code):
 * - 422 `checklist_incomplete` → details.missing [{id, text}] (F-06 AC3)
 * - 409 `plan_not_draft` (PATCH/lock/delete after lock), `plan_not_revisable`, `invalid_transition`
 * - 422 `reason_required`, `no_changes`, `risk_pct_after_entry`, `valid_until_passed`,
 *   `stop_loss_wrong_side`, `take_profit_wrong_side`, `conversion_rate_required`,
 *   `setup_archived`, `account_archived`, `symbol_mismatch`, `unknown_emotion_tag`
 */
export const plansApi = {
  list: (q: PlanListQuery = {}) => api<PlanBrief[]>(withQuery('/plans', { ...q })),
  get: (id: string) => api<Plan>(`/plans/${id}`),
  create: (body: PlanCreate) => api<Plan>('/plans', { method: 'POST', body }),
  /** Draft only. */
  update: (id: string, body: PlanUpdate) => api<Plan>(`/plans/${id}`, { method: 'PATCH', body }),
  remove: (id: string) => api<void>(`/plans/${id}`, { method: 'DELETE' }),
  setPreEmotion: (id: string, body: EmotionInput) => api<Plan>(`/plans/${id}/pre-emotion`, { method: 'PUT', body }),
  lock: (id: string) => api<Plan>(`/plans/${id}/lock`, { method: 'POST' }),
  revisions: (id: string) => api<Revision[]>(`/plans/${id}/revisions`),
  /** Risk delta + after-entry flag without saving (revision sheet). */
  previewRevision: (id: string, changes: RevisionChanges) =>
    api<Revision>(`/plans/${id}/revisions/preview`, { method: 'POST', body: { changes } }),
  revise: (id: string, changes: RevisionChanges, reason: string) =>
    api<Revision>(`/plans/${id}/revisions`, { method: 'POST', body: { changes, reason } }),
  setStatus: (id: string, status: ManualStatus, reason: string) =>
    api<Plan>(`/plans/${id}/status`, { method: 'POST', body: { status, reason } }),
}
