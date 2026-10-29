<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import type { Revision } from '@/api/plans'
import type { Locale } from '@/i18n'
import { formatR } from '@/lib/format'
import { changeRows } from './form'
import { dayTime, timeHm } from './display'

// Append-only revision history (F-06 AC4–AC5): rev 1 = the lock; later ones list "SL 4,366.78 → 4,360.00"
// and the reason; revisions after the entry carry the warning badge "แก้หลังเข้าเทรด".
const props = defineProps<{ revisions: Revision[]; digits: number }>()
const { t, locale } = useI18n()
const l = computed(() => locale.value as Locale)

function changeText(rev: Revision) {
  return changeRows(rev, props.digits, (iso) => dayTime(iso, l.value))
    .map((row) => {
      const c = rev.changes[row.field]
      let from = row.from
      let to = row.to
      if (row.field === 'entry_type') {
        from = t(`trading.entryType.${c.from}`)
        to = t(`trading.entryType.${c.to}`)
      }
      return t('plans.revisions.change', { field: t(`plans.revisions.fields.${row.field}`), from, to })
    })
    .join(' · ')
}

const rows = computed(() =>
  props.revisions.map((rev) => ({
    rev,
    head: t('plans.revisions.row', { n: rev.revision_no, time: timeHm(rev.changed_at, l.value) }),
    detail: rev.revision_no === 1 ? '' : [changeText(rev), rev.reason ? t('plans.revisions.reason', { reason: rev.reason }) : ''].filter(Boolean).join(' · '),
    delta: rev.risk_delta_r !== null && Number(rev.risk_delta_r) !== 0 ? formatR(Number(rev.risk_delta_r), 2) : '',
  })),
)
</script>

<template>
  <section class="tt-card" data-testid="plan-revisions">
    <h2 class="tt-card__title mb-1">{{ t('plans.sections.revisions') }}</h2>
    <p v-if="!rows.length" class="m-0 py-2 text-body-sm text-ink-muted">{{ t('plans.revisions.empty') }}</p>
    <ol class="m-0 list-none p-0">
      <li v-for="r in rows" :key="r.rev.revision_no" class="border-b border-border py-2.5 last:border-0" :data-rev="r.rev.revision_no">
        <div class="flex items-center justify-between gap-3 text-[14px] leading-[22px]">
          <span class="tt-num text-ink-muted">{{ r.head }}</span>
          <b v-if="r.rev.revision_no === 1" class="font-semibold">{{ t('plans.revisions.first') }}</b>
          <TtBadge v-else-if="r.rev.changed_after_entry" variant="warning">{{ t('plans.revisions.afterEntry') }}</TtBadge>
          <span v-else-if="r.delta" class="tt-num font-semibold text-ink-muted">{{ r.delta }}</span>
        </div>
        <p v-if="r.detail" class="tt-help m-0 mt-1.5">{{ r.detail }}</p>
      </li>
    </ol>
  </section>
</template>
