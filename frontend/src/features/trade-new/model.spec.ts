import { describe, expect, it } from 'vitest'
import {
  PLAN_NONE,
  captions,
  emptyExecution,
  emptyForm,
  errorKey,
  firstEntry,
  fmtFixed,
  isoToLocal,
  localLabel,
  localToIso,
  parseNum,
  sortExecutions,
  toInput,
  validateExecution,
  validateForm,
  type ExecRow,
  type TradeForm,
} from './model'

const BKK = 'Asia/Bangkok'
const row = (side: 'in' | 'out', lot: string, price: string, local: string, extra: Partial<ExecRow> = {}): ExecRow => ({
  ...emptyExecution(side, local),
  lot,
  price,
  ...extra,
})

// screens/mobile/10-ManualTrade.png
const DESIGN: ExecRow[] = [
  row('in', '0.30', '4,402.10', '2026-10-09T13:20', { commission: '2.10' }),
  row('in', '0.20', '4404.80', '2026-10-09T13:41', { commission: '1.40' }),
  row('out', '0.25', '4388.00', '2026-10-09T14:30'),
  row('out', '0.25', '4379.50', '2026-10-09T15:05'),
]

function form(over: Partial<TradeForm> = {}): TradeForm {
  return { ...emptyForm({ accountId: 'acc', symbolId: 'xau', local: '2026-10-09T13:20' }), direction: 'short', sl: '4,412.40', executions: DESIGN, ...over }
}

describe('timezone conversion', () => {
  it('maps wall-clock time in the trader timezone to UTC and back', () => {
    expect(localToIso('2026-10-09T13:20', BKK)).toBe('2026-10-09T06:20:00.000Z')
    expect(isoToLocal('2026-10-09T06:20:00Z', BKK)).toBe('2026-10-09T13:20')
    expect(localToIso('2026-10-09T13:20', 'UTC')).toBe('2026-10-09T13:20:00.000Z')
    expect(localToIso('nope', BKK)).toBeNull()
  })

  it('handles a DST zone', () => {
    // New York is UTC-4 in October, UTC-5 in December.
    expect(localToIso('2026-10-09T09:00', 'America/New_York')).toBe('2026-10-09T13:00:00.000Z')
    expect(localToIso('2026-12-09T09:00', 'America/New_York')).toBe('2026-12-09T14:00:00.000Z')
  })
})

describe('executions', () => {
  it('sorts by time with entries first at the same minute', () => {
    const rows = [row('out', '1', '2', '2026-10-09T10:00'), row('in', '1', '1', '2026-10-09T10:00'), row('in', '1', '1', '2026-10-09T09:00')]
    expect(sortExecutions(rows).map((r) => `${r.side}${r.local.slice(11)}`)).toEqual(['in09:00', 'in10:00', 'out10:00'])
  })

  it('captions scale-ins and partial exits like the design', () => {
    const c = captions(DESIGN)
    expect(DESIGN.map((r) => c[r.key])).toEqual([null, 'scaleIn', 'partial', null])
  })

  it('validates a row', () => {
    expect(validateExecution(row('in', '0.123', '1', '2026-10-09T10:00')).lot).toBe('lotStep')
    expect(validateExecution(row('in', '0', '1', '2026-10-09T10:00')).lot).toBe('positive')
    expect(validateExecution(row('in', '1', '', '2026-10-09T10:00')).price).toBe('positive')
    expect(validateExecution(row('in', '1', '1', '')).local).toBe('required')
    expect(validateExecution(row('in', '1', '1', '2026-10-09T10:00', { commission: '-3' })).commission).toBe('cost')
    expect(validateExecution(row('in', '1', '1', '2026-10-09T10:00', { swap: '-1.2' }))).toEqual({})
  })
})

describe('form → API body', () => {
  it('builds the design trade: sorted, UTC times, commission sent as a negative cost', () => {
    const body = toInput(form(), BKK)!
    expect(body.direction).toBe('short')
    expect(body.initial_sl).toBe('4412.40')
    expect(body.initial_tp).toBeNull()
    expect(body.executions.map((e) => [e.side, e.lot, e.price, e.executed_at, e.commission])).toEqual([
      ['in', '0.30', '4402.10', '2026-10-09T06:20:00.000Z', '-2.10'],
      ['in', '0.20', '4404.80', '2026-10-09T06:41:00.000Z', '-1.40'],
      ['out', '0.25', '4388.00', '2026-10-09T07:30:00.000Z', undefined],
      ['out', '0.25', '4379.50', '2026-10-09T08:05:00.000Z', undefined],
    ])
    expect(body).not.toHaveProperty('plan_id')
    expect(body).not.toHaveProperty('unplanned')
  })

  it('maps the plan choice', () => {
    expect(toInput(form({ plan: PLAN_NONE }), BKK)!.unplanned).toBe(true)
    expect(toInput(form({ plan: 'p1' }), BKK)!.plan_id).toBe('p1')
    expect(toInput(form({ rate: '0.0066' }), BKK)!.quote_to_account_rate).toBe('0.0066')
  })

  it('is null while incomplete, with the reasons', () => {
    const blank = emptyForm({ accountId: 'a', symbolId: 's', local: '2026-10-09T10:00' })
    expect(toInput(blank, BKK)).toBeNull()
    expect(validateForm(blank)).toEqual({ execution: 'invalid' })
    expect(validateForm(form({ executions: [row('out', '1', '1', '2026-10-09T10:00')] })).executions).toBe('needEntry')
    expect(validateForm(form({ accountId: '', sl: 'abc' }))).toMatchObject({ account: 'required', sl: 'positive' })
  })

  it('first entry drives plan options', () => {
    expect(firstEntry(form(), BKK)).toEqual({ opened_at: '2026-10-09T06:20:00.000Z', entry_price: '4402.10' })
    expect(firstEntry(form({ executions: [] }), BKK)).toBeNull()
  })
})

describe('display helpers', () => {
  it('formats numbers and dates', () => {
    expect(parseNum('4,402.10')).toBe(4402.1)
    expect(parseNum('x')).toBeNull()
    expect(fmtFixed('4388', 2)).toBe('4,388.00')
    expect(localLabel('2026-10-09T13:20', 'en-US')).toBe('Oct 9 13:20')
    expect(localLabel('2026-10-09T13:20', 'th-TH-u-ca-gregory')).toBe('9 ต.ค. 13:20')
  })

  it('maps error codes', () => {
    expect(errorKey('exit_exceeds_open')).toBe('tradeNew.errors.exit_exceeds_open')
    expect(errorKey('weird')).toBe('tradeNew.errors.generic')
    expect(errorKey(undefined)).toBe('tradeNew.errors.generic')
  })
})
