import type {
  ChecklistItemState,
  Direction,
  EmotionInput,
  EntryType,
  ManagementPlan,
  Plan,
  PlanCreate,
  PlanUpdate,
  Revision,
  RevisionChanges,
} from '@/api/plans'
import type { RiskCalcInput } from '@/api/risk'
import type { ManagementRules } from '@/api/playbook'

// Pure logic of the plan form (F-06): model ↔ API payloads, client-side validation (AC1), revision diffs (AC4).

export const MAX_TPS = 5
/** RiskPct on the backend: 0 < x ≤ 10. */
export const MAX_RISK_PCT = 10
export const SCENARIO_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export interface TpRow {
  price: string
  pct: string
}

export interface PlanFormModel {
  setupId: string
  direction: Direction
  entryType: EntryType
  scenario: string
  invalidation: string
  /** `datetime-local` value (browser time zone); '' = server default (end of the plan day). */
  validUntil: string
  entry: string
  stopLoss: string
  tps: TpRow[]
  riskPct: string
  management: ManagementPlan
  /** checklist item id → ticked */
  checklist: Record<string, boolean>
}

export interface EmotionModel {
  mood: number | null
  confidence: number | null
  tags: string[]
}

/** "4,387.52" → 4387.52; '' / garbage → null. */
export function parseNum(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined) return null
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  const s = v.replace(/[,\s]/g, '').replace('−', '-')
  if (s === '' || !/^-?\d*\.?\d+$|^-?\d+\.$/.test(s)) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

/** Decimal string for the API (no separators, no float noise). */
export function dec(v: string | number): string {
  const n = parseNum(v)
  if (n === null) return ''
  return String(Number(n.toFixed(8)))
}

/** Fixed-digit price with separators: 4387.52 → "4,387.52". */
export function formatPrice(v: string | number | null | undefined, digits: number): string {
  const n = parseNum(v ?? null)
  if (n === null) return ''
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n)
}

/** Percent share / risk %: "50", "1.5" — at most 2 decimals, no padding. */
export function formatPct(v: string | number | null | undefined): string {
  const n = parseNum(v ?? null)
  if (n === null) return ''
  return String(Number(n.toFixed(2)))
}

/** Risk % in the input: one decimal at least ("1.0", "0.75"). */
export function formatRiskPct(v: string | number | null | undefined): string {
  const n = parseNum(v ?? null)
  if (n === null) return ''
  return n.toFixed(Math.max(1, Math.min(2, (String(Number(n.toFixed(2))).split('.')[1] ?? '').length)))
}

const pad = (n: number) => String(n).padStart(2, '0')

/** ISO → `YYYY-MM-DDTHH:mm` in the browser's time zone (datetime-local). */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** datetime-local → ISO (UTC); '' → null. */
export function fromLocalInput(v: string): string | null {
  if (!v) return null
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

/** Default management toggles: every rule the setup defines is on. */
export function defaultManagement(rules: ManagementRules | null | undefined): ManagementPlan {
  return { partial: !!rules?.partial, break_even: !!rules?.break_even, trailing: !!rules?.trailing }
}

export function emptyModel(opts: { setupId?: string; riskPct?: string; scenario?: string; rules?: ManagementRules | null } = {}): PlanFormModel {
  return {
    setupId: opts.setupId ?? '',
    direction: 'long',
    entryType: 'limit',
    scenario: opts.scenario ?? 'A',
    invalidation: '',
    validUntil: '',
    entry: '',
    stopLoss: '',
    tps: [{ price: '', pct: '100' }],
    riskPct: opts.riskPct ? formatRiskPct(opts.riskPct) : '',
    management: defaultManagement(opts.rules),
    checklist: {},
  }
}

export function fromPlan(plan: Plan, digits: number): PlanFormModel {
  return {
    setupId: plan.setup_id,
    direction: plan.direction,
    entryType: plan.entry_type,
    scenario: plan.scenario_label,
    invalidation: plan.invalidation,
    validUntil: toLocalInput(plan.valid_until),
    entry: formatPrice(plan.entry_price, digits),
    stopLoss: formatPrice(plan.stop_loss, digits),
    tps: plan.take_profits.map((tp) => ({ price: formatPrice(tp.price, digits), pct: formatPct(tp.pct) })),
    riskPct: formatRiskPct(plan.planned_risk_pct),
    management: { ...plan.management_plan },
    checklist: Object.fromEntries(plan.checklist_items.map((c) => [c.id, c.checked])),
  }
}

export function emotionFromPlan(plan: Pick<Plan, 'pre_emotion'>): EmotionModel {
  const e = plan.pre_emotion
  return { mood: e?.mood ?? null, confidence: e?.confidence ?? null, tags: [...(e?.tags ?? [])] }
}

export const emotionInput = (e: EmotionModel): EmotionInput => ({ mood: e.mood, confidence: e.confidence, tags: [...e.tags] })
export const hasEmotion = (e: EmotionModel) => e.mood !== null || e.confidence !== null || e.tags.length > 0

/** Even split of 100% over n take-profits, 2 decimals, the last one takes the rounding rest. */
export function splitShares(n: number): string[] {
  if (n <= 0) return []
  const each = Math.floor((100 / n) * 100) / 100
  const out = Array.from({ length: n }, () => each)
  out[n - 1] = Number((100 - each * (n - 1)).toFixed(2))
  return out.map((x) => String(x))
}

/* ── Validation (F-06 AC1 + level sides) ─────────────────── */

/** field → i18n key under `plans.errors`. TP rows use `tp.<i>`; the share total uses `tpShare`. */
export type FormErrors = Record<string, string>

export function validatePlan(m: PlanFormModel): FormErrors {
  const e: FormErrors = {}
  if (!m.setupId) e.setup = 'required'
  const entry = parseNum(m.entry)
  const sl = parseNum(m.stopLoss)
  if (m.entry.trim() === '') e.entry = 'required'
  else if (entry === null || entry <= 0) e.entry = 'positive'
  if (m.stopLoss.trim() === '') e.stopLoss = 'required'
  else if (sl === null || sl <= 0) e.stopLoss = 'positive'
  const long = m.direction === 'long'
  if (!e.entry && !e.stopLoss && entry !== null && sl !== null && (long ? sl >= entry : sl <= entry)) {
    e.stopLoss = long ? 'slBelowEntry' : 'slAboveEntry'
  }

  const filled = m.tps.map((tp, i) => ({ tp, i })).filter(({ tp }) => tp.price.trim() !== '' || tp.pct.trim() !== '')
  if (!filled.some(({ tp }) => tp.price.trim() !== '')) e.tps = 'tpRequired'
  let total = 0
  for (const { tp, i } of filled) {
    const price = parseNum(tp.price)
    if (tp.price.trim() === '') e[`tp.${i}`] = 'required'
    else if (price === null || price <= 0) e[`tp.${i}`] = 'positive'
    else if (!e.entry && entry !== null && (long ? price <= entry : price >= entry)) e[`tp.${i}`] = long ? 'tpAboveEntry' : 'tpBelowEntry'
    const pct = tp.pct.trim() === '' ? (filled.length === 1 ? 100 : null) : parseNum(tp.pct)
    if (pct === null || pct <= 0 || pct > 100) e[`tpPct.${i}`] = 'share'
    else total += pct
  }
  if (total > 100.0001) e.tpShare = 'tpShareOver'

  const risk = parseNum(m.riskPct)
  if (m.riskPct.trim() === '') e.riskPct = 'required'
  else if (risk === null || risk <= 0 || risk > MAX_RISK_PCT) e.riskPct = 'riskRange'
  return e
}

export const isValid = (e: FormErrors) => Object.keys(e).length === 0

/* ── Payloads ────────────────────────────────────────────── */

function tpPayload(m: PlanFormModel) {
  const rows = m.tps.filter((tp) => tp.price.trim() !== '')
  return rows.map((tp) => ({ price: dec(tp.price), pct: tp.pct.trim() === '' ? '100' : dec(tp.pct) }))
}

export function checklistAnswers(m: PlanFormModel) {
  return Object.entries(m.checklist).map(([checklist_item_id, checked]) => ({ checklist_item_id, checked }))
}

/** Full draft state for PATCH (also the dirty-check snapshot). */
export function toUpdate(m: PlanFormModel): PlanUpdate {
  const body: PlanUpdate = {
    setup_id: m.setupId,
    direction: m.direction,
    scenario_label: m.scenario,
    entry_type: m.entryType,
    entry_price: dec(m.entry),
    stop_loss: dec(m.stopLoss),
    take_profits: tpPayload(m),
    planned_risk_pct: dec(m.riskPct),
    management_plan: { ...m.management },
    invalidation: m.invalidation.trim(),
    checklist_answers: checklistAnswers(m),
  }
  const vu = fromLocalInput(m.validUntil)
  if (vu) body.valid_until = vu
  return body
}

export function toCreate(
  m: PlanFormModel,
  ctx: { analysisId: string | null; accountId: string; symbolId: string; planDate?: string | null },
  emotion?: EmotionModel,
): PlanCreate {
  const { setup_id, direction, ...rest } = toUpdate(m)
  const body: PlanCreate = {
    ...rest,
    setup_id: setup_id!,
    direction: direction!,
    entry_type: m.entryType,
    entry_price: dec(m.entry),
    stop_loss: dec(m.stopLoss),
    take_profits: tpPayload(m),
    planned_risk_pct: dec(m.riskPct),
    analysis_id: ctx.analysisId,
    account_id: ctx.accountId,
    symbol_id: ctx.symbolId,
  }
  if (ctx.planDate) body.plan_date = ctx.planDate
  if (emotion && hasEmotion(emotion)) body.pre_emotion = emotionInput(emotion)
  return body
}

/** Input for the realtime calc box; null until entry / SL / risk % are numbers. */
export function calcInput(m: PlanFormModel, accountId: string | null, symbolId: string | null): RiskCalcInput | null {
  const entry = parseNum(m.entry)
  const sl = parseNum(m.stopLoss)
  const risk = parseNum(m.riskPct)
  if (!accountId || !symbolId || entry === null || sl === null || risk === null || entry <= 0 || sl <= 0 || risk <= 0) return null
  const tps = m.tps
    .map((tp) => ({ price: parseNum(tp.price), pct: tp.pct.trim() === '' ? 100 : parseNum(tp.pct) }))
    .filter((tp): tp is { price: number; pct: number } => tp.price !== null && tp.price > 0 && tp.pct !== null && tp.pct > 0)
  return {
    account_id: accountId,
    symbol_id: symbolId,
    direction: m.direction,
    entry: dec(entry),
    stop_loss: dec(sl),
    take_profits: tps.map((tp) => ({ price: dec(tp.price), pct: tp.pct })),
    risk_pct: dec(risk),
  }
}

/** Required checklist items not ticked (F-06 AC3). */
export function missingRequired(items: Pick<ChecklistItemState, 'id' | 'is_required'>[], answers: Record<string, boolean>): string[] {
  return items.filter((i) => i.is_required && !answers[i.id]).map((i) => i.id)
}

/** Scenario letters for the segmented control: letters already used by sibling plans are left out;
 *  shows the current one + the free ones up to `min` options. */
export function scenarioOptions(usedBySiblings: string[], current: string | null, min = 2): string[] {
  const used = new Set(usedBySiblings.filter((l) => l !== current))
  const out: string[] = []
  for (const l of SCENARIO_LETTERS) {
    if (used.has(l)) continue
    out.push(l)
    if (out.length >= min && (!current || out.includes(current))) break
  }
  return out
}

/** First letter no sibling plan uses (what the server would pick). */
export const nextScenario = (used: string[]) => SCENARIO_LETTERS.find((l) => !used.includes(l)) ?? 'A'

/* ── Revisions (F-06 AC4) ────────────────────────────────── */

export interface RevisionDraft {
  entry: string
  stopLoss: string
  tps: TpRow[]
  riskPct: string
}

export function revisionDraft(plan: Plan, digits: number): RevisionDraft {
  const m = fromPlan(plan, digits)
  return { entry: m.entry, stopLoss: m.stopLoss, tps: m.tps, riskPct: m.riskPct }
}

const same = (a: string | number | null, b: string | number | null) => {
  const x = parseNum(a)
  const y = parseNum(b)
  return x !== null && y !== null && Math.abs(x - y) < 1e-9
}

/** Only what differs from the plan. `triggered` → risk % is not revisable (position size is fixed). */
export function revisionChanges(plan: Plan, d: RevisionDraft, opts: { triggered: boolean }): RevisionChanges {
  const c: RevisionChanges = {}
  if (!same(d.entry, plan.entry_price)) c.entry_price = dec(d.entry)
  if (!same(d.stopLoss, plan.stop_loss)) c.stop_loss = dec(d.stopLoss)
  const tps = d.tps.filter((tp) => tp.price.trim() !== '')
  const tpChanged =
    tps.length !== plan.take_profits.length ||
    tps.some((tp, i) => !same(tp.price, plan.take_profits[i].price) || !same(tp.pct || '100', plan.take_profits[i].pct))
  if (tpChanged) c.take_profits = tps.map((tp) => ({ price: dec(tp.price), pct: tp.pct.trim() === '' ? '100' : dec(tp.pct) }))
  if (!opts.triggered && !same(d.riskPct, plan.planned_risk_pct)) c.planned_risk_pct = dec(d.riskPct)
  return c
}

/** Validates the revision values with the plan's direction. */
export function validateRevision(plan: Plan, d: RevisionDraft): FormErrors {
  const m: PlanFormModel = { ...emptyModel(), setupId: plan.setup_id, direction: plan.direction, entry: d.entry, stopLoss: d.stopLoss, tps: d.tps, riskPct: d.riskPct }
  const e = validatePlan(m)
  delete e.setup
  return e
}

/** One display row per changed field: SL 4,366.78 → 4,360.00. Values are formatted, labels are i18n keys. */
export interface ChangeRow {
  field: string
  from: string
  to: string
}

function fmtValue(field: string, v: unknown, digits: number, fmtTime: (iso: string) => string): string {
  if (v === null || v === undefined || v === '') return '—'
  switch (field) {
    case 'entry_price':
    case 'stop_loss':
      return formatPrice(v as string, digits)
    case 'planned_risk_pct':
      return `${formatPct(v as string)}%`
    case 'take_profits':
      return (v as { price: string; pct: string }[]).map((tp) => `${formatPrice(tp.price, digits)} (${formatPct(tp.pct)}%)`).join(' / ')
    case 'valid_until':
      return fmtTime(String(v))
    case 'management_plan':
      return Object.entries(v as Record<string, boolean>)
        .filter(([, on]) => on)
        .map(([k]) => k)
        .join(', ') || '—'
    default:
      return String(v)
  }
}

export function changeRows(rev: Pick<Revision, 'changes'>, digits: number, fmtTime: (iso: string) => string = (s) => s): ChangeRow[] {
  return Object.entries(rev.changes).map(([field, c]) => ({
    field,
    from: fmtValue(field, c.from, digits, fmtTime),
    to: fmtValue(field, c.to, digits, fmtTime),
  }))
}
