import { api, withQuery } from './client'
import type { Dec, RiskStatus } from './accounts'
import type { SessionName, Timeframe } from './playbook'
import type { PlanBrief } from './plans'

// Mirrors backend/app/modules/analysis/schemas.py (F-05, F-19 AC3) and today/router.py.

export type Bias = 'bull' | 'bear' | 'range'
export type LevelKind = 'support' | 'resistance' | 'zone' | 'liquidity' | 'other'
export const BIASES: Bias[] = ['bull', 'bear', 'range']
export const LEVEL_KINDS: LevelKind[] = ['support', 'resistance', 'zone', 'liquidity', 'other']

/** Tiptap / ProseMirror JSON document. */
export interface RichDoc {
  type: 'doc'
  content?: unknown[]
}
export const EMPTY_DOC: RichDoc = { type: 'doc', content: [] }

export interface KeyLevelInput {
  price: Dec
  /** A zone: price … price_to (the server orders them). */
  price_to?: Dec | null
  kind: LevelKind
  label: string
}
export interface KeyLevel {
  price: Dec
  price_to: Dec | null
  kind: LevelKind
  label: string
}

export interface AnalysisSummary {
  id: string
  account_id: string | null
  symbol_id: string
  symbol_code: string
  analysis_date: string
  htf_bias: Bias
  key_levels: KeyLevel[]
  timeframes: Timeframe[]
  session: SessionName | null
  confidence: number
  /** Plain text of the narrative (first 600 chars). */
  narrative_text: string
  plan_count: number
  updated_at: string
}

export interface Analysis extends AnalysisSummary {
  narrative: RichDoc
  created_at: string
  plans: PlanBrief[]
}

export interface AnalysisCreate {
  account_id?: string | null
  symbol_id: string
  /** Today in the user's timezone when omitted. */
  analysis_date?: string | null
  htf_bias: Bias
  key_levels?: KeyLevelInput[]
  timeframes?: Timeframe[]
  session?: SessionName | null
  narrative?: RichDoc
  confidence?: number
}
export type AnalysisUpdate = Partial<AnalysisCreate>

// ------------------------------------------------------------------ chart drawings

export type DrawingTool = 'trendline' | 'ray' | 'horizontal' | 'rectangle' | 'text' | 'measure'
export const DRAWING_TOOLS: DrawingTool[] = ['trendline', 'ray', 'horizontal', 'rectangle', 'text', 'measure']
/** Points each tool needs (backend POINTS_PER_TOOL). */
export const POINTS_PER_TOOL: Record<DrawingTool, 1 | 2> = {
  trendline: 2,
  ray: 2,
  horizontal: 1,
  rectangle: 2,
  text: 1,
  measure: 2,
}
export type DrawingOwner = 'analysis' | 'plan'
/** Token names, never raw colours (both themes). */
export type DrawingColor = 'brand' | 'plan' | 'profit' | 'loss' | 'warning' | 'ink'

export interface ChartPoint {
  /** Unix seconds (bar time). */
  time: number
  price: Dec
}
export interface DrawingStyle {
  color: DrawingColor
  line: 'solid' | 'dashed' | 'dotted'
  width: number
}
export interface Drawing {
  id: string
  tool: DrawingTool
  /** Timeframe it was drawn on; drawings show on every timeframe. */
  timeframe: Timeframe
  points: ChartPoint[]
  style: DrawingStyle
  text: string
}
export type DrawingInput = Omit<Drawing, 'id' | 'style' | 'text'> & { id?: string; style?: Partial<DrawingStyle>; text?: string }

// ------------------------------------------------------------------ market data

export interface Bar {
  time: number
  open: Dec
  high: Dec
  low: Dec
  close: Dec
  volume: number
}
export interface Ohlc {
  symbol_id: string
  symbol_code: string
  timeframe: Timeframe
  digits: number
  /** "mock" until broker OHLC arrives with sync (Phase 4). */
  source: 'mock' | 'mt5' | 'ctrader'
  bars: Bar[]
}

// ------------------------------------------------------------------ today / daily

export interface AccountRisk extends RiskStatus {
  account_id: string
  name: string
}
export interface PnlToday {
  currency: string
  amount: Dec
  r: Dec
  trades: number
}
export interface Daily {
  date: string
  mood: number | null
  tags: string[]
  note: string
  logged_at: string | null
}
export interface Today {
  date: string
  timezone: string
  analyses: AnalysisSummary[]
  plans: PlanBrief[]
  risk: AccountRisk[]
  /** Empty until trades exist (Phase 4). */
  pnl: PnlToday[]
  /** Phase 6. */
  adherence_week: Dec | null
  /** Mentor goal, Phase 8. */
  goal_adherence: Dec | null
  todo: { pending_match: number; pending_review: number; inbox: number }
  daily: Daily | null
}

export const analysisApi = {
  list: (q: { date?: string; symbol_id?: string; account_id?: string; limit?: number } = {}) =>
    api<AnalysisSummary[]>(withQuery('/analyses', q)),
  get: (id: string) => api<Analysis>(`/analyses/${id}`),
  create: (body: AnalysisCreate) => api<Analysis>('/analyses', { method: 'POST', body }),
  /** 409 `analysis_has_plans` when changing the symbol of an analysis that has plans. */
  update: (id: string, body: AnalysisUpdate) => api<Analysis>(`/analyses/${id}`, { method: 'PATCH', body }),
  remove: (id: string) => api<void>(`/analyses/${id}`, { method: 'DELETE' }),
}

export const drawingsApi = {
  list: (owner_type: DrawingOwner, owner_id: string) =>
    api<Drawing[]>(withQuery('/chart-drawings', { owner_type, owner_id })),
  /** Replaces the owner's whole set (the editor saves its state). Max 200. */
  save: (owner_type: DrawingOwner, owner_id: string, drawings: DrawingInput[]) =>
    api<Drawing[]>(withQuery('/chart-drawings', { owner_type, owner_id }), { method: 'PUT', body: { drawings } }),
}

export const marketDataApi = {
  ohlc: (q: { symbol_id: string; tf: Timeframe; to?: number; count?: number }) =>
    api<Ohlc>(withQuery('/market-data/ohlc', q)),
}

export const todayApi = {
  get: (q: { date?: string; account_id?: string } = {}) => api<Today>(withQuery('/today', q)),
  getDaily: (date: string) => api<Daily>(`/daily/${date}`),
  putDaily: (date: string, body: { mood?: number | null; tags?: string[]; note?: string }) =>
    api<Daily>(`/daily/${date}`, { method: 'PUT', body }),
}
