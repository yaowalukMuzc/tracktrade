<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PageContent from '@/components/shell/PageContent.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import type { IngestionJob } from '@/api/connections'
import { useAccountsStore } from '@/stores/accounts'
import ConnectionCard from './ConnectionCard.vue'
import IngestionHistory from './IngestionHistory.vue'
import { useConnections, useNow } from './useConnections'

// /accounts/connections — screens/mobile/24-Connections.png (F-08 AC6). Every MT5 / cTrader account's card, then
// the import history of all of them. `?account=` puts that account first. Desktop uses the tab in /accounts.
const { t } = useI18n()
const route = useRoute()
const store = useAccountsStore()
const now = useNow()

onMounted(() => void store.ensureLoaded())

const linked = computed(() => {
  const list = store.active.filter((a) => a.platform !== 'manual')
  const first = typeof route.query.account === 'string' ? route.query.account : store.selected?.id
  return [...list].sort((a, b) => Number(b.id === first) - Number(a.id === first))
})
const ids = computed(() => linked.value.map((a) => a.id))
const { connections, jobs, loaded, error, load, replace } = useConnections(ids, { jobs: true })

const conn = (accountId: string, platform: string) =>
  (connections.value[accountId] ?? []).find((c) => c.kind === (platform === 'mt5' ? 'mt5_ea' : 'ctrader_oauth')) ?? null

const allJobs = computed<IngestionJob[] | null>(() =>
  loaded.value
    ? Object.values(jobs.value)
        .flat()
        .sort((a, b) => b.started_at.localeCompare(a.started_at))
    : null,
)
/** "90 วัน" on an initial-import row comes from its account's connection. */
const daysByJob = computed(() => {
  const out = new Map<string, number | null>()
  for (const [accountId, list] of Object.entries(jobs.value)) {
    const days = (connections.value[accountId] ?? []).find((c) => c.stats.history_days != null)?.stats.history_days ?? null
    for (const j of list) out.set(j.id, days)
  }
  return out
})
const historyDays = (job: IngestionJob) => daysByJob.value.get(job.id) ?? null
</script>

<template>
  <div>
    <PageHeader :title="t('connections.title')" :crumb="{ to: { name: 'accounts', query: route.query.account ? { account: route.query.account } : {} }, label: t('connections.back') }" />
    <PageContent>
      <TtAlert v-if="error" variant="loss" :title="t('connections.loadError')">
        <template #action><TtButton size="sm" variant="secondary" @click="load">{{ t('connections.retry') }}</TtButton></template>
      </TtAlert>
      <div v-if="!store.loaded || (!loaded && !error && linked.length)" class="tt-card"><TtSkeleton :lines="4" height="36px" /></div>
      <section v-else-if="!linked.length" class="tt-card">
        <TtEmpty icon="connection" :message="t('connections.pageEmpty')" />
      </section>
      <template v-else>
        <ConnectionCard
          v-for="a in linked"
          :key="a.id"
          :account="a"
          :connection="conn(a.id, a.platform)"
          :now="now"
          layout="full"
          @changed="(c) => (replace(c), load())"
        />
        <IngestionHistory :jobs="allJobs" :history-days="historyDays" />
      </template>
    </PageContent>
  </div>
</template>
