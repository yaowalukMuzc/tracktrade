<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RouteLocationRaw } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import type { SetupSummary } from '@/api/playbook'
import { setupMeta, statView } from './model'

// Playbook list card. Desktop (`to` unset): a selectable button, the selected one outlined in brand-700 on brand-50
// (screens/web/13). Mobile (`to` set): a link card with a chevron and a dashed divider (screens/mobile/21).
const props = defineProps<{ setup: SetupSummary; selected?: boolean; to?: RouteLocationRaw }>()
defineEmits<{ select: [] }>()
const { t } = useI18n()

const stats = computed(() => statView(props.setup.stats))
const meta = computed(() => setupMeta(t, props.setup))
const cols = computed(() => [
  { label: t('playbook.stats.trades'), value: stats.value.trades },
  { label: props.to ? t('playbook.stats.winRate') : t('playbook.stats.win'), value: stats.value.winRate },
  { label: props.to ? t('playbook.stats.expectancy') : t('playbook.stats.exp'), value: stats.value.expectancy, dir: stats.value.expDir },
  { label: props.to ? t('playbook.stats.adherence') : t('playbook.stats.adh'), value: stats.value.adherence },
])
</script>

<template>
  <component
    :is="to ? 'RouterLink' : 'button'"
    :to="to"
    :type="to ? undefined : 'button'"
    class="flex w-full flex-col gap-2.5 rounded-lg border bg-surface text-left font-sans text-ink no-underline"
    :class="[
      to ? 'border-border p-4' : 'cursor-pointer',
      !to && (selected ? 'border-2 border-brand-700 bg-brand-50 px-[15px] py-[13px]' : 'border-border px-4 py-3.5 hover:border-border-strong'),
    ]"
    :aria-current="selected ? 'true' : undefined"
    :aria-label="to ? t('playbook.open', { name: setup.name }) : undefined"
    @click="!to && $emit('select')"
  >
    <div class="flex w-full items-center gap-2.5">
      <span class="grid h-9 w-9 flex-none place-items-center rounded-md bg-brand-100 text-brand-700"><AppIcon name="playbook" /></span>
      <div class="flex min-w-0 flex-1 flex-col">
        <span class="truncate text-[14px] font-semibold leading-5">{{ setup.name }}</span>
        <span class="truncate text-[12px] leading-[18px] text-ink-muted">{{ meta }}</span>
      </div>
      <AppIcon v-if="to" name="forward" class="text-ink-subtle" />
    </div>
    <dl class="m-0 grid w-full grid-cols-4 gap-1.5" :class="{ 'gap-2 border-0 border-t border-dashed border-border pt-2.5': to }">
      <div v-for="c in cols" :key="c.label" class="min-w-0">
        <dt class="truncate text-caption font-normal text-ink-muted">{{ c.label }}</dt>
        <dd class="m-0 text-num tabular-nums" :class="c.dir && ['tt-pnl', `tt-pnl--${c.dir}`]">{{ c.value }}</dd>
      </div>
    </dl>
  </component>
</template>
