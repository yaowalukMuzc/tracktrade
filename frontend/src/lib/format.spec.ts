import { describe, expect, it } from 'vitest'
import { MINUS, directionOf, formatMoney, formatPct, formatR } from './format'

describe('format', () => {
  it('signs every P/L with + or U+2212', () => {
    expect(formatMoney(1669.98)).toBe('+$1,669.98')
    expect(formatMoney(-486)).toBe(`${MINUS}$486.00`)
    expect(formatMoney(-486)).not.toContain('-')
    expect(formatMoney(0)).toBe('$0.00')
  })

  it('formats R multiples', () => {
    expect(formatR(2.4)).toBe('+2.4R')
    expect(formatR(-1)).toBe(`${MINUS}1.0R`)
    expect(formatR(0)).toBe('0.0R')
  })

  it('compacts large money for narrow cells', () => {
    expect(formatMoney(-1025.4, 'USD', { compact: true })).toBe(`${MINUS}$1K`)
  })

  it('formats percentages', () => {
    expect(formatPct(62.5)).toBe('62.5%')
    expect(formatPct(3, 1, true)).toBe('+3.0%')
  })

  it('derives direction from sign', () => {
    expect(directionOf(1)).toBe('up')
    expect(directionOf(-1)).toBe('down')
    expect(directionOf(0)).toBe('flat')
  })
})

describe('formatAmount', () => {
  it('shows cents only when present, and then always two digits', async () => {
    const { formatAmount } = await import('./format')
    expect(formatAmount(100000, 'USD')).toBe('$100,000')
    expect(formatAmount('3037.2', 'USD')).toBe('$3,037.20')
    expect(formatAmount('1012.4', 'USD')).toBe('$1,012.40')
    expect(formatAmount('10.005', 'USD', 0)).toBe('$10')
  })
})
