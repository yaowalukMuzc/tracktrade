import { ApiError } from '@/api/client'

const KNOWN = new Set([
  'stop_loss_wrong_side',
  'take_profit_wrong_side',
  'take_profit_pct_over_100',
  'conversion_rate_required',
  'setup_archived',
  'account_archived',
  'symbol_mismatch',
  'plan_not_draft',
  'plan_not_revisable',
  'plan_closed',
  'invalid_transition',
  'reason_required',
  'no_changes',
  'risk_pct_after_entry',
  'valid_until_passed',
  'unknown_emotion_tag',
  'checklist_incomplete',
])

/** ApiError → i18n key under `plans.errors` (codes listed at the bottom of api/plans.ts). */
export function planErrorKey(e: unknown): string {
  if (!(e instanceof ApiError)) return 'plans.errors.network'
  if (KNOWN.has(e.code)) return `plans.errors.${e.code}`
  if (e.code === 'validation_error' || e.status === 422) return 'plans.errors.validation'
  if (e.status === 0) return 'plans.errors.network'
  return 'plans.errors.generic'
}

/** Required items the server says are missing (422 checklist_incomplete → details.missing[{id,text}]). */
export function missingFromError(e: unknown): string[] | null {
  if (!(e instanceof ApiError) || e.code !== 'checklist_incomplete') return null
  const d = e.details as { missing?: { id: string }[] } | null
  return (d?.missing ?? []).map((m) => m.id)
}
