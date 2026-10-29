import { describe, expect, it } from 'vitest'
import type { Plan } from '@/api/plans'
import {
  calcInput,
  changeRows,
  emptyModel,
  formatPrice,
  formatRiskPct,
  fromLocalInput,
  missingRequired,
  nextScenario,
  parseNum,
  revisionChanges,
  scenarioOptions,
  splitShares,
  toCreate,
  toLocalInput,
  toUpdate,
  validatePlan,
  validateRevision,
  type PlanFormModel,
} from './form'

const long = (over: Partial<PlanFormModel> = {}): PlanFormModel => ({
  ...emptyModel({ setupId: 's1', riskPct: '1' }),
  entry: '4,387.52',
  stopLoss: '4,366.78',
  tps: [
    { price: '4,418.00', pct: '50' },
    { price: '4,437.51', pct: '50' },
  ],
  ...over,
})

const plan = (over: Partial<Plan> = {}): Plan =>
  ({
    id: 'p1',
    setup_id: 's1',
    direction: 'long',
    entry_type: 'limit',
    scenario_label: 'A',
    entry_price: '4387.520000',
    stop_loss: '4366.780000',
    take_profits: [
      { price: '4418.000000', pct: '50.00', rr: '1.47' },
      { price: '4437.510000', pct: '50.00', rr: '2.41' },
    ],
    planned_risk_pct: '1.00',
    management_plan: { partial: true, break_even: true, trailing: false },
    invalidation: '',
    valid_until: null,
    checklist_items: [],
    ...over,
  }) as Plan

describe('parseNum / formatting', () => {
  it('reads separators and rejects garbage', () => {
    expect(parseNum('4,387.52')).toBe(4387.52)
    expect(parseNum(' 1.0 ')).toBe(1)
    expect(parseNum('')).toBeNull()
    expect(parseNum('abc')).toBeNull()
    expect(parseNum('1.2.3')).toBeNull()
  })
  it('formats prices with the symbol digits', () => {
    expect(formatPrice('4366.780000', 2)).toBe('4,366.78')
    expect(formatPrice('1.0842', 5)).toBe('1.08420')
    expect(formatRiskPct('1.00')).toBe('1.0')
    expect(formatRiskPct('0.75')).toBe('0.75')
  })
  it('round-trips datetime-local', () => {
    const iso = fromLocalInput('2026-10-09T22:00')!
    expect(toLocalInput(iso)).toBe('2026-10-09T22:00')
    expect(fromLocalInput('')).toBeNull()
  })
  it('splits TP shares to 100%', () => {
    expect(splitShares(2)).toEqual(['50', '50'])
    expect(splitShares(3)).toEqual(['33.33', '33.33', '33.34'])
  })
})

describe('validatePlan (F-06 AC1)', () => {
  it('accepts a complete LONG plan', () => {
    expect(validatePlan(long())).toEqual({})
  })

  it('requires setup, entry, SL, one TP and risk %', () => {
    const e = validatePlan(emptyModel())
    expect(e).toMatchObject({ setup: 'required', entry: 'required', stopLoss: 'required', tps: 'tpRequired', riskPct: 'required' })
  })

  it('LONG needs SL < entry < TPs', () => {
    expect(validatePlan(long({ stopLoss: '4,390' })).stopLoss).toBe('slBelowEntry')
    expect(validatePlan(long({ tps: [{ price: '4,380', pct: '100' }] }))['tp.0']).toBe('tpAboveEntry')
  })

  it('SHORT needs TPs < entry < SL', () => {
    const short = long({ direction: 'short', entry: '4362', stopLoss: '4378.40', tps: [{ price: '4322', pct: '100' }] })
    expect(validatePlan(short)).toEqual({})
    expect(validatePlan({ ...short, stopLoss: '4350' }).stopLoss).toBe('slAboveEntry')
    expect(validatePlan({ ...short, tps: [{ price: '4370', pct: '100' }] })['tp.0']).toBe('tpBelowEntry')
  })

  it('TP shares must not exceed 100%', () => {
    const e = validatePlan(long({ tps: [{ price: '4418', pct: '60' }, { price: '4437', pct: '50' }] }))
    expect(e.tpShare).toBe('tpShareOver')
    expect(validatePlan(long({ tps: [{ price: '4418', pct: '50' }, { price: '4437', pct: '50' }] })).tpShare).toBeUndefined()
  })

  it('a single TP without a share counts as 100%; several need shares', () => {
    expect(validatePlan(long({ tps: [{ price: '4418', pct: '' }] }))).toEqual({})
    expect(validatePlan(long({ tps: [{ price: '4418', pct: '' }, { price: '4437', pct: '50' }] }))['tpPct.0']).toBe('share')
  })

  it('risk % must be in (0, 10]', () => {
    expect(validatePlan(long({ riskPct: '0' })).riskPct).toBe('riskRange')
    expect(validatePlan(long({ riskPct: '12' })).riskPct).toBe('riskRange')
    expect(validatePlan(long({ riskPct: '0.5' })).riskPct).toBeUndefined()
  })
})

describe('payloads', () => {
  it('toUpdate sends plain decimals, skips empty TP rows and an empty valid-until', () => {
    const m = long({ tps: [{ price: '4,418.00', pct: '100' }, { price: '', pct: '' }], checklist: { c1: true, c2: false } })
    const body = toUpdate(m)
    expect(body).toMatchObject({
      setup_id: 's1',
      entry_price: '4387.52',
      stop_loss: '4366.78',
      take_profits: [{ price: '4418', pct: '100' }],
      planned_risk_pct: '1',
      checklist_answers: [
        { checklist_item_id: 'c1', checked: true },
        { checklist_item_id: 'c2', checked: false },
      ],
    })
    expect('valid_until' in body).toBe(false)
  })

  it('toCreate adds the context and the pre-trade emotion when given', () => {
    const body = toCreate(long(), { analysisId: 'a1', accountId: 'acc', symbolId: 'xau', planDate: '2026-10-09' }, { mood: 7, confidence: null, tags: ['t1'] })
    expect(body).toMatchObject({ analysis_id: 'a1', account_id: 'acc', symbol_id: 'xau', plan_date: '2026-10-09', pre_emotion: { mood: 7, confidence: null, tags: ['t1'] } })
    expect(toCreate(long(), { analysisId: null, accountId: 'acc', symbolId: 'xau' }, { mood: null, confidence: null, tags: [] }).pre_emotion).toBeUndefined()
  })

  it('calcInput waits for entry, SL and risk %', () => {
    expect(calcInput(long({ stopLoss: '' }), 'acc', 'xau')).toBeNull()
    expect(calcInput(long(), null, 'xau')).toBeNull()
    expect(calcInput(long(), 'acc', 'xau')).toMatchObject({ entry: '4387.52', stop_loss: '4366.78', risk_pct: '1', take_profits: [{ price: '4418', pct: 50 }, { price: '4437.51', pct: 50 }] })
  })
})

describe('checklist / scenario', () => {
  it('lists required items that are not ticked', () => {
    const items = [
      { id: 'a', is_required: true },
      { id: 'b', is_required: false },
      { id: 'c', is_required: true },
    ]
    expect(missingRequired(items, { a: true })).toEqual(['c'])
    expect(missingRequired(items, { a: true, c: true })).toEqual([])
  })

  it('scenario options skip letters used by sibling plans', () => {
    expect(scenarioOptions([], 'A')).toEqual(['A', 'B'])
    expect(scenarioOptions(['A'], 'B')).toEqual(['B', 'C'])
    expect(scenarioOptions(['B'], 'A', 3)).toEqual(['A', 'C', 'D'])
    expect(nextScenario(['A', 'B'])).toBe('C')
  })
})

describe('revisions (F-06 AC4)', () => {
  const draft = { entry: '4,387.52', stopLoss: '4,366.78', tps: [{ price: '4,418.00', pct: '50' }, { price: '4,437.51', pct: '50' }], riskPct: '1.0' }

  it('sends only the changed fields', () => {
    expect(revisionChanges(plan(), draft, { triggered: false })).toEqual({})
    expect(revisionChanges(plan(), { ...draft, stopLoss: '4,360.00' }, { triggered: false })).toEqual({ stop_loss: '4360' })
    expect(revisionChanges(plan(), { ...draft, tps: [{ price: '4,420', pct: '50' }, draft.tps[1]] }, { triggered: false }).take_profits).toEqual([
      { price: '4420', pct: '50' },
      { price: '4437.51', pct: '50' },
    ])
  })

  it('drops the risk % once the plan is triggered', () => {
    expect(revisionChanges(plan(), { ...draft, riskPct: '0.5' }, { triggered: false })).toEqual({ planned_risk_pct: '0.5' })
    expect(revisionChanges(plan(), { ...draft, riskPct: '0.5' }, { triggered: true })).toEqual({})
  })

  it('validates the new levels against the direction', () => {
    expect(validateRevision(plan(), { ...draft, stopLoss: '4,400' }).stopLoss).toBe('slBelowEntry')
  })

  it('formats change rows', () => {
    const rows = changeRows({ changes: { stop_loss: { from: '4366.78', to: '4360' } } }, 2)
    expect(rows).toEqual([{ field: 'stop_loss', from: '4,366.78', to: '4,360.00' }])
  })
})
