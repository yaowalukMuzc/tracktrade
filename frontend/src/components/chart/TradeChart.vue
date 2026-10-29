<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CandlestickSeries,
  CrosshairMode,
  LineStyle,
  TickMarkType,
  createChart,
  type AutoscaleInfo,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { Bar, Drawing, DrawingTool, KeyLevel } from '@/api/analysis'
import type { Timeframe } from '@/api/playbook'
import { levelColor, onThemeChange, readChartTheme, type ChartTheme } from '@/lib/chartTheme'
import { formatNumber, MINUS } from '@/lib/format'
import { DrawingsPrimitive, type ChartDrawing, type ChartZone } from './DrawingsPrimitive'
import {
  distanceToRectEdge,
  distanceToSegment,
  insideRect,
  logicalToTime,
  measure,
  rayEnd,
  snapTime,
  timeToLogical,
  type Pt,
} from './geometry'
import { POINTS_PER_TOOL } from '@/api/analysis'

/** Plan levels drawn as dashed price lines with EN / SL / TP labels on the price axis. */
export interface PlanLines {
  entry: number | string
  stopLoss: number | string
  takeProfits: (number | string)[]
}

export type ChartTool = DrawingTool | 'cursor'

const props = withDefaults(
  defineProps<{
    bars: Bar[]
    digits: number
    /** Timeframe of `bars`; new drawings remember it. */
    timeframe: Timeframe
    /** Accessible name of the chart (e.g. "XAUUSD H1 chart"). */
    label: string
    plan?: PlanLines | null
    keyLevels?: KeyLevel[]
    drawings?: Drawing[]
    tool?: ChartTool
    /** Allow creating / selecting / deleting drawings. */
    editable?: boolean
    /** CSS height (the width follows the container). */
    height?: string
    /** IANA timezone for axis labels (default: the browser's). */
    timezone?: string
  }>(),
  {
    plan: null,
    keyLevels: () => [],
    drawings: () => [],
    tool: 'cursor',
    editable: false,
    height: '360px',
    timezone: undefined,
  },
)

const emit = defineEmits<{
  'update:drawings': [Drawing[]]
  'update:tool': [ChartTool]
  /** Selected drawing id (cursor tool) — the toolbar enables "delete". */
  select: [string | null]
}>()

const { t, locale } = useI18n()
const host = ref<HTMLDivElement | null>(null)
const chart = shallowRef<IChartApi | null>(null)
const series = shallowRef<ISeriesApi<'Candlestick'> | null>(null)
let theme: ChartTheme | null = null
let primitive: DrawingsPrimitive | null = null
let priceLines: IPriceLine[] = []
let stopTheme: (() => void) | null = null

const times = computed(() => props.bars.map((b) => b.time))
const step = computed(() => {
  const n = times.value.length
  return n > 1 ? times.value[n - 1] - times.value[n - 2] : undefined
})
const selectedId = ref<string | null>(null)
const draft = shallowRef<ChartDrawing | null>(null)
/** Text tool: where the input box is shown, and the anchor it will be saved at. */
const textAt = ref<{ x: number; y: number; time: number; price: number } | null>(null)
const textValue = ref('')
const textInput = ref<HTMLInputElement | null>(null)

const num = (v: number | string) => (typeof v === 'number' ? v : Number(v))
const priceStr = (p: number) => p.toFixed(props.digits)

function toChart(d: Drawing): ChartDrawing {
  return { id: d.id, tool: d.tool, points: d.points.map((p) => ({ time: p.time, price: num(p.price) })), style: d.style, text: d.text }
}
const chartDrawings = computed(() => props.drawings.map(toChart))

const zones = computed<ChartZone[]>(() =>
  props.keyLevels
    .filter((l) => l.price_to !== null)
    .map((l) => ({ from: num(l.price), to: num(l.price_to as string), label: l.label })),
)

// ------------------------------------------------------------------ coordinates

function timeToX(time: number): number | null {
  const c = chart.value
  if (!c || times.value.length === 0) return null
  const x = c.timeScale().logicalToCoordinate(timeToLogical(times.value, time, step.value) as never)
  return x === null ? null : Number(x)
}
function priceToY(price: number): number | null {
  const y = series.value?.priceToCoordinate(price)
  return y === null || y === undefined ? null : Number(y)
}
/** Chart pane coordinates → time / price. Null outside the plot area or without data. */
function pointAt(pt: Pt | undefined): { time: number; price: number; logical: number } | null {
  const c = chart.value
  if (!pt || !c || !series.value || times.value.length === 0) return null
  const pane = c.paneSize()
  if (pt.x < 0 || pt.y < 0 || pt.x > pane.width || pt.y > pane.height) return null
  const logical = c.timeScale().coordinateToLogical(pt.x)
  const price = series.value.coordinateToPrice(pt.y)
  if (logical === null || price === null) return null
  const l = Number(logical)
  return { time: snapTime(times.value, logicalToTime(times.value, l, step.value)), price: Number(price), logical: l }
}

function measureLabel(a: { time: number; price: number }, b: { time: number; price: number }) {
  const m = measure(
    { price: a.price, logical: timeToLogical(times.value, a.time, step.value) },
    { price: b.price, logical: timeToLogical(times.value, b.time, step.value) },
  )
  const sign = m.delta > 0 ? '+' : m.delta < 0 ? MINUS : ''
  const delta = `${sign}${formatNumber(Math.abs(m.delta), props.digits)}`
  const pct = `${sign}${formatNumber(Math.abs(m.pct), 2)}%`
  return t('chart.measureLabel', { delta, pct, bars: m.bars })
}

const state = () => ({
  drawings: chartDrawings.value,
  draft: draft.value,
  selectedId: selectedId.value,
  zones: zones.value,
  theme: theme ?? readChartTheme(),
  timeToX,
  priceToY,
  measureLabel,
})

// ------------------------------------------------------------------ hit test / editing

function screenPoints(d: ChartDrawing): Pt[] | null {
  const pts: Pt[] = []
  for (const p of d.points) {
    const x = timeToX(p.time)
    const y = priceToY(p.price)
    if (x === null || y === null) return null
    pts.push({ x, y })
  }
  return pts
}

function hitTest(p: Pt): string | null {
  const width = host.value?.clientWidth ?? 0
  let best: { id: string; dist: number } | null = null
  for (const d of chartDrawings.value) {
    const pts = screenPoints(d)
    if (!pts) continue
    const [a, b] = pts
    let dist = Infinity
    if (d.tool === 'horizontal') dist = Math.abs(p.y - a.y)
    else if (d.tool === 'trendline' && b) dist = distanceToSegment(p, a, b)
    else if (d.tool === 'ray' && b) dist = distanceToSegment(p, a, rayEnd(a, b, width), true)
    // Inside a box counts as 5px away, so a line drawn over it is picked first.
    else if ((d.tool === 'rectangle' || d.tool === 'measure') && b) dist = Math.min(distanceToRectEdge(p, a, b), insideRect(p, a, b) ? 5 : Infinity)
    else if (d.tool === 'text') dist = insideRect(p, { x: a.x, y: a.y - 16 }, { x: a.x + 8 * d.text.length, y: a.y }, 4) ? 0 : Infinity
    if (dist <= 6 && (!best || dist < best.dist)) best = { id: d.id, dist }
  }
  return best?.id ?? null
}

function select(id: string | null) {
  selectedId.value = id
  emit('select', id)
  primitive?.update()
}

function newId() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `d-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function commit(d: ChartDrawing) {
  const out: Drawing = {
    id: d.id,
    tool: d.tool,
    timeframe: props.timeframe,
    points: d.points.map((p) => ({ time: p.time, price: priceStr(p.price) })),
    style: d.style,
    text: d.text,
  }
  emit('update:drawings', [...props.drawings, out])
  emit('update:tool', 'cursor')
  draft.value = null
  select(d.id)
}

function startDrawing(tool: DrawingTool, at: { time: number; price: number }) {
  const style = { color: tool === 'horizontal' ? 'warning' : 'brand', line: 'solid', width: tool === 'horizontal' ? 1 : 2 } as const
  const d: ChartDrawing = { id: newId(), tool, points: [at], style: { ...style }, text: '' }
  if (POINTS_PER_TOOL[tool] === 1) {
    commit(d)
    return
  }
  draft.value = { ...d, points: [at, at] }
}

/**
 * Taps on the plot are read from pointer events (not the chart's click event, which turns a quick
 * second click into a double click and drops it). A tap = press + release within 6px.
 */
let press: { x: number; y: number } | null = null
function local(e: PointerEvent): Pt {
  const r = host.value!.getBoundingClientRect()
  return { x: e.clientX - r.left, y: e.clientY - r.top }
}
function onPointerDown(e: PointerEvent) {
  if (!e.isPrimary || e.button > 0) return
  press = local(e)
}
function onPointerUp(e: PointerEvent) {
  if (!press || !e.isPrimary) return
  const p = local(e)
  const tap = Math.hypot(p.x - press.x, p.y - press.y) < 6
  press = null
  if (tap) onTap(p)
}

function onTap(pt: Pt) {
  if (!props.editable) return
  const at = pointAt(pt)
  if (!at) return
  const tool = props.tool
  if (draft.value) {
    commit({ ...draft.value, points: [draft.value.points[0], { time: at.time, price: at.price }] })
    return
  }
  if (tool === 'cursor') {
    select(hitTest(pt))
    return
  }
  if (tool === 'text') {
    textAt.value = { x: pt.x, y: pt.y, time: at.time, price: at.price }
    textValue.value = ''
    void nextTick(() => textInput.value?.focus())
    return
  }
  startDrawing(tool, at)
}

function onMove(param: MouseEventParams<Time>) {
  if (!draft.value || !param.point) return
  const at = pointAt({ x: Number(param.point.x), y: Number(param.point.y) })
  if (!at) return
  draft.value = { ...draft.value, points: [draft.value.points[0], { time: at.time, price: at.price }] }
  primitive?.update()
}

function commitText() {
  const at = textAt.value
  const text = textValue.value.trim()
  textAt.value = null
  if (!at || !text) return
  commit({
    id: newId(),
    tool: 'text',
    points: [{ time: at.time, price: at.price }],
    style: { color: 'ink', line: 'solid', width: 1 },
    text: text.slice(0, 200),
  })
}

function cancel() {
  draft.value = null
  textAt.value = null
  if (props.tool !== 'cursor') emit('update:tool', 'cursor')
  primitive?.update()
}

/** Remove the selected drawing (toolbar "delete" / Delete key). */
function deleteSelected() {
  if (!selectedId.value) return
  emit(
    'update:drawings',
    props.drawings.filter((d) => d.id !== selectedId.value),
  )
  select(null)
}

function onKey(e: KeyboardEvent) {
  if (!props.editable) return
  if (e.key === 'Escape') cancel()
  else if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId.value && !textAt.value) {
    e.preventDefault()
    deleteSelected()
  }
}

// ------------------------------------------------------------------ chart setup

function priceFmt() {
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: props.digits, maximumFractionDigits: props.digits })
}

function chartOptions(th: ChartTheme) {
  const fmt = new Intl.DateTimeFormat(locale.value === 'th' ? 'th-TH-u-ca-gregory' : 'en-GB', {
    timeZone: props.timezone,
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
  // Day / month / year marks show the date, intraday marks the local time.
  const part = (tm: Time, opts: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat(locale.value === 'th' ? 'th-TH-u-ca-gregory' : 'en-GB', { timeZone: props.timezone, ...opts }).format(
      new Date(Number(tm) * 1000),
    )
  const tick = (tm: Time, type: TickMarkType) => {
    if (type === TickMarkType.Year) return part(tm, { year: 'numeric' })
    if (type === TickMarkType.Month) return part(tm, { month: 'short' })
    if (type === TickMarkType.DayOfMonth) return part(tm, { day: 'numeric', month: 'short' })
    return part(tm, { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  return {
    autoSize: true,
    layout: {
      background: { color: th.surface },
      textColor: th.inkSubtle,
      fontFamily: th.font,
      fontSize: 11,
    },
    grid: { vertLines: { color: th.grid }, horzLines: { color: th.grid } },
    rightPriceScale: { borderColor: th.border },
    timeScale: { borderColor: th.border, timeVisible: true, secondsVisible: false, tickMarkFormatter: tick },
    crosshair: { mode: CrosshairMode.Normal },
    localization: {
      timeFormatter: (tm: Time) => fmt.format(new Date(Number(tm) * 1000)),
      // "4,366.00" — thousands separators like the rest of the app.
      priceFormatter: (p: number) => priceFmt().format(p),
    },
    // Pinch zoom + drag pan on touch screens (F-19 AC4).
    handleScale: { pinch: true, mouseWheel: true, axisPressedMouseMove: true },
    handleScroll: { horzTouchDrag: true, vertTouchDrag: false, pressedMouseMove: true, mouseWheel: true },
  }
}

function seriesOptions(th: ChartTheme) {
  return {
    upColor: th.up,
    downColor: th.down,
    wickUpColor: th.up,
    wickDownColor: th.down,
    borderVisible: false,
    priceLineVisible: false,
    priceFormat: { type: 'price' as const, precision: props.digits, minMove: 1 / 10 ** props.digits },
    // Keep plan / key levels in view when autoscaling.
    autoscaleInfoProvider: (original: () => AutoscaleInfo | null) => {
      const res = original()
      const extra = levelPrices()
      if (!res || !res.priceRange || extra.length === 0) return res
      return {
        ...res,
        priceRange: {
          minValue: Math.min(res.priceRange.minValue, ...extra),
          maxValue: Math.max(res.priceRange.maxValue, ...extra),
        },
      }
    },
  }
}

function levelPrices(): number[] {
  const out: number[] = []
  if (props.plan) out.push(num(props.plan.entry), num(props.plan.stopLoss), ...props.plan.takeProfits.map(num))
  for (const l of props.keyLevels) {
    out.push(num(l.price))
    if (l.price_to !== null) out.push(num(l.price_to))
  }
  return out.filter((n) => Number.isFinite(n) && n > 0)
}

function drawPriceLines() {
  const s = series.value
  const th = theme
  if (!s || !th) return
  for (const line of priceLines) s.removePriceLine(line)
  priceLines = []
  const add = (price: number, color: string, title: string, style: LineStyle, width: 1 | 2) => {
    if (!Number.isFinite(price) || price <= 0) return
    priceLines.push(
      s.createPriceLine({
        price,
        color,
        lineWidth: width,
        lineStyle: style,
        axisLabelVisible: true,
        axisLabelColor: color,
        axisLabelTextColor: th.inkInverse,
        title,
      }),
    )
  }
  for (const l of props.keyLevels) {
    if (l.price_to === null) add(num(l.price), levelColor(th, l.kind), l.label.slice(0, 18), LineStyle.Solid, 1)
  }
  const plan = props.plan
  if (plan) {
    add(num(plan.entry), th.plan, t('chart.entryShort'), LineStyle.Dashed, 2)
    add(num(plan.stopLoss), th.loss, t('chart.slShort'), LineStyle.Dashed, 2)
    plan.takeProfits.forEach((tp, i) =>
      add(num(tp), th.profit, plan.takeProfits.length > 1 ? t('chart.tpShortN', { n: i + 1 }) : t('chart.tpShort'), LineStyle.Dashed, 2),
    )
  }
}

let fitted = false
function setData() {
  const s = series.value
  if (!s) return
  s.setData(
    props.bars.map((b) => ({
      time: b.time as UTCTimestamp,
      open: num(b.open),
      high: num(b.high),
      low: num(b.low),
      close: num(b.close),
    })),
  )
  if (!fitted && props.bars.length) {
    // Show the latest ~120 bars, like a trader's default view.
    const n = props.bars.length
    chart.value?.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 120), to: n + 6 })
    fitted = true
  }
  primitive?.update()
}

function applyTheme() {
  theme = readChartTheme()
  chart.value?.applyOptions(chartOptions(theme))
  series.value?.applyOptions(seriesOptions(theme))
  drawPriceLines()
  primitive?.update()
}

onMounted(() => {
  if (!host.value) return
  theme = readChartTheme()
  const c = createChart(host.value, chartOptions(theme))
  const s = c.addSeries(CandlestickSeries, seriesOptions(theme))
  chart.value = c
  series.value = s
  primitive = new DrawingsPrimitive(state)
  s.attachPrimitive(primitive)
  c.subscribeCrosshairMove(onMove)
  setData()
  drawPriceLines()
  stopTheme = onThemeChange(applyTheme)
})

onBeforeUnmount(() => {
  stopTheme?.()
  chart.value?.unsubscribeCrosshairMove(onMove)
  chart.value?.remove()
  chart.value = null
  series.value = null
})

watch(() => props.bars, setData)
watch(
  () => props.digits,
  () => {
    chart.value?.applyOptions(chartOptions(theme ?? readChartTheme()))
    series.value?.applyOptions(seriesOptions(theme ?? readChartTheme()))
  },
)
watch(() => [props.plan, props.keyLevels], drawPriceLines, { deep: true })
watch(() => [props.drawings, props.keyLevels], () => primitive?.update(), { deep: true })
watch(
  () => props.tool,
  (tool) => {
    if (tool !== 'cursor') select(null)
    draft.value = null
    textAt.value = null
    primitive?.update()
  },
)
watch(locale, () => {
  chart.value?.applyOptions(chartOptions(theme ?? readChartTheme()))
  drawPriceLines()
})

/** Scroll so the latest bars are visible. */
function scrollToLatest() {
  chart.value?.timeScale().scrollToRealTime()
}

defineExpose({ deleteSelected, selectedId, scrollToLatest })
</script>

<template>
  <div
    class="relative w-full select-none overflow-hidden rounded-control"
    :class="{ 'cursor-crosshair': editable && tool !== 'cursor' }"
    :style="{ height }"
    role="img"
    :aria-label="label"
    tabindex="0"
    @keydown="onKey"
  >
    <div
      ref="host"
      class="absolute inset-0"
      data-testid="trade-chart"
      @pointerdown.capture="onPointerDown"
      @pointerup.capture="onPointerUp"
    />
    <form
      v-if="textAt"
      class="absolute z-10"
      :style="{ left: `${textAt.x}px`, top: `${Math.max(0, textAt.y - 36)}px` }"
      @submit.prevent="commitText"
    >
      <input
        ref="textInput"
        v-model="textValue"
        maxlength="200"
        class="tt-input h-8 w-48 text-sm"
        :aria-label="t('chart.textPrompt')"
        :placeholder="t('chart.textPrompt')"
        @keydown.esc.stop.prevent="cancel"
        @blur="commitText"
      />
    </form>
  </div>
</template>
