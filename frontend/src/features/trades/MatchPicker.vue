<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import type { MatchCandidate, PositionSummary } from '@/api/positions'
import type { Locale } from '@/i18n'
import { UNPLANNED, entryKey, lot, pctText, price, timeHm } from './model'

// Trade summary + plan options + "no plan" (screens/web/06-WTrades.png modal, screens/mobile/12-MatchQueue.png).
// `choice` = plan id, or UNPLANNED. The parent owns the buttons (modal footer / sticky bar).
const props = defineProps<{
  position: PositionSummary
  firstEntry: string
  candidates: MatchCandidate[]
  tz: string
  /** Mobile: 3-column summary, solid "Locked" badge, the longer "recommended" label. */
  compact?: boolean
  /** Mobile lays the summary (inside the trade card) and the options (below it) out separately. */
  part?: 'all' | 'summary' | 'options'
}>()
const choice = defineModel<string>({ required: true })
const { t, locale } = useI18n()
const l = computed(() => locale.value as Locale)

const options = computed(() =>
  props.candidates.map((c) => {
    const reasons = [c.within_time ? t('trades.match.inTime') : t('trades.match.outOfTime')]
    if (!c.within_price) reasons.push(t('trades.match.outOfRange'))
    return {
      id: c.plan.id,
      title: t('trades.match.option', {
        label: c.plan.scenario_label,
        entry: t(entryKey(c, props.position.direction)),
        price: price(c.plan.entry_price, props.position.digits),
      }),
      locked: c.plan.locked_at ? t('trades.match.locked', { time: timeHm(c.plan.locked_at, props.tz, l.value) }) : t('trades.match.notLocked'),
      sub: `${t('trades.match.distance', { d: price(c.distance, props.position.digits), pct: pctText(c.pct_of_sl) })} · ${reasons.join(' · ')}`,
      recommended: c.recommended,
    }
  }),
)
</script>

<template>
  <div class="flex flex-col gap-3">
    <div v-if="part !== 'options'" class="tt-calc" :class="compact ? 'grid-cols-3' : 'grid-cols-4'">
      <div v-if="!compact">
        <span>{{ position.symbol_code }}</span>
        <b :class="position.direction === 'long' ? 'text-profit-ink' : 'text-loss-ink'">{{ t(`trading.direction.${position.direction}`) }}</b>
      </div>
      <div>
        <span>{{ t('trades.match.fill') }}</span>
        <b>{{ price(firstEntry, position.digits) }}</b>
      </div>
      <div>
        <span>{{ t('trades.match.lot') }}</span>
        <b>{{ lot(position.total_lot) }}</b>
      </div>
      <div>
        <span>{{ t('trades.match.time') }}</span>
        <b>{{ timeHm(position.opened_at, tz, l) }}</b>
      </div>
    </div>

    <div v-if="compact && part !== 'summary'" class="text-overline uppercase text-ink-muted">{{ t('trades.match.candidates') }}</div>
    <div v-if="part !== 'summary'" role="radiogroup" :aria-label="t('trades.match.candidates')" class="flex flex-col gap-3">
      <label v-for="o in options" :key="o.id" class="opt" :class="{ 'opt--on': choice === o.id }" data-testid="match-option">
        <input v-model="choice" type="radio" name="match-plan" :value="o.id" class="opt__radio" />
        <span class="flex min-w-0 flex-1 flex-col gap-0.5">
          <span class="flex flex-wrap items-center gap-2">
            <span class="text-body font-semibold text-ink">{{ o.title }}</span>
            <TtBadge :variant="compact ? 'solid' : 'neutral'">{{ o.locked }}</TtBadge>
          </span>
          <span class="text-body-sm text-ink-muted">{{ o.sub }}</span>
          <TtBadge v-if="o.recommended && compact" variant="profit" class="mt-1 self-start">{{ t('trades.match.recommendedLong') }}</TtBadge>
        </span>
        <TtBadge v-if="o.recommended && !compact" variant="profit" class="flex-none">{{ t('trades.match.recommended') }}</TtBadge>
      </label>

      <label class="opt" :class="{ 'opt--on': choice === UNPLANNED }" data-testid="match-option-unplanned">
        <input v-model="choice" type="radio" name="match-plan" :value="UNPLANNED" class="opt__radio" />
        <span class="flex min-w-0 flex-1 flex-col gap-0.5">
          <span class="text-body font-semibold text-ink">{{ t('trades.match.unplanned') }}</span>
          <span class="text-body-sm text-ink-muted">{{ t('trades.match.unplannedSub') }}</span>
        </span>
      </label>
    </div>
  </div>
</template>

<style scoped>
/* WTrades.dc.html .opt / .opt--on — a selected option gets a 2px brand-700 frame and the brand-50 wash. */
.opt {
  display: flex; gap: 12px; align-items: flex-start; padding: 14px 16px;
  border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); cursor: pointer;
}
.opt:hover { border-color: var(--border-strong); }
.opt--on, .opt--on:hover { border-color: var(--brand-700); outline: 1px solid var(--brand-700); background: var(--brand-50); }
.opt:has(:focus-visible) { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.opt__radio { width: 20px; height: 20px; margin-top: 2px; flex: none; accent-color: var(--brand-700); }
</style>
