import { describe, expect, it } from 'vitest'
import { messages } from './messages'

const { th, en } = messages

function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === 'object' ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
  )
}

// F-23 AC2: both languages must cover the same keys, so switching never shows a raw key.
describe('locales', () => {
  it('th and en have identical key sets', () => {
    expect(keys(th).sort()).toEqual(keys(en).sort())
  })

  it('has no empty strings', () => {
    for (const msgs of [th, en]) {
      const empty = keys(msgs).filter((k) => k.split('.').reduce<unknown>((o, p) => (o as Record<string, unknown>)[p], msgs) === '')
      expect(empty).toEqual([])
    }
  })
})
