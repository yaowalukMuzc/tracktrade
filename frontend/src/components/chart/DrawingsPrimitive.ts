import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  PrimitivePaneViewZOrder,
  SeriesAttachedParameter,
  Time,
} from 'lightweight-charts'
import type { CanvasRenderingTarget2D } from 'fancy-canvas'
import type { DrawingStyle, DrawingTool } from '@/api/analysis'
import { drawingColor, type ChartTheme } from '@/lib/chartTheme'
import { rayEnd, type Pt } from './geometry'

/** A drawing in chart terms (numbers, not decimal strings). */
export interface ChartDrawing {
  id: string
  tool: DrawingTool
  points: { time: number; price: number }[]
  style: DrawingStyle
  text: string
}

/** Price zone from the analysis' key levels (price … price_to). */
export interface ChartZone {
  from: number
  to: number
  label: string
}

export interface DrawingsState {
  drawings: ChartDrawing[]
  /** Drawing being created (second point follows the cursor). */
  draft: ChartDrawing | null
  selectedId: string | null
  zones: ChartZone[]
  theme: ChartTheme
  /** time → x in media pixels (null when off-chart / no data). */
  timeToX: (time: number) => number | null
  priceToY: (price: number) => number | null
  /** "+12.40 (+0.28%) · 8 bars" */
  measureLabel: (a: { time: number; price: number }, b: { time: number; price: number }) => string
}

const DASH: Record<DrawingStyle['line'], number[]> = { solid: [], dashed: [6, 4], dotted: [2, 3] }
const ZONE_ALPHA = 0.12

class Renderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly state: DrawingsState,
    private readonly layer: 'background' | 'foreground',
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const s = this.state
      if (this.layer === 'background') {
        for (const z of s.zones) this.zone(ctx, z, mediaSize.width)
        return
      }
      for (const z of s.zones) this.zoneLabel(ctx, z)
      for (const d of s.drawings) this.drawing(ctx, d, mediaSize.width, d.id === s.selectedId)
      if (s.draft) this.drawing(ctx, s.draft, mediaSize.width, true)
    })
  }

  private zone(ctx: CanvasRenderingContext2D, z: ChartZone, width: number) {
    const { theme, priceToY } = this.state
    const y1 = priceToY(z.from)
    const y2 = priceToY(z.to)
    if (y1 === null || y2 === null) return
    const top = Math.min(y1, y2)
    const h = Math.max(1, Math.abs(y2 - y1))
    ctx.save()
    ctx.globalAlpha = ZONE_ALPHA
    ctx.fillStyle = theme.brand
    ctx.fillRect(0, top, width, h)
    ctx.globalAlpha = 1
    ctx.strokeStyle = theme.brand
    ctx.lineWidth = 1
    ctx.strokeRect(0.5, top + 0.5, width - 1, h)
    ctx.restore()
  }

  /** Zone name on a surface chip above the candles so it stays readable. */
  private zoneLabel(ctx: CanvasRenderingContext2D, z: ChartZone) {
    const { theme, priceToY } = this.state
    const y1 = priceToY(z.from)
    const y2 = priceToY(z.to)
    if (!z.label || y1 === null || y2 === null) return
    const top = Math.min(y1, y2)
    ctx.save()
    ctx.font = `500 11px ${theme.font}`
    const w = ctx.measureText(z.label).width + 8
    ctx.fillStyle = theme.surface
    ctx.fillRect(4, top + 2, w, 16)
    ctx.fillStyle = theme.brand
    ctx.textBaseline = 'middle'
    ctx.fillText(z.label, 8, top + 10)
    ctx.restore()
  }

  private drawing(ctx: CanvasRenderingContext2D, d: ChartDrawing, width: number, selected: boolean) {
    const { theme, timeToX, priceToY } = this.state
    const pts: Pt[] = []
    for (const p of d.points) {
      const x = timeToX(p.time)
      const y = priceToY(p.price)
      if (x === null || y === null) return
      pts.push({ x, y })
    }
    if (pts.length === 0) return
    const color = drawingColor(theme, d.style.color)
    ctx.save()
    ctx.strokeStyle = color
    ctx.fillStyle = color
    ctx.lineWidth = d.style.width + (selected ? 0.5 : 0)
    ctx.setLineDash(DASH[d.style.line])
    const [a, b] = pts
    switch (d.tool) {
      case 'trendline':
        if (b) this.line(ctx, a, b)
        break
      case 'ray':
        if (b) this.line(ctx, a, rayEnd(a, b, width))
        break
      case 'horizontal':
        this.line(ctx, { x: 0, y: a.y }, { x: width, y: a.y })
        break
      case 'rectangle':
        if (b) {
          ctx.globalAlpha = ZONE_ALPHA
          ctx.fillRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y))
          ctx.globalAlpha = 1
          ctx.strokeRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y))
        }
        break
      case 'text':
        ctx.font = `600 12px ${theme.font}`
        ctx.textBaseline = 'bottom'
        ctx.fillText(d.text, a.x, a.y)
        break
      case 'measure':
        if (b) this.measure(ctx, d, a, b)
        break
    }
    if (selected) {
      ctx.setLineDash([])
      ctx.fillStyle = theme.surface
      ctx.lineWidth = 1.5
      for (const p of d.tool === 'horizontal' ? [a] : pts) {
        ctx.beginPath()
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
      }
    }
    ctx.restore()
  }

  private line(ctx: CanvasRenderingContext2D, a: Pt, b: Pt) {
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    ctx.stroke()
  }

  private measure(ctx: CanvasRenderingContext2D, d: ChartDrawing, a: Pt, b: Pt) {
    const { theme } = this.state
    const up = d.points[1].price >= d.points[0].price
    const color = up ? theme.profit : theme.loss
    ctx.setLineDash([])
    ctx.strokeStyle = color
    ctx.fillStyle = color
    ctx.globalAlpha = ZONE_ALPHA
    ctx.fillRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y))
    ctx.globalAlpha = 1
    ctx.lineWidth = 1
    this.line(ctx, { x: a.x, y: a.y }, { x: a.x, y: b.y })
    this.line(ctx, { x: a.x, y: b.y }, { x: b.x, y: b.y })
    const label = this.state.measureLabel(d.points[0], d.points[1])
    ctx.font = `600 11px ${theme.font}`
    const w = ctx.measureText(label).width + 12
    const x = (a.x + b.x) / 2 - w / 2
    const y = up ? Math.min(a.y, b.y) - 24 : Math.max(a.y, b.y) + 4
    ctx.fillRect(x, y, w, 20)
    ctx.fillStyle = theme.inkInverse
    ctx.textBaseline = 'middle'
    ctx.fillText(label, x + 6, y + 10)
  }
}

class View implements IPrimitivePaneView {
  constructor(
    private readonly state: () => DrawingsState,
    private readonly layer: 'background' | 'foreground',
  ) {}
  zOrder(): PrimitivePaneViewZOrder {
    return this.layer === 'background' ? 'bottom' : 'top'
  }
  renderer(): IPrimitivePaneRenderer {
    return new Renderer(this.state(), this.layer)
  }
}

/** Renders zones (behind candles) and drawings (on top) from a state getter. */
export class DrawingsPrimitive implements ISeriesPrimitive<Time> {
  private requestUpdate: (() => void) | null = null
  private readonly views: View[]

  constructor(state: () => DrawingsState) {
    this.views = [new View(state, 'background'), new View(state, 'foreground')]
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this.requestUpdate = param.requestUpdate
  }

  detached(): void {
    this.requestUpdate = null
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views
  }

  /** Redraw after the state changed. */
  update(): void {
    this.requestUpdate?.()
  }
}
