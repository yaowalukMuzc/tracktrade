import { describe, expect, it } from 'vitest'
import { RISK_DEFAULTS } from '@/api/accounts'
import { describeRule, pctText, riskPayload, serverFieldErrors, validateAccount, validateRisk } from './model'

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
