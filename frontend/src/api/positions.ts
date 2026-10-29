import { api, downloadFile, withQuery } from './client'
import type { Dec } from './accounts'
import type { Direction } from './plans'

// Mirrors backend/app/modules/positions/schemas.py (F-07, F-10).

export type Source = 'manual' | 'mt5' | 'ctrader' | 'ocr'
export type Side = 'in' | 'out'
export type TradeTab = 'all' | 'review' | 'pending' | 'unplanned' | 'open'
export type MatchStatus = 'auto' | 'manual' | 'pending'
/** Why a trade counts as unplanned (F-07 AC3). */
export type UnplannedReason = 'no_plan' | 'plan_not_locked' | 'locked_after_entry'
export const TRADE_TABS: TradeTab[] = ['all', 'review', 'pending', 'unplanned', 'open']

export interface PlanRef {
  id: string
  scenario_label: string
  setup_id: string
  setup_name: string
  status: string
  entry_type: 'market' | 'limit' | 'stop'
  entry_price: Dec
  stop_loss: Dec
  locked_at: string | null
}

export interface PositionSummary {
  id: string
  ref_no: number
  account_id: string
  account_name: string
  currency: string
  symbol_id: string
  symbol_code: string
  digits: number
  direction: Direction
  source: Source
  status: 'open' | 'closed'
  opened_at: string
  closed_at: string | null
  avg_entry: Dec
  avg_exit: Dec | null
  total_lot: Dec
  open_lot: Dec
  net_pnl: Dec
  r_multiple: Dec | null
  current_sl: Dec | null
  current_tp: Dec | null
  is_unplanned: boolean
  match_status: MatchStatus
  plan: PlanRef | null
  /** Phase 5–6: null until the engines exist ("—"). */
  adherence_pct: Dec | null
  quality_grade: string | null
  quadrant: string | null
  review_status: 'pending' | 'done' | null
}

export interface TabCounts {
  all: number
  review: number
  pending: number
  unplanned: number
  open: number
}

export interface PositionList {
  items: PositionSummary[]
  total: number
  offset: number
  limit: number
  counts: TabCounts
}

export interface Execution {
  id: string
  side: Side
  lot: Dec
  price: Dec
  executed_at: string
  commission: Dec
  swap: Dec
  profit: Dec | null
  broker_deal_id: string | null
}

export interface Modification {
  id: string
  field: 'sl' | 'tp'
  old_value: Dec | null
  new_value: Dec | null
  modified_at: string
  direction_of_risk: 'increase' | 'decrease' | 'neutral'
}

export interface Position extends PositionSummary {
  broker_position_id: string | null
  broker_symbol: string | null
  initial_sl: Dec | null
  initial_tp: Dec | null
  gross_pnl: Dec
  commission: Dec
  swap: Dec
  initial_risk_amount: Dec | null
  mae: Dec | null
  mfe: Dec | null
  mae_r: Dec | null
  mfe_r: Dec | null
  unplanned_reason: UnplannedReason | null
  matched_at: string | null
  match_meta: Record<string, unknown>
  risk_profile_version: number | null
  executions: Execution[]
  modifications: Modification[]
}

export interface ExecutionInput {
  side: Side
  lot: Dec
  price: Dec
  /** ISO-8601 with a timezone. */
  executed_at: string
  /** Signed like the broker: a cost is negative. */
  commission?: Dec
  swap?: Dec
}

export interface ManualPositionInput {
  account_id: string
  symbol_id: string
  direction: Direction
  initial_sl?: Dec | null
  initial_tp?: Dec | null
  executions: ExecutionInput[]
  /** Link this plan, or `unplanned: true`, or neither → the matching engine decides. */
  plan_id?: string | null
  unplanned?: boolean
  quote_to_account_rate?: Dec | null
}

export interface PositionCalc {
  status: 'open' | 'closed'
  avg_entry: Dec
  avg_exit: Dec | null
  total_lot: Dec
  open_lot: Dec
  gross_pnl: Dec
  commission: Dec
  swap: Dec
  net_pnl: Dec
  initial_risk_amount: Dec | null
  r_multiple: Dec | null
  currency: string
  unplanned_reason: UnplannedReason | null
}

export interface MatchCandidate {
  plan: PlanRef
  distance: Dec
  /** Distance as % of the plan's SL distance, e.g. "0.4". */
  pct_of_sl: Dec
  within_price: boolean
  within_time: boolean
  eligible: boolean
  recommended: boolean
}

export interface MatchQueueItem {
  position: PositionSummary
  first_entry: Dec
  candidates: MatchCandidate[]
}

export interface TradeFilters {
  tab?: TradeTab
  account_id?: string
  symbol_id?: string
  setup_id?: string
  direction?: Direction
  /** YYYY-MM-DD in the trader's timezone. */
  from?: string
  to?: string
  q?: string
}

const P = '/positions'
type Query = Record<string, string | number | undefined>

export const positionsApi = {
  list: (f: TradeFilters, offset = 0, limit = 20) => api<PositionList>(withQuery(P, { ...(f as Query), offset, limit })),
  get: (id: string) => api<Position>(`${P}/${id}`),
  create: (body: ManualPositionInput) => api<Position>(P, { method: 'POST', body }),
  preview: (body: ManualPositionInput, signal?: AbortSignal) => api<PositionCalc>(`${P}/preview`, { method: 'POST', body, signal }),
  remove: (id: string) => api<void>(`${P}/${id}`, { method: 'DELETE' }),
  planOptions: (q: { account_id: string; symbol_id: string; direction: Direction; opened_at: string; entry_price: string }) =>
    api<MatchCandidate[]>(withQuery(`${P}/plan-options`, q)),
  matchQueue: (accountId?: string) => api<MatchQueueItem[]>(withQuery(`${P}/match-queue`, { account_id: accountId })),
  candidates: (id: string) => api<MatchCandidate[]>(`${P}/${id}/match-candidates`),
  /** `null` = record as unplanned. */
  match: (id: string, planId: string | null) => api<Position>(`${P}/${id}/match`, { method: 'PUT', body: { plan_id: planId } }),
  exportCsv: (f: TradeFilters) => downloadFile(withQuery(`${P}/export.csv`, f as Query), 'tracktrade-trades.csv'),
}
