<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import type { AnalysisSummary } from '@/api/analysis'
import { biasBadge, chartTimeframes } from './model'

// Mobile "Analysis วันนี้" cards (screens/source/Today.dc.html) — each opens the analysis.
defineProps<{ analyses: AnalysisSummary[] }>()
const { t } = useI18n()

const htf = (a: AnalysisSummary) => chartTimeframes(a.timeframes, a.timeframes[0]).at(-1) ?? t('today.analysis.htf')
const tfs = (a: AnalysisSummary) => chartTimeframes(a.timeframes, a.timeframes[0]).reverse().join(' · ')
</script>

<template>
  <RouterLink
    v-for="a in analyses"
    :key="a.id"
    :to="`/analysis/${a.id}`"
    class="tt-card flex flex-col gap-2 text-ink no-underline"
    data-testid="today-analysis"
  >
    <div class="flex items-center gap-2">
      <span class="text-[15px] font-semibold">{{ a.symbol_code }}</span>
      <TtBadge v-bind="biasBadge(a.htf_bias)">{{ htf(a) }} {{ t(`trading.bias.${a.htf_bias}`) }}</TtBadge>
      <span class="flex-1" />
      <span class="text-caption text-ink-muted">{{ t('today.analysis.confidence', { n: a.confidence }) }}</span>
    </div>
    <p class="m-0 line-clamp-2 text-body-sm text-ink-muted">{{ a.narrative_text || t('today.analysis.noNarrative') }}</p>
    <div class="tt-row">
      <TtBadge v-if="a.timeframes.length" variant="outline">{{ tfs(a) }}</TtBadge>
      <TtBadge v-if="a.session" variant="outline">{{ t(`trading.session.${a.session}`) }}</TtBadge>
      <TtBadge>{{ t('today.analysis.plans', { n: a.plan_count }, a.plan_count) }}</TtBadge>
    </div>
  </RouterLink>
</template>
