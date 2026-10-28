<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtCard from '@/components/ui/TtCard.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtStat from '@/components/ui/TtStat.vue'
import { playbookApi, type Setup } from '@/api/playbook'
import ChecklistCard from './ChecklistCard.vue'
import ExamplesCard from './ExamplesCard.vue'
import { breakEvenLabel, errorKey, partialLabel, riskLabel, sessionLabel, setupMeta, statView, trailingLabel } from './model'

// Setup detail. `split` = right column of the desktop Playbook (screens/web/13); `page` = mobile detail
// (screens/mobile/22) whose title/back/edit live in the page header. Stats stay "—" until Phase 7 (F-04 AC3).
const props = defineProps<{ setup: Setup; layout: 'split' | 'page' }>()
const emit = defineEmits<{ update: [Setup]; edit: []; archived: [Setup] }>()
const { t } = useI18n()

const stats = computed(() => statView(props.setup.stats))
const meta = computed(() => setupMeta(t, props.setup))
const rules = computed(() => props.setup.management_rules)

const busy = ref(false)
const error = ref<[string, Record<string, unknown>?] | null>(null)

async function toggleArchive() {
  busy.value = true
  error.value = null
  try {
    const res = props.setup.is_archived ? await playbookApi.unarchive(props.setup.id) : await playbookApi.archive(props.setup.id)
    emit('update', res)
    emit('archived', res)
  } catch (e) {
    error.value = errorKey(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex min-w-0 flex-col" :class="layout === 'split' ? 'gap-6' : 'gap-3'">
    <TtAlert v-if="error" variant="loss" :title="t(error[0], error[1] ?? {})" dismissible @dismiss="error = null" />

    <!-- Header -->
    <TtCard v-if="layout === 'split'" class="flex flex-col gap-3">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div class="min-w-0">
          <h2 class="m-0 break-words text-h2">{{ setup.name }}</h2>
          <div class="mt-1.5 flex flex-wrap gap-2">
            <TtBadge variant="outline">{{ meta }}</TtBadge>
            <TtBadge v-if="setup.is_archived" icon="archive">{{ t('playbook.archivedBadge') }}</TtBadge>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <TtButton size="sm" icon="edit" @click="emit('edit')">{{ t('playbook.edit') }}</TtButton>
          <TtButton variant="ghost" size="sm" class="!text-ink-muted" :loading="busy" @click="toggleArchive">
            {{ setup.is_archived ? t('playbook.unarchive') : t('playbook.archive') }}
          </TtButton>
        </div>
      </div>
      <p class="m-0 whitespace-pre-line text-body text-ink-muted">{{ setup.description || t('playbook.noDescription') }}</p>
    </TtCard>
    <template v-else>
      <p class="m-0 whitespace-pre-line text-body text-ink-muted">{{ setup.description || t('playbook.noDescription') }}</p>
      <div class="flex flex-wrap gap-2">
        <TtBadge v-if="setup.timeframes.length" variant="outline">{{ setup.timeframes.join(' · ') }}</TtBadge>
        <TtBadge v-for="s in setup.sessions" :key="s" variant="outline">{{ sessionLabel(t, s) }}</TtBadge>
        <TtBadge variant="brand">{{ t('playbook.defaultRiskChip', { risk: riskLabel(setup.default_risk_pct) }) }}</TtBadge>
        <TtBadge v-if="setup.is_archived" icon="archive">{{ t('playbook.archivedBadge') }}</TtBadge>
      </div>
    </template>

    <!-- KPIs (F-04 AC3 — Phase 7) -->
    <div
      class="grid gap-3"
      :class="layout === 'split' ? 'grid-cols-[repeat(auto-fit,minmax(170px,1fr))]' : 'grid-cols-2'"
      :title="stats.trades === '—' ? t('playbook.stats.pending') : undefined"
    >
      <TtStat :label="t('playbook.stats.trades')">{{ stats.trades }}</TtStat>
      <TtStat :label="t('playbook.stats.winRate')">{{ stats.winRate }}</TtStat>
      <TtStat :label="t('playbook.stats.expectancy')">
        <span :class="stats.expDir && `tt-pnl--${stats.expDir}`">{{ stats.expectancy }}</span>
      </TtStat>
      <template v-if="layout === 'split'">
        <TtStat :label="t('playbook.stats.avgAdherence')">{{ stats.adherence }}</TtStat>
        <TtStat :label="t('playbook.stats.avgQuality')">{{ stats.quality }}</TtStat>
      </template>
      <TtStat v-else :label="t('playbook.stats.adhQuality')">
        {{ stats.adherence === '—' && stats.grade === '—' ? '—' : `${stats.adherence} · ${stats.grade}` }}
      </TtStat>
    </div>
    <p v-if="stats.trades === '—'" class="sr-only">{{ t('playbook.stats.pending') }}</p>

    <!-- Checklist + management rules -->
    <div class="grid items-start" :class="layout === 'split' ? 'grid-cols-[repeat(auto-fit,minmax(min(100%,340px),1fr))] gap-6' : 'gap-3'">
      <ChecklistCard :setup="setup" @update="emit('update', $event)" />
      <TtCard>
        <h2 class="tt-card__title mb-1">{{ t('playbook.rules.title') }}</h2>
        <dl class="m-0">
          <div v-if="layout === 'split'" class="kv-row">
            <dt>{{ t('playbook.rules.defaultRisk') }}</dt>
            <dd>{{ riskLabel(setup.default_risk_pct, 1) }}</dd>
          </div>
          <div class="kv-row">
            <dt>{{ t('playbook.rules.partial') }}</dt>
            <dd :class="{ 'kv-off': !rules.partial }">{{ partialLabel(t, rules.partial) }}</dd>
          </div>
          <div class="kv-row">
            <dt>{{ t('playbook.rules.breakEven') }}</dt>
            <dd :class="{ 'kv-off': !rules.break_even }">{{ breakEvenLabel(t, rules.break_even) }}</dd>
          </div>
          <div class="kv-row">
            <dt>{{ t('playbook.rules.trailing') }}</dt>
            <dd :class="{ 'kv-off': !rules.trailing }">{{ trailingLabel(t, rules.trailing) }}</dd>
          </div>
        </dl>
      </TtCard>
    </div>

    <ExamplesCard :setup="setup" :layout="layout" :class="{ 'mt-3': layout === 'page' }" @update="emit('update', $event)" />

    <template v-if="layout === 'page'">
      <section class="mt-3 flex flex-col gap-3">
        <h2 class="m-0 text-h3">{{ t('playbook.recent.title') }}</h2>
        <div class="tt-card !p-0">
          <TtEmpty icon="trades" :message="t('playbook.recent.empty')" />
        </div>
      </section>
      <TtButton variant="ghost" block class="!text-ink-muted" :loading="busy" @click="toggleArchive">
        {{ setup.is_archived ? t('playbook.unarchiveThis') : t('playbook.archiveThis') }}
      </TtButton>
    </template>
  </div>
</template>

<style scoped>
/* screens.css .kv — label / value rows of the management-rules card. */
.kv-row { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border); font: 400 14px/22px var(--font-sans); }
.kv-row:last-child { border-bottom: 0; }
.kv-row dt { color: var(--ink-muted); }
.kv-row dd { margin: 0; font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }
.kv-row dd.kv-off { font-weight: 400; color: var(--ink-subtle); }
</style>
