<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import TradeChart, { type PlanLines } from '@/components/chart/TradeChart.vue'
import { useOhlc } from '@/components/chart/useOhlc'
import TtButton from '@/components/ui/TtButton.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import type { Timeframe } from '@/api/playbook'

// "Preview บนกราฟ" (screens/web/05-WPlan.png): read-only chart with the plan's EN / SL / TP lines, M15 / H1.
const props = defineProps<{ symbolId: string | null; symbolCode: string; digits: number; plan: PlanLines | null }>()
const { t } = useI18n()
const TFS: Timeframe[] = ['M15', 'H1']
const tf = ref<Timeframe>('M15')
const { data, loading, error, reload } = useOhlc(toRef(props, 'symbolId'), tf, 200)
const digits = computed(() => data.value?.digits ?? props.digits)
</script>

<template>
  <section class="overflow-hidden rounded-lg border border-border bg-surface" data-testid="plan-chart">
    <div class="flex items-center gap-1.5 border-b border-border px-2.5 py-2">
      <h2 class="m-0 text-[14px] font-semibold leading-5">{{ t('plans.sections.preview') }}</h2>
      <span class="flex-1" />
      <div class="tt-row !gap-1.5" role="group" :aria-label="t('chart.timeframes')">
        <TtChip v-for="x in TFS" :key="x" size="sm" :selected="tf === x" @click="tf = x">{{ x }}</TtChip>
      </div>
    </div>
    <div v-if="error" class="flex h-[320px] flex-col items-center justify-center gap-3 text-body-sm text-ink-muted">
      {{ t('chart.loadError') }}
      <TtButton size="sm" @click="reload">{{ t('chart.retry') }}</TtButton>
    </div>
    <div v-else-if="!data && loading" class="h-[320px] p-4"><TtSkeleton :lines="1" height="288px" /></div>
    <TradeChart
      v-else-if="data"
      :bars="data.bars"
      :digits="digits"
      :timeframe="tf"
      :label="`${symbolCode} ${tf}`"
      :plan="plan"
      height="320px"
    />
    <p v-if="data?.source === 'mock'" class="m-0 border-t border-border px-3 py-1.5 text-caption text-ink-subtle">{{ t('chart.sourceMock') }}</p>
  </section>
</template>
