<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import type { IngestionJob } from '@/api/connections'
import { describeJob, shortDateTime, type Msg } from './model'

// "ประวัติการนำเข้า" (screens/mobile/24-Connections.png): one row per import — sync, history import, failures.
const props = withDefaults(
  defineProps<{ jobs: IngestionJob[] | null; historyDays?: (job: IngestionJob) => number | null; limit?: number; bare?: boolean }>(),
  { historyDays: () => null, limit: 20 },
)
const { t, locale } = useI18n()

const tr = (m: Msg) => {
  const n = m.params?.n
  return typeof n === 'number' ? t(m.key, m.params ?? {}, n) : t(m.key, m.params ?? {})
}

const rows = computed(() =>
  (props.jobs ?? []).slice(0, props.limit).map((job) => {
    const d = describeJob(job, props.historyDays(job))
    const when = shortDateTime(job.started_at, locale.value, job.kind !== 'history')
    return {
      id: job.id,
      ok: d.ok,
      warn: job.status === 'warning',
      title: tr(d.title),
      sub: [when, ...d.parts.map(tr)].join(' · '),
    }
  }),
)
</script>

<template>
  <section class="flex flex-col gap-3" data-testid="ingestion-history">
    <h2 class="m-0 text-h3">{{ t('connections.historyTitle') }}</h2>
    <div v-if="jobs === null" class="tt-card"><TtSkeleton :lines="3" height="36px" /></div>
    <p v-else-if="!rows.length" class="m-0 text-body-sm text-ink-muted">{{ t('connections.historyEmpty') }}</p>
    <ul v-else class="tt-list">
      <li v-for="r in rows" :key="r.id" class="tt-list__row">
        <span
          class="grid size-9 flex-none place-items-center rounded-md"
          :class="!r.ok ? 'bg-loss-100 text-loss-ink' : r.warn ? 'bg-warning-100 text-warning-ink' : 'bg-profit-100 text-profit-ink'"
        >
          <AppIcon :name="r.ok ? 'check' : 'close'" :size="16" />
        </span>
        <span class="flex min-w-0 flex-1 flex-col">
          <span class="text-[14px] font-semibold leading-5">{{ r.title }}</span>
          <span class="text-caption text-ink-muted">{{ r.sub }}</span>
        </span>
      </li>
    </ul>
  </section>
</template>
