import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import type { Drawing, KeyLevel } from '@/api/analysis'
import {
  addLevel,
  emptyLevelForm,
  errorKey,
  formatLevelPrice,
  imageFileError,
  isNotFound,
  levelFromForm,
  localToday,
  normalizeDoc,
  sortLevels,
  toDrawingInputs,
  toggleTimeframe,
  validateLevel,
} from './model'

const lvl = (price: string, price_to: string | null = null, kind: KeyLevel['kind'] = 'support'): KeyLevel => ({ price, price_to, kind, label: '' })

describe('key level form', () => {
  it('requires a positive price', () => {
    expect(validateLevel(emptyLevelForm())).toEqual({ price: 'required' })
    expect(validateLevel({ ...emptyLevelForm(), price: 'abc' })).toEqual({ price: 'positive' })
    expect(validateLevel({ ...emptyLevelForm(), price: '0' })).toEqual({ price: 'positive' })
    expect(validateLevel({ ...emptyLevelForm(), price: '4,366.50' })).toEqual({})
  })

  it('needs both ends for a zone, and they must differ', () => {
    const zone = { ...emptyLevelForm(), kind: 'zone' as const, price: '4380' }
    expect(validateLevel(zone)).toEqual({ priceTo: 'required' })
    expect(validateLevel({ ...zone, priceTo: '4380.0' })).toEqual({ priceTo: 'sameAsPrice' })
    expect(validateLevel({ ...zone, priceTo: '4388' })).toEqual({})
  })

  it('ignores price_to for line kinds', () => {
    expect(validateLevel({ ...emptyLevelForm(), price: '4366', priceTo: 'x' })).toEqual({})
    expect(levelFromForm({ kind: 'resistance', price: '4,437.5', priceTo: '4500', label: ' previous high ' })).toEqual({
      price: '4437.5',
      price_to: null,
      kind: 'resistance',
      label: 'previous high',
    })
  })

  it('orders zone ends low → high', () => {
    expect(levelFromForm({ kind: 'zone', price: '4388', priceTo: '4380', label: '' })).toMatchObject({ price: '4380', price_to: '4388' })
  })
})

describe('key level list', () => {
  it('sorts by price, stable for equal prices', () => {
    const a = { ...lvl('4366'), label: 'a' }
    const b = { ...lvl('4366'), label: 'b' }
    expect(sortLevels([lvl('4437.5'), a, lvl('4380', '4388', 'zone'), b]).map((l) => l.label || l.price)).toEqual(['a', 'b', '4380', '4437.5'])
    expect(addLevel([lvl('4366'), lvl('4437.5')], lvl('4400')).map((l) => l.price)).toEqual(['4366', '4400', '4437.5'])
  })

  it('formats lines with the symbol digits and zones without trailing zeros', () => {
    expect(formatLevelPrice(lvl('4366'), 2)).toBe('4,366.00')
    expect(formatLevelPrice(lvl('4437.500000'), 2)).toBe('4,437.50')
    expect(formatLevelPrice(lvl('4380.000000', '4388.000000', 'zone'), 2)).toBe('4,380 – 4,388')
    expect(formatLevelPrice(lvl('1.0842'), 5)).toBe('1.08420')
  })
})

describe('helpers', () => {
  it('toggles timeframes in canonical order', () => {
    expect(toggleTimeframe(['H4', 'M15'], 'H1')).toEqual(['M15', 'H1', 'H4'])
    expect(toggleTimeframe(['M15', 'H1'], 'M15')).toEqual(['H1'])
  })

  it('formats the local date as YYYY-MM-DD', () => {
    expect(localToday(new Date(2026, 9, 9, 23, 30))).toBe('2026-10-09')
  })

  it('drops text drawings without text', () => {
    const base = { timeframe: 'H1', points: [{ time: 1, price: '1' }], style: { color: 'ink', line: 'solid', width: 1 } } as const
    const ds = [
      { ...base, id: 'a', tool: 'horizontal', text: '' },
      { ...base, id: 'b', tool: 'text', text: '  ' },
      { ...base, id: 'c', tool: 'text', text: 'Higher low' },
    ] as unknown as Drawing[]
    expect(toDrawingInputs(ds).map((d) => d.id)).toEqual(['a', 'c'])
  })

  it('normalizes narrative documents', () => {
    expect(normalizeDoc(null)).toEqual({ type: 'doc', content: [] })
    expect(normalizeDoc({ type: 'doc' })).toEqual({ type: 'doc', content: [] })
    const doc = { type: 'doc', content: [{ type: 'paragraph' }] }
    expect(normalizeDoc(doc)).toEqual(doc)
  })

  it('checks image files before upload', () => {
    expect(imageFileError(new File(['x'], 'a.png', { type: 'image/png' }))).toBeNull()
    expect(imageFileError(new File(['x'], 'a.gif', { type: 'image/gif' }))?.[0]).toBe('analysis.errors.fileType')
  })

  it('maps API errors', () => {
    expect(errorKey(new ApiError(409, 'analysis_has_plans', 'x'))[0]).toBe('analysis.errors.hasPlans')
    expect(errorKey(new Error('offline'))[0]).toBe('analysis.errors.network')
    expect(isNotFound(new ApiError(404, 'not_found', 'x'))).toBe(true)
    expect(isNotFound(new ApiError(500, 'boom', 'x'))).toBe(false)
  })
})
