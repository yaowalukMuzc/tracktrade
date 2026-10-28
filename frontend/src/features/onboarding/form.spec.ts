import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import { apiErrors, emptyForm, parseNum, toPayload, validate } from './form'

const filled = () => ({ ...emptyForm(), name: ' FTMO 100K ', broker: 'FTMO', initial_balance: '100,000' })

describe('onboarding form', () => {
  it('parses grouped numbers and rejects junk', () => {
    expect(parseNum('100,000.5')).toBe(100000.5)
    expect(parseNum('-1')).toBeNaN()
    expect(parseNum('1e3')).toBeNaN()
  })

  it('accepts the F-02 AC2 defaults once name, broker and balance are filled', () => {
    expect(validate(emptyForm())).toMatchObject({ name: { key: 'required' }, broker: { key: 'required' }, initial_balance: { key: 'required' } })
    expect(validate(filled())).toEqual({})
  })

  it('mirrors the backend limits', () => {
    const f = filled()
    f.initial_balance = '0'
    f.risk.risk_per_trade_pct = '11'
    f.risk.max_trades_per_day = '2.5'
    f.risk.revenge_cooldown_min = '1441'
    f.risk.news_blackout_min = 'x'
    expect(validate(f)).toEqual({
      initial_balance: { key: 'positive' },
      risk_per_trade_pct: { key: 'rangePct', params: { max: 10 } },
      max_trades_per_day: { key: 'integer' },
      revenge_cooldown_min: { key: 'range', params: { min: 0, max: 1440 } },
      news_blackout_min: { key: 'integer' },
    })
  })

  it('checks risk ≤ daily loss ≤ drawdown', () => {
    const f = filled()
    f.risk.max_daily_loss_pct = '12'
    expect(validate(f)).toEqual({ max_daily_loss_pct: { key: 'dailyVsDrawdown' } })
    f.risk.max_daily_loss_pct = '0.5'
    expect(validate(f)).toEqual({ risk_per_trade_pct: { key: 'riskVsDaily' } })
  })

  it('builds one create payload with the risk profile', () => {
    expect(toPayload(filled())).toEqual({
      name: 'FTMO 100K',
      broker: 'FTMO',
      platform: 'mt5',
      account_type: 'live',
      currency: 'USD',
      initial_balance: '100000',
      risk_profile: {
        risk_per_trade_pct: '1',
        max_daily_loss_pct: '3',
        max_drawdown_pct: '10',
        max_trades_per_day: 5,
        revenge_cooldown_min: 30,
        news_blackout_min: 15,
      },
    })
  })

  it('maps API validation details to fields', () => {
    const e = new ApiError(422, 'validation_error', 'Request validation failed', [
      { loc: ['body', 'risk_profile', 'max_trades_per_day'], msg: 'x' },
    ])
    expect(apiErrors(e)).toEqual({ fields: { max_trades_per_day: { key: 'invalid' } }, form: { key: 'fixFields' } })
    const cross = new ApiError(422, 'validation_error', '', [{ loc: ['body', 'risk_profile'], msg: 'x' }])
    expect(apiErrors(cross).form).toEqual({ key: 'riskConsistency' })
    expect(apiErrors(new Error('net'))).toEqual({ fields: {}, form: { key: 'saveFailed' } })
  })
})
