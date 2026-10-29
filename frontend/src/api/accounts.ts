import { api } from './client'

/** Money/price values arrive as strings (backend Decimal) — parse only for display/maths. */
export type Dec = string

export type Platform = 'mt5' | 'ctrader' | 'manual'
export type AccountType = 'live' | 'demo' | 'prop'

export interface Account {
  id: string
  name: string
  broker: string
  platform: Platform
  account_type: AccountType
  account_number: string | null
  currency: string
  initial_balance: Dec
  is_active: boolean
  archived_at: string | null
  created_at: string
  /** Reported by a connected broker (EA heartbeat / cTrader); null for manual accounts. */
  last_balance?: Dec | null
  last_equity?: Dec | null
  last_equity_at?: string | null
}

export interface RiskProfileInput {
  risk_per_trade_pct: Dec
  max_daily_loss_pct: Dec
  max_drawdown_pct: Dec
  max_trades_per_day: number
  revenge_cooldown_min: number
  news_blackout_min: number
}

export interface RiskProfile extends RiskProfileInput {
  version: number
  updated_at: string
}

export interface AccountInput {
  name: string
  broker: string
  platform: Platform
  account_type: AccountType
  account_number?: string | null
  currency: string
  initial_balance: Dec
  risk_profile?: RiskProfileInput
}

export interface Usage {
  used: Dec
  limit: Dec
}

export interface RiskStatus {
  currency: string
  balance: Dec
  equity: Dec
  daily_loss: Usage
  drawdown_pct: Usage
  trades_today: Usage
}

export type RuleCode = 'no_trading_window' | 'max_lot_vs_plan' | 'max_consecutive_losses' | 'custom'
export type Severity = 'low' | 'medium' | 'high'
export type RuleParams =
  | { days: number[]; after: string }
  | { ratio: Dec }
  | { n: number }
  | { text: string }

export interface Rule {
  id: string
  code: RuleCode
  params: Record<string, unknown>
  severity: Severity
  is_active: boolean
  created_by: 'trader' | 'mentor'
  created_at: string
}

export interface SymbolOverride {
  id: string
  broker_symbol: string
  symbol_id: string
  symbol_code: string
  contract_size: Dec | null
  tick_value: Dec | null
}

export interface AuditEntry {
  id: string
  action: 'create' | 'update' | 'archive' | 'unarchive' | 'delete'
  entity: string
  entity_id: string
  actor_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  created_at: string
}

export interface SymbolSpec {
  id: string
  code: string
  asset_class: 'fx' | 'metal'
  digits: number
  point_size: Dec
  pip_size: Dec
  contract_size: Dec
  base_currency: string
  quote_currency: string
}

/** F-02 AC2 defaults — mirrors backend RISK_DEFAULTS (shown before an account exists). */
export const RISK_DEFAULTS: RiskProfileInput = {
  risk_per_trade_pct: '1.0',
  max_daily_loss_pct: '3.0',
  max_drawdown_pct: '10.0',
  max_trades_per_day: 5,
  revenge_cooldown_min: 30,
  news_blackout_min: 15,
}

const acc = (id: string) => `/accounts/${id}`

export const accountsApi = {
  list: (includeArchived = false) => api<Account[]>(`/accounts${includeArchived ? '?include_archived=true' : ''}`),
  create: (body: AccountInput) => api<Account>('/accounts', { method: 'POST', body }),
  update: (id: string, body: Partial<AccountInput>) => api<Account>(acc(id), { method: 'PATCH', body }),
  archive: (id: string) => api<Account>(`${acc(id)}/archive`, { method: 'POST' }),
  unarchive: (id: string) => api<Account>(`${acc(id)}/unarchive`, { method: 'POST' }),

  riskProfile: (id: string) => api<RiskProfile>(`${acc(id)}/risk-profile`),
  saveRiskProfile: (id: string, body: RiskProfileInput) => api<RiskProfile>(`${acc(id)}/risk-profile`, { method: 'PUT', body }),
  riskStatus: (id: string) => api<RiskStatus>(`${acc(id)}/risk-status`),

  rules: (id: string) => api<Rule[]>(`${acc(id)}/rules`),
  createRule: (id: string, body: { code: RuleCode; params: RuleParams; severity: Severity }) =>
    api<Rule>(`${acc(id)}/rules`, { method: 'POST', body }),
  updateRule: (id: string, ruleId: string, body: Partial<Pick<Rule, 'is_active' | 'severity'>> & { params?: RuleParams }) =>
    api<Rule>(`${acc(id)}/rules/${ruleId}`, { method: 'PATCH', body }),
  deleteRule: (id: string, ruleId: string) => api<void>(`${acc(id)}/rules/${ruleId}`, { method: 'DELETE' }),

  overrides: (id: string) => api<SymbolOverride[]>(`${acc(id)}/symbol-overrides`),
  saveOverride: (id: string, body: { broker_symbol: string; symbol_id: string; contract_size?: Dec | null; tick_value?: Dec | null }) =>
    api<SymbolOverride>(`${acc(id)}/symbol-overrides`, { method: 'PUT', body }),
  deleteOverride: (id: string, overrideId: string) => api<void>(`${acc(id)}/symbol-overrides/${overrideId}`, { method: 'DELETE' }),

  auditLog: (id: string) => api<AuditEntry[]>(`${acc(id)}/audit-log`),
  symbols: () => api<SymbolSpec[]>('/symbols'),
}
