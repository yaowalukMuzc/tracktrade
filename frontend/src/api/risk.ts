import { api } from './client'
import type { Dec } from './accounts'

export interface RiskCalcInput {
  account_id: string
  symbol_id: string
  direction: 'long' | 'short'
  entry: Dec
  stop_loss: Dec
  take_profits?: { price: Dec; pct?: number }[]
  risk_pct?: Dec
  lot?: Dec
  quote_to_account_rate?: Dec
}

export interface RiskCalcResult {
  balance: Dec
  currency: string
  lot: Dec
  risk_amount: Dec
  risk_pct: Dec
  target_risk_amount: Dec | null
  value_per_point: Dec
  sl_points: Dec
  rr_per_tp: Dec[]
  rr_avg: Dec | null
  contract_size: Dec
  tick_value_source: 'override' | 'standard'
}

/** F-03 AC3 / F-06 AC2 — the plan form (Phase 3) uses this. */
export const riskApi = {
  calc: (body: RiskCalcInput) => api<RiskCalcResult>('/risk/calc', { method: 'POST', body }),
}
