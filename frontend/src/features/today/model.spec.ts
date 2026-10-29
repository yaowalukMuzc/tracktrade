import { describe, expect, it } from 'vitest'
import type { AccountRisk } from '@/api/analysis'
import type { PlanBrief } from '@/api/plans'
import { biasBadge, chartTimeframes, dailyLossKpi, formatPrice, lastTakeProfit, pnlKpi, rankAnalyses, sortPlans, todayKpis, todoTotal } from './model'

function risk(over: Partial<AccountRisk> & { name: string }, used = { loss: '0', trades: '0' }, limit = { loss: '3000', trades: '5' }): AccountRisk {
  return {
    account_id: over.name,
    currency: 'USD',
    balance: '100000',
    equity: '100000',
    daily_loss: { used: used.loss, limit: limit.loss },
    drawdown_pct: { used: '0', limit: '10' },
    trades_today: { used: used.trades, limit: limit.trades },
    ...over,
  }
}

const ftmo = risk({ name: 'FTMO 100K Challenge' }, { loss: '0', trades: '2' })
const ic = risk({ name: 'IC Markets Live', balance: '8412' }, { loss: '126', trades: '1' }, { loss: '252.36', trades: '3' })
const demo = risk({ name: 'Demo Practice', balance: '10517' }, { loss: '0', trades: '0' }, { loss: '315.51', trades: '5' })

describe('todayKpis', () => {
  it('sums trades used / max across all accounts (F-02 AC3 "all")', () => {
    const k = todayKpis({ pnl: [], risk: [ftmo, ic, demo], adherence_week: null, goal_adherence: null })
    expect(k.trades).toEqual({ used: 3, limit: 13 })
  })

  it('shows a single account as is', () => {
    const k = todayKpis({ pnl: [], risk: [ftmo], adherence_week: '74', goal_adherence: '85' })
    expect(k.trades).toEqual({ used: 2, limit: 5 })
    expect(k.adherence).toBe(74)
    expect(k.goal).toBe(85)
    expect(k.dailyLoss).toMatchObject({ usedPct: 0, limitPct: 3, limitAmount: 3000, accountName: null })
  })

  it('keeps adherence null until it exists (never invents a number)', () => {
    const k = todayKpis({ pnl: [], risk: [], adherence_week: null, goal_adherence: null })
    expect(k.adherence).toBeNull()
    expect(k.dailyLoss).toBeNull()
    expect(k.trades).toEqual({ used: 0, limit: 0 })
  })
})

describe('pnlKpi', () => {
  it('is $0 with 0 trades before any trade exists', () => {
    expect(pnlKpi([], [ftmo])).toEqual({ currency: 'USD', amount: 0, r: 0, trades: 0, otherCurrencies: 0 })
  })

  it('uses the main currency and counts trades of every currency', () => {
    const k = pnlKpi(
      [
        { currency: 'EUR', amount: '-50', r: '-0.5', trades: 1 },
        { currency: 'USD', amount: '420', r: '0.41', trades: 2 },
      ],
      [ftmo, ic],
    )
    expect(k).toEqual({ currency: 'USD', amount: 420, r: 0.41, trades: 3, otherCurrencies: 1 })
  })
})

describe('dailyLossKpi', () => {
  it('shows the account closest to its limit when several are selected', () => {
    const k = dailyLossKpi([ftmo, ic, demo])!
    expect(k.accountName).toBe('IC Markets Live')
    expect(k.usage).toBeCloseTo(49.93, 1)
    expect(k.usedPct).toBeCloseTo(1.5, 2)
    expect(k.limitPct).toBeCloseTo(3, 2)
  })

  it('falls back to the first account when nothing is used', () => {
    expect(dailyLossKpi([ftmo, demo])!.accountName).toBe('FTMO 100K Challenge')
  })
})

const plan = (over: Partial<PlanBrief>): PlanBrief =>
  ({ id: 'p', analysis_id: null, symbol_code: 'XAUUSD', scenario_label: 'A', status: 'draft', take_profits: [], ...over }) as PlanBrief

describe('plans', () => {
  it('ranks analyses by open plans, then API order', () => {
    const plans = [
      plan({ analysis_id: 'eur', status: 'skipped', symbol_code: 'EURUSD' }),
      plan({ analysis_id: 'xau', status: 'locked' }),
      plan({ analysis_id: 'xau', status: 'draft', scenario_label: 'B' }),
    ]
    expect(rankAnalyses([{ id: 'eur' }, { id: 'xau' }], plans).map((a) => a.id)).toEqual(['xau', 'eur'])
    expect(rankAnalyses([{ id: 'a' }, { id: 'b' }], []).map((a) => a.id)).toEqual(['a', 'b'])
  })

  it('groups plans by the ranked symbols then scenario label', () => {
    const plans = [
      plan({ id: '1', symbol_code: 'EURUSD' }),
      plan({ id: '2', scenario_label: 'B' }),
      plan({ id: '3', scenario_label: 'A' }),
      plan({ id: '4', symbol_code: 'GBPUSD' }),
    ]
    expect(sortPlans(plans, ['XAUUSD', 'EURUSD']).map((p) => p.id)).toEqual(['3', '2', '1', '4'])
  })

  it('shows the last take profit', () => {
    expect(lastTakeProfit(plan({ take_profits: [{ price: '4418', pct: '50', rr: null }, { price: '4437.51', pct: '50', rr: null }] }))).toBe('4437.51')
    expect(lastTakeProfit(plan({}))).toBeNull()
  })
})

describe('formatting', () => {
  it('formats prices with the symbol digits', () => {
    expect(formatPrice('4387.52', 2)).toBe('4,387.52')
    expect(formatPrice('4362', 2)).toBe('4,362.00')
    expect(formatPrice('1.0842', 5)).toBe('1.08420')
  })

  it('totals the to-do counts', () => {
    expect(todoTotal({ pending_match: 2, pending_review: 1, inbox: 0 })).toBe(3)
  })
})

describe('analysis helpers', () => {
  it('maps bias to a badge', () => {
    expect(biasBadge('bull')).toEqual({ variant: 'profit', icon: 'up' })
    expect(biasBadge('bear')).toEqual({ variant: 'loss', icon: 'down' })
    expect(biasBadge('range')).toEqual({ variant: 'neutral' })
  })

  it('offers the analysis timeframes plus H1, ordered', () => {
    expect(chartTimeframes(['H4', 'M15'])).toEqual(['M15', 'H1', 'H4'])
    expect(chartTimeframes([])).toEqual(['H1'])
  })
})
