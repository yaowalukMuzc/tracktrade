import { ApiError } from '@/api/client'
import type { AnalysisCreate, Bias, Drawing, DrawingInput, KeyLevel, LevelKind, RichDoc } from '@/api/analysis'
import { MAX_UPLOAD_MB, TIMEFRAMES, UPLOAD_TYPES, type SessionName, type Timeframe } from '@/api/playbook'
import { formatNumber } from '@/lib/format'

// Pure helpers of the Market Analysis screen (F-05 AC1–AC2, F-19 AC3–AC4).

/** Timeframe chips of the design (chart switcher and "Timeframes" multi-select). */
export const ANALYSIS_TFS: Timeframe[] = ['M5', 'M15', 'H1', 'H4', 'D1']
/** Backend KeyLevels max_length. */
export const MAX_LEVELS = 30

// ------------------------------------------------------------------ form state

export interface AnalysisForm {
  account_id: string | null
  symbol_id: string
  analysis_date: string
  htf_bias: Bias
  timeframes: Timeframe[]
  session: SessionName | null
  confidence: number
  key_levels: KeyLevel[]
  narrative: RichDoc
}

export const formToBody = (f: AnalysisForm): AnalysisCreate => ({
  account_id: f.account_id,
  symbol_id: f.symbol_id,
  analysis_date: f.analysis_date,
  htf_bias: f.htf_bias,
  timeframes: [...f.timeframes],
  session: f.session,
  confidence: f.confidence,
  key_levels: f.key_levels.map((l) => ({ price: l.price, price_to: l.price_to, kind: l.kind, label: l.label })),
  narrative: f.narrative,
})

/** `YYYY-MM-DD` of a date in the browser's timezone (input[type=date] value). */
export function localToday(d = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export const isIsoDate = (s: unknown): s is string => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s)

/** Toggle a timeframe, keeping the canonical M1 … W1 order. */
export function toggleTimeframe(list: Timeframe[], tf: Timeframe): Timeframe[] {
  const set = new Set(list)
  if (set.has(tf)) set.delete(tf)
  else set.add(tf)
  return TIMEFRAMES.filter((x) => set.has(x))
}

// ------------------------------------------------------------------ key levels

export interface LevelForm {
  kind: LevelKind
  price: string
  priceTo: string
  label: string
}
export type LevelError = 'required' | 'positive' | 'sameAsPrice'
export type LevelErrors = Partial<Record<'price' | 'priceTo', LevelError>>

export const emptyLevelForm = (): LevelForm => ({ kind: 'support', price: '', priceTo: '', label: '' })

/** "4,366.5" → "4366.5"; null when empty; NaN when not a number. */
function parsePrice(s: string): string | null {
  const v = s.replace(/[,\s]/g, '')
  if (!v) return null
  return /^\d*\.?\d+$|^\d+\.$/.test(v) ? v.replace(/\.$/, '') : 'NaN'
}

const isPositive = (v: string) => Number.isFinite(Number(v)) && Number(v) > 0

/** A zone needs both ends; other kinds are a single price. */
export function validateLevel(f: LevelForm): LevelErrors {
  const errors: LevelErrors = {}
  const price = parsePrice(f.price)
  if (price === null) errors.price = 'required'
  else if (!isPositive(price)) errors.price = 'positive'
  if (f.kind === 'zone') {
    const to = parsePrice(f.priceTo)
    if (to === null) errors.priceTo = 'required'
    else if (!isPositive(to)) errors.priceTo = 'positive'
    else if (price !== null && isPositive(price) && Number(to) === Number(price)) errors.priceTo = 'sameAsPrice'
  }
  return errors
}

/** Valid form → key level (zone ends ordered low → high, like the server does). */
export function levelFromForm(f: LevelForm): KeyLevel {
  const price = parsePrice(f.price) as string
  if (f.kind !== 'zone') return { price, price_to: null, kind: f.kind, label: f.label.trim() }
  const to = parsePrice(f.priceTo) as string
  const [lo, hi] = Number(to) < Number(price) ? [to, price] : [price, to]
  return { price: lo, price_to: hi, kind: 'zone', label: f.label.trim() }
}

/** Levels listed by price, low → high (the order of the design). Stable for equal prices. */
export function sortLevels(levels: KeyLevel[]): KeyLevel[] {
  return levels
    .map((l, i) => ({ l, i }))
    .sort((a, b) => Number(a.l.price) - Number(b.l.price) || a.i - b.i)
    .map((x) => x.l)
}

export const addLevel = (levels: KeyLevel[], level: KeyLevel) => sortLevels([...levels, level])

/** `4,366.00` for a line (symbol digits), `4,380 – 4,388` for a zone (no trailing zeros). */
export function formatLevelPrice(l: Pick<KeyLevel, 'price' | 'price_to'>, digits: number): string {
  if (l.price_to === null) {
    return new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(l.price))
  }
  return `${formatNumber(l.price, digits)} – ${formatNumber(l.price_to, digits)}`
}

/** Marker style per kind (screens/source/WAnalysis.dc.html): lines are short bars, zones a box. */
export const LEVEL_MARKER: Record<LevelKind, string> = {
  support: 'h-[3px] bg-warning',
  resistance: 'h-[3px] bg-ink-muted',
  zone: 'h-2.5 border border-brand-500 bg-brand-100',
  liquidity: 'h-[3px] bg-brand-700',
  other: 'h-[3px] bg-ink-subtle',
}

// ------------------------------------------------------------------ drawings / narrative

/** Editor state → PUT body. Text drawings without text are dropped (the server rejects them). */
export function toDrawingInputs(drawings: Drawing[]): DrawingInput[] {
  return drawings
    .filter((d) => d.tool !== 'text' || d.text.trim() !== '')
    .map((d) => ({ id: d.id, tool: d.tool, timeframe: d.timeframe, points: d.points, style: d.style, text: d.text }))
}

/** Anything the API hands back → a Tiptap document. */
export function normalizeDoc(doc: unknown): RichDoc {
  if (doc && typeof doc === 'object' && (doc as RichDoc).type === 'doc') {
    const content = (doc as RichDoc).content
    return { type: 'doc', content: Array.isArray(content) ? content : [] }
  }
  return { type: 'doc', content: [] }
}

/** Client-side check before uploading a narrative image. */
export function imageFileError(file: File): [string, Record<string, unknown>?] | null {
  if (!UPLOAD_TYPES.includes(file.type)) return ['analysis.errors.fileType']
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return ['analysis.errors.fileSize', { mb: MAX_UPLOAD_MB }]
  return null
}

// ------------------------------------------------------------------ errors

export function errorKey(e: unknown): [string, Record<string, unknown>?] {
  if (!(e instanceof ApiError)) return ['analysis.errors.network']
  switch (e.code) {
    case 'analysis_has_plans':
      return ['analysis.errors.hasPlans']
    case 'validation_error':
      return ['analysis.errors.validation']
    case 'file_too_large':
      return ['analysis.errors.fileSize', { mb: MAX_UPLOAD_MB }]
    case 'unsupported_file_type':
      return ['analysis.errors.fileType']
  }
  if (e.status === 0) return ['analysis.errors.network']
  return ['analysis.errors.generic']
}

export const isNotFound = (e: unknown) => e instanceof ApiError && (e.status === 404 || e.status === 422)
