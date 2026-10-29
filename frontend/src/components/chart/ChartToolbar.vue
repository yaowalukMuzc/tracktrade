<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/lib/icons'
import type { ChartTool } from './TradeChart.vue'

// Vertical drawing toolbar (screens/source/WAnalysis.dc.html: cursor, trendline, —, ▭, T, measure, delete).
/** `bare`: no frame (the parent card draws the divider). */
defineProps<{ canDelete: boolean; vertical?: boolean; bare?: boolean }>()
const tool = defineModel<ChartTool>({ required: true })
const emit = defineEmits<{ delete: [] }>()
const { t } = useI18n()

const tools: { id: ChartTool; icon?: IconName; glyph?: string }[] = [
  { id: 'cursor', icon: 'toolCursor' },
  { id: 'trendline', icon: 'toolTrendline' },
  { id: 'ray', icon: 'toolRay' },
  { id: 'horizontal', glyph: '—' },
  { id: 'rectangle', glyph: '▭' },
  { id: 'text', glyph: 'T' },
  { id: 'measure', icon: 'toolMeasure' },
]
</script>

<template>
  <div
    class="flex gap-1"
    :class="[vertical ? 'flex-col' : 'flex-row flex-wrap', bare ? '' : 'rounded-control border border-border bg-surface p-1']"
    role="toolbar"
    :aria-label="t('chart.tools.label')"
    :aria-orientation="vertical ? 'vertical' : 'horizontal'"
  >
    <button
      v-for="item in tools"
      :key="item.id"
      type="button"
      class="grid size-9 place-items-center rounded-[8px] text-sm font-bold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700"
      :class="tool === item.id ? 'bg-brand-100 text-brand-700' : 'text-ink-muted hover:bg-surface-sunken'"
      :aria-label="t(`chart.tools.${item.id}`)"
      :title="t(`chart.tools.${item.id}`)"
      :aria-pressed="tool === item.id"
      @click="tool = item.id"
    >
      <AppIcon v-if="item.icon" :name="item.icon" :size="16" />
      <!-- eslint-disable-next-line @intlify/vue-i18n/no-raw-text -- tool glyphs from the design, not words -->
      <span v-else aria-hidden="true">{{ item.glyph }}</span>
    </button>
    <button
      type="button"
      class="grid size-9 place-items-center rounded-[8px] text-ink-muted transition-colors hover:bg-surface-sunken disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700"
      :aria-label="t('chart.tools.delete')"
      :title="t('chart.tools.delete')"
      :disabled="!canDelete"
      @click="emit('delete')"
    >
      <AppIcon name="delete" :size="16" />
    </button>
  </div>
</template>
