import type { Direction } from '@/api/plans'
import type { ExecutionInput, ManualPositionInput, Side } from '@/api/positions'

// Manual trade form (F-07) — pure helpers: form model ↔ ManualPositionInput, validation,
// and wall-clock time in the trader's timezone ↔ ISO-8601. P/L itself always comes from the API.

/** One execution row as typed. `local` = `YYYY-MM-DDTHH:mm` in the trader's timezone. */
export interface ExecRow {
  key: string
  side: Side
  lot: string
  price: string
  local: string
  /** Cost as a positive number (sent negative, broker style). */
  commission: string
  /** Signed, as the broker reports it. */
  swap: string
}

/** '' = decide later (match queue) · 'none' = unplanned · otherwise a plan id. */
export type PlanChoice = string
export const PLAN_LATER = ''
export const PLAN_NONE = 'none'

export interface TradeForm {
  accountId: string
  symbolId: string
  direction: Direction
  sl: string
  tp: string
  /** Quote → account rate, only asked for after `conversion_rate_required`. */
  rate: string
  executions: ExecRow[]
  plan: PlanChoice
}

export type FormErrorKey = 'account' | 'symbol' | 'executions' | 'sl' | 'tp' | 'rate' | 'execution'
export type ExecErrorKey = 'lot' | 'price' | 'local' | 'commission' | 'swap'

let seq = 0
export const newKey = () => `x${Date.now().toString(36)}${(seq++).toString(36)}`

/** `"4,402.10"` → 4402.1; empty / junk → null. */
export function parseNum(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  const s = String(value).replace(/,/g, '').trim()
  if (!s || !/^[-+]?\d*\.?\d+$/.test(s)) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

/** Decimal string as the API wants it (no thousands separators). */
export const clean = (value: string) => value.replace(/,/g, '').trim().replace(/^\+/, '')

function decimals(value: string): number {
  const s = clean(value)
  const i = s.indexOf('.')
  return i === -1 ? 0 : s.length - i - 1
}

/* ── Timezone ─────────────────────────────────────────────── */

const LOCAL_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/

/** Offset (ms) of `tz` from UTC at the instant `utcMs`. */
export function tzOffsetMs(tz: string, utcMs: number): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(new Date(utcMs))
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value)
  const asUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  return asUtc - Math.floor(utcMs / 1000) * 1000
}

/** `2026-10-09T13:20` in `tz` → `2026-10-09T06:20:00.000Z`. */
export function localToIso(local: string, tz: string): string | null {
  const m = LOCAL_RE.exec(local)
  if (!m) return null
  const wall = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5])
  let utc = wall - tzOffsetMs(tz, wall)
  utc = wall - tzOffsetMs(tz, utc) // second pass for DST edges
  return new Date(utc).toISOString()
}

/** ISO instant → `YYYY-MM-DDTHH:mm` on the wall clock of `tz`. */
export function isoToLocal(iso: string | Date, tz: string): string {
  const ms = typeof iso === 'string' ? Date.parse(iso) : iso.getTime()
  const d = new Date(ms + tzOffsetMs(tz, ms))
  return d.toISOString().slice(0, 16)
}

export const nowLocal = (tz: string, at: Date = new Date()) => isoToLocal(at, tz)

/* ── Executions ───────────────────────────────────────────── */

export function emptyExecution(side: Side, local: string): ExecRow {
  return { key: newKey(), side, lot: '', price: '', local, commission: '', swap: '' }
}

/** Time order; at the same minute an entry comes before an exit (as the backend sorts). */
export function sortExecutions(rows: ExecRow[]): ExecRow[] {
  return [...rows].sort((a, b) => (a.local === b.local ? (a.side === b.side ? 0 : a.side === 'in' ? -1 : 1) : a.local < b.local ? -1 : 1))
}

/** Caption per row: 2nd+ entry = scale-in, an exit that leaves lots open = partial. */
export function captions(rows: ExecRow[]): Record<string, 'scaleIn' | 'partial' | null> {
  const out: Record<string, 'scaleIn' | 'partial' | null> = {}
  let entries = 0
  let open = 0
  for (const r of sortExecutions(rows)) {
    const lot = parseNum(r.lot) ?? 0
    if (r.side === 'in') {
      entries += 1
      open += lot
      out[r.key] = entries > 1 ? 'scaleIn' : null
    } else {
      open -= lot
      out[r.key] = open > 1e-9 ? 'partial' : null
    }
  }
  return out
}

export function validateExecution(r: ExecRow): Partial<Record<ExecErrorKey, string>> {
  const e: Partial<Record<ExecErrorKey, string>> = {}
  const lot = parseNum(r.lot)
  if (lot === null || lot <= 0) e.lot = 'positive'
  else if (decimals(r.lot) > 2) e.lot = 'lotStep'
  const price = parseNum(r.price)
  if (price === null || price <= 0) e.price = 'positive'
  else if (decimals(r.price) > 6) e.price = 'tooPrecise'
  if (!LOCAL_RE.test(r.local)) e.local = 'required'
  const c = r.commission.trim()
  if (c && (parseNum(c) === null || (parseNum(c) ?? 0) < 0)) e.commission = 'cost'
  if (r.swap.trim() && parseNum(r.swap) === null) e.swap = 'number'
  return e
}

/* ── Form ─────────────────────────────────────────────────── */

export function emptyForm(opts: { accountId?: string | null; symbolId?: string | null; local: string }): TradeForm {
  return {
    accountId: opts.accountId ?? '',
    symbolId: opts.symbolId ?? '',
    direction: 'long',
    sl: '',
    tp: '',
    rate: '',
    // One entry to start from, stamped "now" — the trader fills lot + price.
    executions: [emptyExecution('in', opts.local)],
    plan: PLAN_LATER,
  }
}

/** A row still missing its lot or price (shown as "fill in" in the list). */
export const isBlank = (r: ExecRow) => !r.lot.trim() || !r.price.trim()

const optionalPrice = (v: string) => {
  if (!v.trim()) return true
  const n = parseNum(v)
  return n !== null && n > 0
}

export function validateForm(f: TradeForm): Partial<Record<FormErrorKey, string>> {
  const e: Partial<Record<FormErrorKey, string>> = {}
  if (!f.accountId) e.account = 'required'
  if (!f.symbolId) e.symbol = 'required'
  if (!f.executions.some((r) => r.side === 'in')) e.executions = 'needEntry'
  if (f.executions.some((r) => Object.keys(validateExecution(r)).length)) e.execution = 'invalid'
  if (!optionalPrice(f.sl)) e.sl = 'positive'
  if (!optionalPrice(f.tp)) e.tp = 'positive'
  if (f.rate.trim() && !optionalPrice(f.rate)) e.rate = 'positive'
  return e
}

export const isValid = (f: TradeForm) => Object.keys(validateForm(f)).length === 0

function money(v: string, negate: boolean): string | undefined {
  const s = clean(v)
  if (!s || parseNum(s) === 0) return undefined
  return negate ? (s.startsWith('-') ? s.slice(1) : `-${s}`) : s
}

/** API body, or null while the form is incomplete. */
export function toInput(f: TradeForm, tz: string): ManualPositionInput | null {
  if (!isValid(f)) return null
  const executions: ExecutionInput[] = []
  for (const r of sortExecutions(f.executions)) {
    const iso = localToIso(r.local, tz)
    if (!iso) return null
    const row: ExecutionInput = { side: r.side, lot: clean(r.lot), price: clean(r.price), executed_at: iso }
    const commission = money(r.commission, true)
    const swap = money(r.swap, false)
    if (commission) row.commission = commission
    if (swap) row.swap = swap
    executions.push(row)
  }
  const body: ManualPositionInput = {
    account_id: f.accountId,
    symbol_id: f.symbolId,
    direction: f.direction,
    initial_sl: f.sl.trim() ? clean(f.sl) : null,
    initial_tp: f.tp.trim() ? clean(f.tp) : null,
    executions,
  }
  if (f.rate.trim()) body.quote_to_account_rate = clean(f.rate)
  if (f.plan === PLAN_NONE) body.unplanned = true
  else if (f.plan) body.plan_id = f.plan
  return body
}

/** The first entry (time order) — what plan options and matching are based on. */
export function firstEntry(f: TradeForm, tz: string): { opened_at: string; entry_price: string } | null {
  const first = sortExecutions(f.executions).find((r) => r.side === 'in')
  if (!first) return null
  const iso = localToIso(first.local, tz)
  const price = parseNum(first.price)
  if (!iso || price === null || price <= 0) return null
  return { opened_at: iso, entry_price: clean(first.price) }
}

/* ── Display ──────────────────────────────────────────────── */

/** Fixed decimals with separators: `4,388.00`. */
export function fmtFixed(value: string | number, digits: number): string {
  const n = typeof value === 'number' ? value : (parseNum(value) ?? 0)
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n)
}

/** `9 ต.ค. 13:20` from a wall-clock local string (already in the trader's timezone). */
export function localLabel(local: string, intlTag: string): string {
  const m = LOCAL_RE.exec(local)
  if (!m) return local
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]))
  const date = new Intl.DateTimeFormat(intlTag, { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(d)
  return `${date} ${m[4]}:${m[5]}`
}

/** `HH:mm` of an instant in `tz`. */
export const timeIn = (iso: string, tz: string) => isoToLocal(iso, tz).slice(11, 16)

/** API error codes with their own message (else the generic one). */
export const KNOWN_ERRORS = [
  'exit_before_entry',
  'exit_exceeds_open',
  'stop_loss_wrong_side',
  'conversion_rate_required',
  'invalid_execution',
  'no_executions',
  'plan_mismatch',
  'account_archived',
  'validation_error',
  'not_found',
] as const

export function errorKey(code: string | undefined): string {
  return code && (KNOWN_ERRORS as readonly string[]).includes(code) ? `tradeNew.errors.${code}` : 'tradeNew.errors.generic'
}
