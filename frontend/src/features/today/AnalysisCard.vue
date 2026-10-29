<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TradeChart from '@/components/chart/TradeChart.vue'
import { useOhlc } from '@/components/chart/useOhlc'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { drawingsApi, type AnalysisSummary, type Drawing } from '@/api/analysis'
import type { Timeframe } from '@/api/playbook'
import { biasBadge, chartTimeframes } from './model'

// Desktop analysis card (screens/source/WToday.dc.html): header chips, read-only chart with the analysis'
// key levels + drawings (H1 by default), narrative excerpt. Several analyses → symbol chips.
const props = defineProps<{ analyses: AnalysisSummary[]; timezone?: string }>()
const selectedId = defineModel<string | null>('selected', { default: null })
const { t } = useI18n()

const analysis = computed(() => props.analyses.find((a) => a.id === selectedId.value) ?? props.analyses[0])
const bias = computed(() => biasBadge(analysis.value.htf_bias))
const tf = ref<Timeframe>('H1')
const tfs = computed(() => chartTimeframes(analysis.value.timeframes))
/** "H4 Bull": the bias belongs to the analysis' highest timeframe. */
const htf = computed(() => chartTimeframes(analysis.value.timeframes, analysis.value.timeframes[0]).at(-1) ?? t('today.analysis.htf'))
const symbolId = computed(() => analysis.value.symbol_id)
const { data: ohlc, error: ohlcError, reload } = useOhlc(symbolId, tf, 120)
const drawings = shallowRef<Drawing[]>([])

watch(
  () => analysis.value.id,
  async (id) => {
    tf.value = 'H1'
    drawings.value = []
    try {
      const list = await drawingsApi.list('analysis', id)
      if (analysis.value.id === id) drawings.value = list
    } catch {
      /* the chart still shows bars + key levels */
    }
  },
  { immediate: true },
)
</script>

<template>
  <section class="tt-card tt-card--flush" data-testid="today-analysis">
    <header class="flex flex-wrap items-center gap-2 px-5 py-4">
      <h2 class="m-0 text-h3">{{ t('today.analysis.title', { symbol: analysis.symbol_code }) }}</h2>
      <TtBadge :variant="bias.variant" :icon="bias.icon">{{ htf }} {{ t(`trading.bias.${analysis.htf_bias}`) }}</TtBadge>
      <TtBadge v-if="analysis.session" variant="outline">{{ t(`trading.session.${analysis.session}`) }}</TtBadge>
      <span class="text-caption text-ink-muted">{{ t('today.analysis.confidence', { n: analysis.confidence }) }}</span>
      <span class="flex-1" />
      <div v-if="analyses.length > 1" class="tt-row" role="group" :aria-label="t('today.analysis.pick')">
        <TtChip v-for="a in analyses" :key="a.id" size="sm" :selected="a.id === analysis.id" @click="selectedId = a.id">{{ a.symbol_code }}</TtChip>
      </div>
      <RouterLink :to="`/analysis/${analysis.id}`" class="tt-btn tt-btn--ghost tt-btn--sm">{{ t('today.analysis.open') }}</RouterLink>
    </header>

    <div class="border-t border-border">
      <div v-if="ohlcError" class="flex h-[280px] flex-col items-center justify-center gap-2 text-body-sm text-ink-muted">
        {{ t('chart.loadError') }}
        <TtButton variant="secondary" size="sm" @click="reload">{{ t('chart.retry') }}</TtButton>
      </div>
      <div v-else-if="!ohlc" class="p-4"><TtSkeleton :lines="1" height="248px" /></div>
      <TradeChart
        v-else
        :bars="ohlc.bars"
        :digits="ohlc.digits"
        :timeframe="tf"
        :label="t('today.analysis.chart', { symbol: analysis.symbol_code, tf })"
        :key-levels="analysis.key_levels"
        :drawings="drawings"
        :timezone="timezone"
        height="280px"
      />
    </div>

    <footer class="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border px-5 pb-4 pt-3">
      <p class="m-0 line-clamp-2 min-w-0 flex-1 basis-[320px] text-body-sm text-ink-muted">
        {{ analysis.narrative_text || t('today.analysis.noNarrative') }}
      </p>
      <div class="tt-row" role="group" :aria-label="t('today.analysis.timeframes')">
        <TtChip v-for="x in tfs" :key="x" size="sm" :selected="x === tf" @click="tf = x">{{ x }}</TtChip>
      </div>
    </footer>
  </section>
</template>
