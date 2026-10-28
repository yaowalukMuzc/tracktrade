import { ApiError } from '@/api/client'
import {
  MAX_UPLOAD_MB,
  SESSIONS,
  TIMEFRAMES,
  UPLOAD_TYPES,
  type ChecklistInput,
  type ManagementRules,
  type SessionName,
  type Setup,
  type SetupInput,
  type SetupStats,
  type SetupSummary,
  type Timeframe,
} from '@/api/playbook'
import { formatR } from '@/lib/format'

/** Shown for every stat the backend can't compute yet (F-04 AC3 lands in Phase 7) — never a fake number. */
export const DASH = '—'
export const MAX_CHECKLIST = 30
export const MAX_EXAMPLES = 12
export const NAME_MAX = 100
export const DESCRIPTION_MAX = 2000
export const ITEM_MAX = 200
export const METHOD_MAX = 100

type Translate = (key: string, named?: Record<string, unknown>) => string

/* ── Display ─────────────────────────────────────────────── */

const num = (v: string | number, min = 0) =>
  new Intl.NumberFormat('en-US', { minimumFractionDigits: min, maximumFractionDigits: 2 }).format(Number(v))

/** `1%`, `0.75%` (cards, chips) or `1.0%` (management rules, `min = 1`). */
export const riskLabel = (pct: string | number, min = 0) => `${num(pct, min)}%`

export const sessionLabel = (t: Translate, s: SessionName | string) => t(`playbook.sessions.${s}`)

/** "M15 · H1 · London · 1%" — the one-line summary under a setup name. */
export function setupMeta(t: Translate, s: Pick<SetupSummary, 'timeframes' | 'sessions' | 'default_risk_pct'>) {
  return [...s.timeframes, ...s.sessions.map((x) => sessionLabel(t, x)), riskLabel(s.default_risk_pct)].join(' · ')
}

export function partialLabel(t: Translate, r: ManagementRules['partial']) {
  return r ? t('playbook.rules.partialValue', { pct: num(r.pct), r: num(r.at_r) }) : t('playbook.rules.off')
}
export function breakEvenLabel(t: Translate, r: ManagementRules['break_even']) {
  return r ? t('playbook.rules.breakEvenValue', { r: num(r.at_r) }) : t('playbook.rules.off')
}
export function trailingLabel(t: Translate, r: ManagementRules['trailing']) {
  return r ? r.method : t('playbook.rules.off')
}

export interface StatView {
  trades: string
  winRate: string
  expectancy: string
  /** P/L direction of the expectancy — the only stat that may be colored. */
  expDir: 'up' | 'down' | null
  adherence: string
  quality: string
  grade: string
}

/** Stats are 0–100 percentages and R multiples; any missing value renders as "—". */
export function statView(s: SetupStats): StatView {
  const has = (v: string | null): v is string => v !== null && v !== undefined
  const exp = has(s.expectancy_r) ? Number(s.expectancy_r) : null
  return {
    trades: s.trades > 0 ? String(s.trades) : DASH,
    winRate: has(s.win_rate) ? `${num(s.win_rate)}%` : DASH,
    expectancy: exp === null ? DASH : formatR(exp, 2),
    expDir: exp === null || exp === 0 ? null : exp > 0 ? 'up' : 'down',
    adherence: has(s.avg_adherence) ? `${num(Math.round(Number(s.avg_adherence)))}%` : DASH,
    quality: s.avg_quality_grade && has(s.avg_quality) ? `${s.avg_quality_grade} · ${Math.round(Number(s.avg_quality))}` : DASH,
    grade: s.avg_quality_grade ?? DASH,
  }
}

/* ── Checklist editing ───────────────────────────────────── */

/** Editable checklist row; `key` is stable across edits (the server `id` when it has one). */
export interface EditItem {
  key: string
  id?: string
  text: string
  is_required: boolean
}

let seq = 0
export const newKey = () => `new-${++seq}`

export const toEditItems = (items: Setup['checklist']): EditItem[] => items.map((i) => ({ key: i.id, id: i.id, text: i.text, is_required: i.is_required }))

/** PUT body — keeps existing ids so answers in plans keep pointing at them. */
export const toChecklistInput = (items: EditItem[]): ChecklistInput[] =>
  items.map((i) => ({ ...(i.id ? { id: i.id } : {}), text: i.text.trim(), is_required: i.is_required }))

export function moveItem<T>(list: T[], from: number, to: number): T[] {
  if (from === to || to < 0 || to >= list.length) return list
  const next = [...list]
  const [it] = next.splice(from, 1)
  next.splice(to, 0, it)
  return next
}

/* ── Create / edit form ──────────────────────────────────── */

export interface SetupFormModel {
  name: string
  description: string
  timeframes: Timeframe[]
  sessions: SessionName[]
  risk: string
  partialOn: boolean
  partialPct: string
  partialAt: string
  beOn: boolean
  beAt: string
  trailOn: boolean
  trailMethod: string
  checklist: EditItem[]
}

export type FormField = 'name' | 'description' | 'risk' | 'partialPct' | 'partialAt' | 'beAt' | 'trailMethod' | 'checklist'
export type FormErrors = Partial<Record<FormField, string>>

export function emptyForm(): SetupFormModel {
  return {
    name: '',
    description: '',
    timeframes: [],
    sessions: [],
    risk: '1',
    partialOn: false,
    partialPct: '50',
    partialAt: '1.5',
    beOn: false,
    beAt: '1',
    trailOn: false,
    trailMethod: '',
    checklist: [],
  }
}

export function formFromSetup(s: Setup): SetupFormModel {
  const r = s.management_rules
  return {
    name: s.name,
    description: s.description,
    timeframes: [...s.timeframes],
    sessions: [...s.sessions],
    risk: num(s.default_risk_pct).replace(/,/g, ''),
    partialOn: !!r.partial,
    partialPct: r.partial ? num(r.partial.pct).replace(/,/g, '') : '50',
    partialAt: r.partial ? num(r.partial.at_r).replace(/,/g, '') : '1.5',
    beOn: !!r.break_even,
    beAt: r.break_even ? num(r.break_even.at_r).replace(/,/g, '') : '1',
    trailOn: !!r.trailing,
    trailMethod: r.trailing?.method ?? '',
    checklist: toEditItems(s.checklist),
  }
}

const DECIMAL = /^\d+(\.\d{1,2})?$/

/** Range check mirroring the backend's Decimal fields (gt 0, le/lt max, 2 decimals). Returns an i18n key or null. */
function decimalError(raw: string, max: number, inclusive: boolean, rangeKey: string): string | null {
  const v = raw.trim()
  if (!DECIMAL.test(v)) return 'playbook.errors.decimals'
  const n = Number(v)
  if (n <= 0 || (inclusive ? n > max : n >= max)) return rangeKey
  return null
}

/** Client-side mirror of `SetupCreate` / `SetupUpdate` (backend/app/modules/playbook/schemas.py). Values are i18n keys. */
export function validateForm(m: SetupFormModel, withChecklist: boolean): FormErrors {
  const e: FormErrors = {}
  const name = m.name.trim()
  if (!name) e.name = 'playbook.errors.nameRequired'
  else if (name.length > NAME_MAX) e.name = 'playbook.errors.nameLong'
  if (m.description.length > DESCRIPTION_MAX) e.description = 'playbook.errors.tooLong'
  const risk = decimalError(m.risk, 10, true, 'playbook.errors.riskRange')
  if (risk) e.risk = risk
  if (m.partialOn) {
    const pct = decimalError(m.partialPct, 100, false, 'playbook.errors.pctRange')
    if (pct) e.partialPct = pct
    const at = decimalError(m.partialAt, 20, true, 'playbook.errors.rRange')
    if (at) e.partialAt = at
  }
  if (m.beOn) {
    const at = decimalError(m.beAt, 20, true, 'playbook.errors.rRange')
    if (at) e.beAt = at
  }
  if (m.trailOn) {
    const method = m.trailMethod.trim()
    if (!method) e.trailMethod = 'playbook.errors.methodRequired'
    else if (method.length > METHOD_MAX) e.trailMethod = 'playbook.errors.tooLong'
  }
  if (withChecklist) {
    if (m.checklist.length > MAX_CHECKLIST) e.checklist = 'playbook.checklist.max'
    else if (m.checklist.some((i) => !i.text.trim())) e.checklist = 'playbook.errors.itemRequired'
    else if (m.checklist.some((i) => i.text.trim().length > ITEM_MAX)) e.checklist = 'playbook.errors.tooLong'
  }
  return e
}

/** Max length / count passed to the error message for each field. */
export const ERROR_PARAMS: Record<FormField, Record<string, number>> = {
  name: { n: NAME_MAX },
  description: { n: DESCRIPTION_MAX },
  risk: {},
  partialPct: {},
  partialAt: {},
  beAt: {},
  trailMethod: { n: METHOD_MAX },
  checklist: { n: MAX_CHECKLIST },
}

export function formToInput(m: SetupFormModel, withChecklist: boolean): SetupInput {
  const body: SetupInput = {
    name: m.name.trim(),
    description: m.description.trim(),
    timeframes: TIMEFRAMES.filter((x) => m.timeframes.includes(x)),
    sessions: SESSIONS.filter((x) => m.sessions.includes(x)),
    default_risk_pct: m.risk.trim(),
    management_rules: {
      partial: m.partialOn ? { pct: m.partialPct.trim(), at_r: m.partialAt.trim() } : null,
      break_even: m.beOn ? { at_r: m.beAt.trim() } : null,
      trailing: m.trailOn ? { method: m.trailMethod.trim() } : null,
    },
  }
  if (withChecklist) body.checklist = m.checklist.map((i) => ({ text: i.text.trim(), is_required: i.is_required }))
  return body
}

/* ── Errors ──────────────────────────────────────────────── */

/** FastAPI `validation_error` details → form field (loc is `['body', ...path]`). */
export function apiFieldErrors(e: unknown): FormErrors {
  if (!(e instanceof ApiError) || e.code !== 'validation_error' || !Array.isArray(e.details)) return {}
  const out: FormErrors = {}
  for (const d of e.details as { loc?: unknown[] }[]) {
    const path = (d.loc ?? []).filter((p) => p !== 'body').join('.')
    const field: FormField | undefined = path.startsWith('name')
      ? 'name'
      : path.startsWith('description')
        ? 'description'
        : path.startsWith('default_risk_pct')
          ? 'risk'
          : path.startsWith('management_rules.partial.pct')
            ? 'partialPct'
            : path.startsWith('management_rules.partial')
              ? 'partialAt'
              : path.startsWith('management_rules.break_even')
                ? 'beAt'
                : path.startsWith('management_rules.trailing')
                  ? 'trailMethod'
                  : path.startsWith('checklist')
                    ? 'checklist'
                    : undefined
    if (field && !out[field]) out[field] = 'playbook.errors.invalid'
  }
  return out
}

/** Any playbook API failure → `playbook.errors.*` key (+ params). */
export function errorKey(e: unknown): [string, Record<string, unknown>?] {
  if (!(e instanceof ApiError)) return ['playbook.errors.network']
  switch (e.code) {
    case 'file_too_large':
      return ['playbook.errors.fileSize', { mb: MAX_UPLOAD_MB }]
    case 'unsupported_file_type':
      return ['playbook.errors.fileType']
    case 'too_many_examples':
      return ['playbook.errors.tooManyExamples', { max: MAX_EXAMPLES }]
    case 'attachment_in_use':
      return ['playbook.errors.attachmentInUse']
    case 'validation_error':
      return ['playbook.errors.validation']
  }
  if (e.status === 0) return ['playbook.errors.network']
  if (e.status === 404) return ['playbook.errors.notFound']
  if (e.status === 413) return ['playbook.errors.fileSize', { mb: MAX_UPLOAD_MB }]
  if (e.status === 415) return ['playbook.errors.fileType']
  if (e.status === 429) return ['playbook.errors.rateLimited']
  return ['playbook.errors.generic']
}

/** Client-side image check before upload (server re-checks the bytes). */
export function fileError(file: File): [string, Record<string, unknown>?] | null {
  if (!UPLOAD_TYPES.includes(file.type)) return ['playbook.errors.fileType']
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return ['playbook.errors.fileSize', { mb: MAX_UPLOAD_MB }]
  return null
}
