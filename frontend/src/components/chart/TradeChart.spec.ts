import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createI18n } from 'vue-i18n'
import type { Bar } from '@/api/analysis'

// Canvas doesn't exist in jsdom: replace the chart library with a recorder.
const calls = vi.hoisted(() => ({
  priceLines: [] as Record<string, unknown>[],
  removed: 0,
  data: [] as unknown[],
  seriesOptions: [] as Record<string, unknown>[],
  primitives: 0,
}))

vi.mock('lightweight-charts', () => {
  const series = {
    setData: (d: unknown[]) => calls.data.splice(0, calls.data.length, ...d),
    createPriceLine: (o: Record<string, unknown>) => {
      calls.priceLines.push(o)
      return o
    },
    removePriceLine: () => {
      calls.removed++
    },
    applyOptions: (o: Record<string, unknown>) => calls.seriesOptions.push(o),
    attachPrimitive: () => {
      calls.primitives++
    },
    priceToCoordinate: () => 0,
    coordinateToPrice: () => 0,
  }
  const timeScale = {
    setVisibleLogicalRange: () => {},
    logicalToCoordinate: () => 0,
    coordinateToLogical: () => 0,
    scrollToRealTime: () => {},
  }
  return {
    CandlestickSeries: 'Candlestick',
    CrosshairMode: { Normal: 0 },
    LineStyle: { Solid: 0, Dotted: 1, Dashed: 2 },
    TickMarkType: { Year: 0, Month: 1, DayOfMonth: 2, Time: 3, TimeWithSeconds: 4 },
    createChart: () => ({
      addSeries: (_type: unknown, o: Record<string, unknown>) => {
        calls.seriesOptions.push(o)
        return series
      },
      applyOptions: () => {},
      timeScale: () => timeScale,
      paneSize: () => ({ width: 800, height: 400 }),
      subscribeCrosshairMove: () => {},
      unsubscribeCrosshairMove: () => {},
      remove: () => {},
    }),
  }
})

import TradeChart from './TradeChart.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: { en: { chart: { entryShort: 'EN', slShort: 'SL', tpShort: 'TP', tpShortN: 'TP{n}', measureLabel: '', textPrompt: '' } } },
})

const bars: Bar[] = [
  { time: 1_760_000_000, open: '4380.00', high: '4390.50', low: '4375.25', close: '4388.00', volume: 1 },
  { time: 1_760_003_600, open: '4388.00', high: '4392.00', low: '4381.00', close: '4384.10', volume: 1 },
]

function mountChart(props: Record<string, unknown> = {}) {
  return mount(TradeChart, {
    props: { bars, digits: 2, timeframe: 'H1', label: 'XAUUSD H1', ...props },
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
}

describe('TradeChart', () => {
  beforeEach(() => {
    calls.priceLines.length = 0
    calls.removed = 0
    calls.seriesOptions.length = 0
  })

  it('feeds the bars as numbers with the symbol precision', async () => {
    mountChart()
    await flushPromises()
    expect(calls.data).toEqual([
      { time: 1_760_000_000, open: 4380, high: 4390.5, low: 4375.25, close: 4388 },
      { time: 1_760_003_600, open: 4388, high: 4392, low: 4381, close: 4384.1 },
    ])
    expect(calls.seriesOptions[0].priceFormat).toEqual({ type: 'price', precision: 2, minMove: 0.01 })
    expect(calls.primitives).toBeGreaterThan(0)
  })

  it('draws plan lines at the plan prices: dashed EN / SL / TP1 / TP2', async () => {
    mountChart({ plan: { entry: '4387.52', stopLoss: '4366.78', takeProfits: ['4418', '4437.51'] } })
    await flushPromises()
    expect(calls.priceLines.map((l) => [l.title, l.price, l.lineStyle])).toEqual([
      ['EN', 4387.52, 2],
      ['SL', 4366.78, 2],
      ['TP1', 4418, 2],
      ['TP2', 4437.51, 2],
    ])
  })

  it('shows single key levels as solid lines (zones are drawn as boxes) and redraws on change', async () => {
    const w = mountChart({
      keyLevels: [
        { price: '4366', price_to: null, kind: 'support', label: 'H4 swing low' },
        { price: '4380', price_to: '4388', kind: 'zone', label: 'Demand' },
      ],
    })
    await flushPromises()
    expect(calls.priceLines.map((l) => [l.title, l.price, l.lineStyle])).toEqual([['H4 swing low', 4366, 0]])

    await w.setProps({ plan: { entry: 100, stopLoss: 90, takeProfits: [120] } })
    await flushPromises()
    expect(calls.removed).toBe(1)
    expect(calls.priceLines.slice(1).map((l) => l.title)).toEqual(['H4 swing low', 'EN', 'SL', 'TP'])
  })

  it('keeps the plan inside the autoscale range', async () => {
    mountChart({ plan: { entry: '4387.52', stopLoss: '4300', takeProfits: ['4500'] } })
    await flushPromises()
    const provider = calls.seriesOptions[0].autoscaleInfoProvider as (o: () => unknown) => { priceRange: { minValue: number; maxValue: number } }
    const range = provider(() => ({ priceRange: { minValue: 4370, maxValue: 4395 } }))
    expect(range.priceRange).toEqual({ minValue: 4300, maxValue: 4500 })
  })
})
