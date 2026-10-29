import type { AccountRisk, Bias, PnlToday, Today } from '@/api/analysis'
import { TIMEFRAMES, type Timeframe } from '@/api/playbook'
import type { BadgeVariant } from '@/components/ui/TtBadge.vue'
import type { IconName } from '@/lib/icons'
import type { PlanBrief } from '@/api/plans'
import { isOpenPlan } from '@/features/plans/status'

// Pure helpers behind the Today page (screens/web/03-WToday.png). Nothing here invents numbers:
// P/L is empty until trades exist (Phase 4) and shows $0.00 / 0 trades; adherence is null until Phase 6.

export interface PnlKpi {
  currency: string
  amount: number
  r: number
  trades: number
  /** Other currencies with P/L today (can't be summed into one amount). */
  otherCurrencies: number
}

export interface DailyLossKpi {
  /** Loss used today as % of the balance. */
  usedPct: number
  /** Limit as % of the balance and as money. */
  limitPct: number
  limitAmount: number
  /** used / limit, 0–100, for the meter. */
  usage: number
  currency: string
  /** The account shown when several are aggregated (the one closest to its limit). */
  accountName: string | null
}

export interface TodayKpis {
  pnl: PnlKpi
  trades: { used: number; limit: number }
  dailyLoss: DailyLossKpi | null
  adherence: number | null
  goal: number | null
}

const n = (v: string | number | null | undefined) => (v == null ? 0 : Number(v))

/** P/L of the most-used currency (by account count), summed per currency by the API. */
export function pnlKpi(pnl: PnlToday[], risk: AccountRisk[]): PnlKpi {
  const counts = new Map<string, number>()
  for (const r of risk) counts.set(r.currency, (counts.get(r.currency) ?? 0) + 1)
  const main = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? pnl[0]?.currency ?? 'USD'
  const row = pnl.find((p) => p.currency === main) ?? pnl[0]
  if (!row) return { currency: main, amount: 0, r: 0, trades: 0, otherCurrencies: 0 }
  return {
    currency: row.currency,
    amount: n(row.amount),
    r: n(row.r),
    // Trade counts are currency independent, so they add up.
    trades: pnl.reduce((s, p) => s + p.trades, 0),
    otherCurrencies: pnl.filter((p) => p.currency !== row.currency && n(p.amount) !== 0).length,
  }
}

/**
 * Daily loss is a per-account limit, so across accounts the page shows the account closest to its
 * limit (ties: the first) rather than a sum of unrelated limits.
 */
export function dailyLossKpi(risk: AccountRisk[]): DailyLossKpi | null {
  if (!risk.length) return null
  const usage = (r: AccountRisk) => (n(r.daily_loss.limit) > 0 ? n(r.daily_loss.used) / n(r.daily_loss.limit) : 0)
  const worst = risk.reduce((a, b) => (usage(b) > usage(a) ? b : a))
  const balance = n(worst.balance)
  const pct = (v: number) => (balance > 0 ? (v / balance) * 100 : 0)
  return {
    usedPct: pct(n(worst.daily_loss.used)),
    limitPct: pct(n(worst.daily_loss.limit)),
    limitAmount: n(worst.daily_loss.limit),
    usage: Math.min(100, usage(worst) * 100),
    currency: worst.currency,
    accountName: risk.length > 1 ? worst.name : null,
  }
}

export function todayKpis(today: Pick<Today, 'pnl' | 'risk' | 'adherence_week' | 'goal_adherence'>): TodayKpis {
  return {
    pnl: pnlKpi(today.pnl, today.risk),
    trades: today.risk.reduce(
      (s, r) => ({ used: s.used + n(r.trades_today.used), limit: s.limit + n(r.trades_today.limit) }),
      { used: 0, limit: 0 },
    ),
    dailyLoss: dailyLossKpi(today.risk),
    adherence: today.adherence_week == null ? null : n(today.adherence_week),
    goal: today.goal_adherence == null ? null : n(today.goal_adherence),
  }
}

/** Price with the symbol's digits: `4,387.52`, `1.08420`. */
export function formatPrice(value: string | number, digits: number) {
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value))
}

/** The final target — the row shows one TP (screens/source/WToday.dc.html). */
export const lastTakeProfit = (p: PlanBrief) => p.take_profits[p.take_profits.length - 1]?.price ?? null

/**
 * Analyses where the action is come first: most open plans (draft / locked / triggered), then the API
 * order (latest edit first). The first one is the analysis the desktop card opens on.
 */
export function rankAnalyses<A extends { id: string }>(analyses: A[], plans: PlanBrief[]): A[] {
  const open = (id: string) => plans.filter((p) => p.analysis_id === id && isOpenPlan(p.status)).length
  return analyses.map((a, i) => ({ a, i, o: open(a.id) })).sort((x, y) => y.o - x.o || x.i - y.i).map((x) => x.a)
}

/** Plans grouped by symbol in the order of the ranked analyses (others after), then scenario label A, B, … */
export function sortPlans(plans: PlanBrief[], symbolOrder: string[] = []) {
  const rank = (code: string) => {
    const i = symbolOrder.indexOf(code)
    return i === -1 ? symbolOrder.length : i
  }
  return [...plans].sort(
    (a, b) =>
      rank(a.symbol_code) - rank(b.symbol_code) ||
      a.symbol_code.localeCompare(b.symbol_code) ||
      a.scenario_label.localeCompare(b.scenario_label),
  )
}

/** Total of the "to do" card. */
export const todoTotal = (todo: Today['todo']) => todo.pending_match + todo.pending_review + todo.inbox

/** HTF bias badge: direction is meaning, so bull / bear use profit / loss (screens/source/WToday.dc.html). */
export function biasBadge(bias: Bias): { variant: BadgeVariant; icon?: IconName } {
  if (bias === 'bull') return { variant: 'profit', icon: 'up' }
  if (bias === 'bear') return { variant: 'loss', icon: 'down' }
  return { variant: 'neutral' }
}

/** Timeframes offered on the Today chart: the analysis' own plus the H1 default, in TIMEFRAMES order. */
export function chartTimeframes(own: Timeframe[], fallback: Timeframe = 'H1'): Timeframe[] {
  const set = new Set<Timeframe>([...own, fallback])
  return TIMEFRAMES.filter((tf) => set.has(tf))
}
