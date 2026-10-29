import { describe, expect, it } from 'vitest'
import { RISK_DEFAULTS } from '@/api/accounts'
import { connectionBadge, describeJob, describeRule, isAuthError, pctText, relativeTime, riskPayload, serverFieldErrors, unknownSymbols, validateAccount, validateRisk } from './model'

describe('validateRisk (mirrors backend RiskProfileIn)', () => {
  it('accepts the F-02 AC2 defaults', () => {
    expect(validateRisk(RISK_DEFAULTS)).toEqual({})
  })

  it('checks ranges, integers and relations between limits', () => {
    const e = validateRisk({ ...RISK_DEFAULTS, risk_per_trade_pct: '0', max_trades_per_day: 2.5, news_blackout_min: 241 })
    expect(e.risk_per_trade_pct?.key).toBe('accounts.errors.range')
    expect(e.max_trades_per_day?.key).toBe('accounts.errors.integer')
    expect(e.news_blackout_min?.params).toEqual({ min: 0, max: 240 })
    expect(validateRisk({ ...RISK_DEFAULTS, max_daily_loss_pct: '12' }).max_daily_loss_pct?.key).toBe('accounts.errors.dailyOverDd')
    expect(validateRisk({ ...RISK_DEFAULTS, risk_per_trade_pct: '4' }).risk_per_trade_pct?.key).toBe('accounts.errors.riskOverDaily')
    expect(validateRisk({ ...RISK_DEFAULTS, max_drawdown_pct: '' }).max_drawdown_pct?.key).toBe('accounts.errors.required')
  })

  it('normalises the payload for the API', () => {
    expect(riskPayload({ ...RISK_DEFAULTS, risk_per_trade_pct: '0.750', max_trades_per_day: '4' as unknown as number })).toMatchObject({
      risk_per_trade_pct: '0.75',
      max_trades_per_day: 4,
    })
  })
})

describe('validateAccount', () => {
  const ok = { name: 'FTMO 100K', broker: 'FTMO', currency: 'USD', initial_balance: '100000' }
  it('requires name/broker, a 3-letter currency and a positive balance', () => {
    expect(validateAccount(ok)).toEqual({})
    const e = validateAccount({ name: ' ', broker: '', currency: 'usd', initial_balance: '0' })
    expect(Object.keys(e).sort()).toEqual(['broker', 'currency', 'initial_balance', 'name'])
    expect(e.initial_balance?.key).toBe('accounts.errors.positive')
  })
})

describe('display helpers', () => {
  it('formats percentages with one decimal minimum', () => {
    expect([pctText('1.00'), pctText('10.00'), pctText('0.75')]).toEqual(['1.0', '10.0', '0.75'])
  })

  it('describes rules for the list', () => {
    const day = (d: number) => ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัส', 'ศุกร์', 'เสาร์', 'อาทิตย์'][d]
    expect(describeRule({ code: 'no_trading_window', params: { days: [4], after: '20:00' } }, day, 'th')).toEqual({
      key: 'accounts.rules.describe.no_trading_window',
      params: { days: 'ศุกร์', after: '20:00' },
    })
    expect(describeRule({ code: 'max_lot_vs_plan', params: { ratio: '1.20' } }, day, 'th').params).toEqual({ ratio: '1.2' })
  })

  it('maps pydantic error locations to form fields', () => {
    const details = [{ loc: ['body', 'risk_profile', 'max_drawdown_pct'], msg: 'x' }, { loc: ['body'], msg: 'y' }]
    expect(Object.keys(serverFieldErrors(details, ['max_drawdown_pct', 'name'] as const))).toEqual(['max_drawdown_pct'])
  })
})

describe('connection helpers (F-08)', () => {
  const now = Date.parse('2026-10-09T03:05:10Z')
  it('relative time within a day, short date after', () => {
    expect(relativeTime('2026-10-09T03:05:00Z', now, 'en')).toBe('10 sec. ago')
    expect(relativeTime('2026-10-09T02:05:10Z', now, 'en')).toBe('1 hr. ago')
    expect(relativeTime('2026-10-07T03:14:00Z', now, 'th')).toMatch(/ต\.ค\. \d\d:14$/)
  })
  it('table badge per status', () => {
    const base = { last_error: null, last_seen_at: '2026-10-09T03:05:00Z', last_sync_at: null }
    expect(connectionBadge('manual', undefined, now, 'th')).toEqual({ variant: 'outline', key: 'connections.badge.none' })
    expect(connectionBadge('mt5', undefined, now, 'th').key).toBe('connections.badge.none')
    expect(connectionBadge('mt5', { ...base, status: 'connected' }, now, 'en')).toEqual({ variant: 'profit', key: 'connections.badge.synced', params: { ago: '10s' } })
    expect(connectionBadge('mt5', { ...base, status: 'pending' }, now, 'th').key).toBe('connections.badge.waitingEa')
    expect(connectionBadge('ctrader', { ...base, status: 'error', last_error: 'CH_ACCESS_TOKEN_INVALID: x' }, now, 'th')).toEqual({
      variant: 'loss',
      key: 'connections.badge.tokenExpired',
    })
    expect(connectionBadge('mt5', { ...base, status: 'error', last_error: 'boom' }, now, 'th').key).toBe('connections.status.error')
  })
  it('auth errors and unknown symbols', () => {
    expect(isAuthError('invalid_grant: expired')).toBe(true)
    expect(isAuthError('TIMEOUT: x')).toBe(false)
    expect(unknownSymbols('unknown_symbols: US30.cash, GER40')).toEqual(['US30.cash', 'GER40'])
    expect(unknownSymbols(null)).toEqual([])
  })
  it('describes import jobs', () => {
    const job = { kind: 'history', source: 'mt5', status: 'success', attempts: 1, error: null, started_at: '', stats: { deals: 124 } }
    expect(describeJob(job, 90).parts.map((p) => p.key)).toEqual(['connections.job.deals', 'connections.job.days'])
    const failed = describeJob({ ...job, kind: 'sync', source: 'ctrader', status: 'error', attempts: 3 }, null)
    expect(failed.ok).toBe(false)
    expect(failed.parts[0]).toEqual({ key: 'connections.job.failed', params: { n: 3, max: 3 } })
    expect(describeJob({ ...job, kind: 'sync', stats: { positions: 2 } }, null).parts[0]).toEqual({ key: 'connections.job.positions', params: { n: 2 } })
    expect(describeJob(job, null).title).toEqual({ key: 'connections.job.history', params: { source: 'MT5' } })
  })
})
