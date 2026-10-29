import type { BadgeVariant } from '@/components/ui/TtBadge.vue'
import type { Direction, PlanStatus } from '@/api/plans'

/** Plan status → Badge variant (shared by Today, Analysis and the plan page) — design-system/components/Badge.md. */
export const PLAN_STATUS_BADGE: Record<PlanStatus, BadgeVariant> = {
  draft: 'neutral',
  locked: 'solid',
  triggered: 'brand',
  closed: 'outline',
  skipped: 'warning',
  missed: 'warning',
  invalidated: 'loss',
  expired: 'neutral',
}

/** Read-only end states: the form shows the values and the status reason. */
export const isTerminalPlan = (s: PlanStatus) => !isOpenPlan(s)

/** LONG / SHORT badge variant (direction always spelled out — CLAUDE.md). */
export const directionBadge = (d: Direction): BadgeVariant => (d === 'long' ? 'long' : 'short')

/** Plans that can still be acted on (lock / revise / change status). */
export const isOpenPlan = (s: PlanStatus) => s === 'draft' || s === 'locked' || s === 'triggered'

/** Short form of a sha256 for display: "7f3a…c91e". */
export const shortHash = (hash: string | null | undefined) => (hash ? `${hash.slice(0, 4)}…${hash.slice(-4)}` : '')
