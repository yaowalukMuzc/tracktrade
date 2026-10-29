import { describe, expect, it } from 'vitest'
import type { MatchCandidate, PositionSummary } from '@/api/positions'
import {
  dayLabelKind,
  defaultChoice,
  entryExit,
  groupByDay,
  holdParts,
  pctText,
  pnlText,
  price,
  queryToState,
  rText,
  stateToQuery,
  toFilters,
  tradeState,
} from './model'

const TZ = 'Asia/Bangkok'

function pos(over: Partial<PositionSummary> = {}): PositionSummary {
  return {
    id: 'p1', ref_no: 1, account_id: 'a1', account_name: 'FTMO', currency: 'USD', symbol_id: 's1',
    symbol_code: 'XAUUSD', digits: 2, direction: 'long', source: 'mt5', status: 'closed',
    opened_at: '2026-10-09T03:05:00Z', closed_at: '2026-10-09T05:52:00Z', avg_entry: '4387.600000',
    avg_exit: '4398.400000', total_lot: '0.48', open_lot: '0.00', net_pnl: '517.30', r_multiple: '0.51',
    current_sl: null, current_tp: null, is_unplanned: false, match_status: 'auto', plan: null,
    adherence_pct: null, quality_grade: null, quadrant: null, review_status: 'pending',
    ...over,
  }
}

describe('query ↔ state', () => {
  it('reads defaults and ignores junk', () => {
    expect(queryToState({ tab: 'nope', page: '-2', from: '9 Oct' })).toEqual({
      tab: 'all', q: '', from: null, to: null, symbol_id: null, setup_id: null, page: 1,
    })
  })
  it('round-trips and keeps unrelated params', () => {
    const s = queryToState({ tab: 'pending', q: 'xau', from: '2026-09-10', to: '2026-10-09', symbol: 's1', page: '2' })
    expect(stateToQuery(s, { match: 'p9', tab: 'all' })).toEqual({
      match: 'p9', tab: 'pending', q: 'xau', from: '2026-09-10', to: '2026-10-09', symbol: 's1', page: '2',
    })
    expect(stateToQuery({ ...s, tab: 'all', q: '  ', page: 1 })).not.toHaveProperty('tab')
  })
  it('builds API filters with the account', () => {
    const s = queryToState({ tab: 'open', q: ' eur ' })
    expect(toFilters(s, 'a1')).toEqual({ tab: 'open', q: 'eur', from: undefined, to: undefined, symbol_id: undefined, setup_id: undefined, account_id: 'a1' })
  })
})

describe('numbers', () => {
  it('formats prices with symbol digits', () => {
    expect(price('4387.600000', 2)).toBe('4,387.60')
    expect(price('1.084020', 5)).toBe('1.08402')
    expect(price(null, 2)).toBe('—')
    expect(entryExit(pos({ avg_exit: null }))).toBe('4,387.60 → —')
  })
  it('signs P/L with a true minus and hides open results', () => {
    expect(pnlText(pos(), 'money')).toBe('+$517.30')
    expect(pnlText(pos({ net_pnl: '-1012.00', r_multiple: '-1.00' }), 'money')).toBe('−$1,012.00')
    expect(pnlText(pos({ net_pnl: '-1012.00', r_multiple: '-1.00' }), 'r')).toBe('−1.00R')
    expect(pnlText(pos({ status: 'open' }), 'money')).toBe('—')
    expect(rText('-0.10')).toBe('−0.10')
    expect(rText('0.51')).toBe('+0.51')
    expect(rText(null)).toBe('—')
  })
  it('hold time', () => {
    expect(holdParts('2026-10-09T03:05:00Z', '2026-10-09T05:52:00Z')).toEqual({ h: 2, m: 47 })
    expect(holdParts('2026-10-09T03:05:00Z', null)).toBeNull()
  })
  it('percent of SL without trailing zeros', () => {
    expect(pctText('21.0')).toBe('21')
    expect(pctText('0.4')).toBe('0.4')
  })
})

describe('grouping', () => {
  it('groups by the trader-local day with per-currency totals of closed trades', () => {
    const items = [
      pos({ id: 'a', opened_at: '2026-10-09T03:05:00Z', net_pnl: '517.30', r_multiple: '0.51' }),
      pos({ id: 'b', opened_at: '2026-10-09T01:42:00Z', net_pnl: '-97.30', r_multiple: '-0.10' }),
      pos({ id: 'o', opened_at: '2026-10-09T00:10:00Z', status: 'open', net_pnl: '0' }),
      // 23:30 UTC on the 7th = 06:30 on the 8th in Bangkok
      pos({ id: 'c', opened_at: '2026-10-07T23:30:00Z', net_pnl: '-1012.00', r_multiple: '-1.00' }),
    ]
    const groups = groupByDay(items, TZ)
    expect(groups.map((g) => [g.day, g.items.map((i) => i.id)])).toEqual([
      ['2026-10-09', ['a', 'b', 'o']],
      ['2026-10-08', ['c']],
    ])
    expect(groups[0].totals).toEqual([{ currency: 'USD', money: 420, r: 0.41 }])
  })
  it('labels today and yesterday', () => {
    const now = new Date('2026-10-09T05:00:00Z')
    expect(dayLabelKind('2026-10-09', TZ, now)).toBe('today')
    expect(dayLabelKind('2026-10-08', TZ, now)).toBe('yesterday')
    expect(dayLabelKind('2026-10-01', TZ, now)).toBe('date')
  })
})

describe('status and match choice', () => {
  it('one status per trade', () => {
    expect(tradeState(pos({ match_status: 'pending' }))).toBe('pending')
    expect(tradeState(pos({ status: 'open', review_status: null }))).toBe('open')
    expect(tradeState(pos())).toBe('review')
    expect(tradeState(pos({ review_status: 'done' }))).toBe('reviewed')
  })
  it('defaults to the recommended plan, else unplanned', () => {
    const c = (id: string, eligible: boolean, recommended = false) =>
      ({ plan: { id }, eligible, recommended }) as unknown as MatchCandidate
    expect(defaultChoice([c('x', true), c('y', true, true)])).toBe('y')
    expect(defaultChoice([c('x', false), c('y', true)])).toBe('y')
    expect(defaultChoice([c('x', false)])).toBeNull()
  })
})
