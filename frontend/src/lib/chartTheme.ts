import type { DrawingColor } from '@/api/analysis'

/**
 * Chart colours come from the design tokens at runtime (canvas can't use CSS variables,
 * PLAN §5 "lib/chartTheme.ts"). Read again whenever `data-theme` changes.
 */
export interface ChartTheme {
  up: string
  down: string
  grid: string
  plan: string
  actual: string
  brand: string
  brandStrong: string
  profit: string
  loss: string
  warning: string
  ink: string
  inkMuted: string
  inkSubtle: string
  inkInverse: string
  surface: string
  border: string
  font: string
}

const VARS: Record<keyof Omit<ChartTheme, 'font'>, string> = {
  up: '--chart-up',
  down: '--chart-down',
  grid: '--chart-grid',
  plan: '--chart-plan',
  actual: '--chart-actual',
  brand: '--brand-500',
  brandStrong: '--brand-700',
  profit: '--profit',
  loss: '--loss',
  warning: '--warning',
  ink: '--ink',
  inkMuted: '--ink-muted',
  inkSubtle: '--ink-subtle',
  inkInverse: '--ink-inverse',
  surface: '--surface',
  border: '--border',
}

export function readChartTheme(root: HTMLElement = document.documentElement): ChartTheme {
  const css = getComputedStyle(root)
  const read = (name: string) => css.getPropertyValue(name).trim()
  const theme = Object.fromEntries(Object.entries(VARS).map(([k, v]) => [k, read(v)])) as Omit<ChartTheme, 'font'>
  return { ...theme, font: read('--font-sans') || 'Inter, Anuphan, sans-serif' }
}

/** Drawing colour token → theme colour. */
export function drawingColor(theme: ChartTheme, color: DrawingColor): string {
  switch (color) {
    case 'plan':
      return theme.plan
    case 'profit':
      return theme.profit
    case 'loss':
      return theme.loss
    case 'warning':
      return theme.warning
    case 'ink':
      return theme.inkMuted
    default:
      return theme.brand
  }
}

/** Key level kind → line colour; matches the markers in the analysis' key-level list. */
export function levelColor(theme: ChartTheme, kind: string): string {
  switch (kind) {
    case 'support':
      return theme.warning
    case 'resistance':
      return theme.inkMuted
    case 'liquidity':
      return theme.brandStrong
    case 'zone':
      return theme.brand
    default:
      return theme.inkSubtle
  }
}

/** Calls `cb` when the `data-theme` attribute on <html> changes. Returns the disconnect function. */
export function onThemeChange(cb: () => void): () => void {
  const observer = new MutationObserver(cb)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class', 'style'] })
  return () => observer.disconnect()
}
