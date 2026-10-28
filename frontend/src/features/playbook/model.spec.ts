import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import type { SetupStats } from '@/api/playbook'
import { apiFieldErrors, emptyForm, errorKey, fileError, formToInput, moveItem, statView, toChecklistInput, validateForm } from './model'

const noStats: SetupStats = { trades: 0, win_rate: null, expectancy_r: null, avg_adherence: null, avg_quality: null, avg_quality_grade: null }

describe('playbook model', () => {
  it('shows "—" for stats the backend does not compute yet', () => {
    const v = statView(noStats)
    expect([v.trades, v.winRate, v.expectancy, v.adherence, v.quality]).toEqual(['—', '—', '—', '—', '—'])
    expect(v.expDir).toBeNull()
  })

  it('formats real stats with a signed expectancy', () => {
    const v = statView({ trades: 18, win_rate: '61', expectancy_r: '-0.08', avg_adherence: '84.2', avg_quality: '74', avg_quality_grade: 'B' })
    expect(v.expectancy).toBe('−0.08R')
    expect(v.expDir).toBe('down')
    expect(v.quality).toBe('B · 74')
  })

  it('validates like the backend schema', () => {
    const m = { ...emptyForm(), name: '  ', risk: '12', partialOn: true, partialPct: '100', partialAt: '1.555', trailOn: true }
    expect(validateForm(m, false)).toEqual({
      name: 'playbook.errors.nameRequired',
      risk: 'playbook.errors.riskRange',
      partialPct: 'playbook.errors.pctRange',
      partialAt: 'playbook.errors.decimals',
      trailMethod: 'playbook.errors.methodRequired',
    })
    expect(validateForm({ ...emptyForm(), name: 'London Breakout' }, true)).toEqual({})
  })

  it('builds the request body with null for disabled rules and canonical order', () => {
    const body = formToInput({ ...emptyForm(), name: ' X ', timeframes: ['H1', 'M15'], sessions: ['new_york', 'asia'], beOn: true }, false)
    expect(body.timeframes).toEqual(['M15', 'H1'])
    expect(body.sessions).toEqual(['asia', 'new_york'])
    expect(body.management_rules).toEqual({ partial: null, break_even: { at_r: '1' }, trailing: null })
    expect(body.checklist).toBeUndefined()
  })

  it('keeps checklist ids and reorders', () => {
    const items = [
      { key: 'a', id: 'a', text: ' A ', is_required: true },
      { key: 'new-1', text: 'B', is_required: false },
    ]
    expect(toChecklistInput(items)).toEqual([{ id: 'a', text: 'A', is_required: true }, { text: 'B', is_required: false }])
    expect(moveItem([1, 2, 3], 0, 2)).toEqual([2, 3, 1])
    expect(moveItem([1, 2], 0, -1)).toEqual([1, 2])
  })

  it('maps API errors', () => {
    expect(errorKey(new ApiError(413, 'file_too_large', ''))[0]).toBe('playbook.errors.fileSize')
    expect(errorKey(new TypeError('fetch'))[0]).toBe('playbook.errors.network')
    const v = new ApiError(422, 'validation_error', '', [{ loc: ['body', 'management_rules', 'partial', 'pct'] }, { loc: ['body', 'name'] }])
    expect(apiFieldErrors(v)).toEqual({ partialPct: 'playbook.errors.invalid', name: 'playbook.errors.invalid' })
  })

  it('checks files before upload', () => {
    expect(fileError(new File(['x'], 'a.gif', { type: 'image/gif' }))?.[0]).toBe('playbook.errors.fileType')
    expect(fileError(new File(['x'], 'a.png', { type: 'image/png' }))).toBeNull()
  })
})
