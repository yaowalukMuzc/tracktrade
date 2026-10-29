<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtModal from '@/components/ui/TtModal.vue'
import type { Account } from '@/api/accounts'
import { connectionsApi, type Connection } from '@/api/connections'
import { isAuthError, relativeTime, shortDateTime, unknownSymbols } from './model'
import { actionErrorKey } from './useConnections'
import ApiKeyDialog from './ApiKeyDialog.vue'
import EaInstallSteps from './EaInstallSteps.vue'
import KeyField from './KeyField.vue'

/**
 * Broker connection of one account (F-08 AC1, AC6).
 * `aside`: the right-column card of screens/web/14-WAccounts.png (title + kv rows).
 * `full`:  the card of screens/mobile/24-Connections.png (icon row + stat tiles) — mobile page and the desktop tab.
 */
const props = withDefaults(
  defineProps<{ account: Account; connection?: Connection | null; now: number; layout?: 'aside' | 'full'; loading?: boolean }>(),
  { layout: 'aside', connection: null },
)
const emit = defineEmits<{ changed: [conn: Connection] }>()
const { t, locale } = useI18n()

const busy = ref<'' | 'key' | 'sync' | 'download' | 'ctrader'>('')
const errorKey = ref('')
const notice = ref('')
const fullKey = ref<string | null>(null)
const keyDialog = ref(false)
const confirmRotate = ref(false)

const conn = computed(() => props.connection)
const platform = computed(() => props.account.platform)
const status = computed(() => conn.value?.status ?? null)
const errored = computed(() => status.value === 'error')
const authError = computed(() => isAuthError(conn.value?.last_error))
const unknown = computed(() => unknownSymbols(conn.value?.last_error))
const ago = (iso: string | null | undefined) => (iso ? relativeTime(iso, props.now, locale.value) : '')
const lastContact = computed(() => conn.value?.last_seen_at ?? conn.value?.last_sync_at ?? null)

const STATUS_BADGE = { connected: 'profit', pending: 'warning', offline: 'neutral', error: 'loss' } as const
const title = computed(() =>
  platform.value === 'mt5'
    ? props.layout === 'full'
      ? t('connections.mt5.rowTitle', { name: props.account.name })
      : t('connections.mt5.title')
    : platform.value === 'ctrader'
      ? props.layout === 'full'
        ? t('connections.ctrader.rowTitle', { broker: props.account.broker })
        : t('connections.ctrader.title', { broker: props.account.broker })
      : t('connections.manual.title'),
)
const subtitle = computed(() => {
  if (!conn.value) return ''
  if (!lastContact.value) return t('connections.mt5.never')
  return t('connections.mt5.lastSyncAgo', { ago: ago(lastContact.value) })
})
const tileTone = computed(() => (errored.value ? 'bg-loss-100 text-loss-ink' : status.value === 'connected' ? 'bg-profit-100 text-profit-ink' : 'bg-surface-sunken text-ink-muted'))

async function run<T>(what: typeof busy.value, fn: () => Promise<T>): Promise<T | undefined> {
  busy.value = what
  errorKey.value = ''
  notice.value = ''
  try {
    return await fn()
  } catch (e) {
    errorKey.value = actionErrorKey(e)
    return undefined
  } finally {
    busy.value = ''
  }
}

async function createKey() {
  confirmRotate.value = false
  const res = await run('key', () => connectionsApi.createMt5Key(props.account.id))
  if (!res) return
  fullKey.value = res.api_key
  keyDialog.value = true
  emit('changed', res.connection)
}

async function syncNow() {
  if (!conn.value) return
  const res = await run('sync', () => connectionsApi.sync(conn.value!.id))
  if (!res) return
  notice.value = platform.value === 'mt5' ? t('connections.mt5.syncSent') : t('connections.ctrader.pending')
  emit('changed', res)
}

const download = () => run('download', () => connectionsApi.downloadEa())

async function connectCtrader() {
  const res = await run('ctrader', () => connectionsApi.ctraderAuthorize(props.account.id))
  if (res) window.location.assign(res.authorize_url)
}
</script>

<template>
  <section
    class="tt-card tt-stack"
    :class="{ '!border-loss': errored }"
    :data-testid="`connection-${account.platform}`"
    :aria-busy="loading || undefined"
  >
    <!-- header -->
    <div v-if="layout === 'full' && platform !== 'manual'" class="flex items-center gap-3">
      <span class="grid size-9 flex-none place-items-center rounded-md" :class="tileTone">
        <AppIcon :name="platform === 'mt5' ? 'connection' : 'link'" />
      </span>
      <span class="flex min-w-0 flex-1 flex-col">
        <h2 class="m-0 truncate text-[14px] font-semibold leading-5">{{ title }}</h2>
        <span v-if="subtitle" class="truncate text-caption text-ink-muted">{{ subtitle }}</span>
      </span>
      <TtBadge v-if="status" :variant="STATUS_BADGE[status]" :icon="status === 'connected' ? 'success' : undefined">{{ t(`connections.status.${status}`) }}</TtBadge>
    </div>
    <div v-else class="flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">{{ title }}</h2>
      <TtBadge v-if="status" :variant="STATUS_BADGE[status]" :icon="status === 'connected' ? 'success' : undefined">{{ t(`connections.status.${status}`) }}</TtBadge>
      <TtBadge v-else-if="platform !== 'manual'" variant="outline">{{ t('connections.badge.none') }}</TtBadge>
    </div>

    <!-- manual account -->
    <p v-if="platform === 'manual'" class="m-0 text-body-sm text-ink-muted">{{ t('connections.manual.body') }}</p>

    <!-- ================= MT5 EA ================= -->
    <template v-else-if="platform === 'mt5'">
      <template v-if="!conn">
        <p class="m-0 text-body-sm text-ink-muted">{{ t('connections.mt5.noKey') }}</p>
        <div class="flex flex-wrap gap-2">
          <TtButton variant="primary" size="sm" icon="key" :loading="busy === 'key'" @click="createKey">{{ t('connections.mt5.createKey') }}</TtButton>
          <TtButton variant="ghost" size="sm" icon="download" :loading="busy === 'download'" @click="download">{{ t('connections.mt5.download') }}</TtButton>
        </div>
      </template>
      <template v-else>
        <div v-if="layout === 'full'" class="tt-calc">
          <div><span>{{ t('connections.mt5.dealsToday') }}</span><b>{{ conn.stats.deals_today }}</b></div>
          <div><span>{{ t('connections.mt5.mods') }}</span><b>{{ conn.stats.mods_today }}</b></div>
          <div>
            <span>{{ t('connections.mt5.history') }}</span>
            <b>{{ conn.stats.history_days != null ? t('connections.mt5.historyDays', { n: conn.stats.history_days }) : t('connections.mt5.historyPending') }}</b>
          </div>
        </div>

        <KeyField :label="t('connections.mt5.apiKey')" :display="fullKey ?? conn.key_hint ?? ''" :copy-value="fullKey" />

        <dl v-if="layout === 'aside'" class="m-0 flex flex-col">
          <div class="flex justify-between gap-3 border-b border-border py-2.5 text-body-sm">
            <dt class="text-ink-muted">{{ t('connections.mt5.lastSync') }}</dt>
            <dd class="m-0 font-semibold tabular-nums">{{ lastContact ? ago(lastContact) : t('connections.mt5.never') }}</dd>
          </div>
          <div class="flex justify-between gap-3 py-2.5 text-body-sm">
            <dt class="text-ink-muted">{{ t('connections.mt5.dealsMods') }}</dt>
            <dd class="m-0 font-semibold tabular-nums">{{ conn.stats.deals_today }} · {{ conn.stats.mods_today }}</dd>
          </div>
        </dl>

        <TtAlert v-if="status === 'pending'" variant="warning" icon="clock" :title="t('connections.mt5.waitingTitle')" :body="t('connections.mt5.waitingBody')" />
        <EaInstallSteps v-if="status === 'pending'" />
        <TtAlert
          v-if="status === 'offline'"
          variant="warning"
          icon="clock"
          :title="t('connections.mt5.offlineTitle')"
          :body="t('connections.mt5.offlineBody', { ago: ago(lastContact) })"
        />
        <TtAlert v-if="unknown.length" variant="warning" :title="t('connections.mt5.unknownSymbols', { list: unknown.join(', ') })" />
        <TtAlert v-else-if="errored && conn.last_error" variant="loss" :title="t('connections.ctrader.errorTitle')" :body="conn.last_error" />

        <div class="flex flex-wrap items-center gap-2">
          <TtButton variant="secondary" size="sm" icon="sync" :loading="busy === 'sync'" @click="syncNow">{{ t('connections.mt5.syncNow') }}</TtButton>
          <TtButton variant="ghost" size="sm" icon="download" :loading="busy === 'download'" @click="download">{{ t('connections.mt5.download') }}</TtButton>
          <TtButton variant="ghost" size="sm" icon="key" :loading="busy === 'key'" @click="confirmRotate = true">{{ t('connections.mt5.rotate') }}</TtButton>
        </div>
      </template>
    </template>

    <!-- ================= cTrader ================= -->
    <template v-else>
      <p v-if="!conn" class="m-0 text-body-sm text-ink-muted">{{ t('connections.ctrader.intro') }}</p>
      <template v-else>
        <div v-if="layout === 'full' && !errored" class="tt-calc">
          <div><span>{{ t('connections.mt5.dealsToday') }}</span><b>{{ conn.stats.deals_today }}</b></div>
          <div><span>{{ t('connections.mt5.mods') }}</span><b>{{ conn.stats.mods_today }}</b></div>
          <div>
            <span>{{ t('connections.mt5.history') }}</span>
            <b>{{ conn.stats.history_days != null ? t('connections.mt5.historyDays', { n: conn.stats.history_days }) : t('connections.mt5.historyPending') }}</b>
          </div>
        </div>
        <p v-if="status === 'pending'" class="m-0 text-body-sm text-ink-muted">{{ t('connections.ctrader.pending') }}</p>
        <TtAlert
          v-if="errored && authError"
          variant="loss"
          :title="t('connections.ctrader.tokenTitle')"
          :body="t('connections.ctrader.tokenBody', { error: conn.last_error ?? '' })"
        />
        <template v-else-if="errored">
          <TtAlert v-if="layout === 'full'" variant="loss" :title="t('connections.ctrader.errorTitle')" :body="conn.last_error ?? ''" />
          <span v-else class="text-body-sm text-ink-muted">
            {{ t('connections.ctrader.errorBody', { error: conn.last_error ?? '', at: conn.last_error_at ? shortDateTime(conn.last_error_at, locale) : '' }) }}
          </span>
        </template>
        <dl v-if="layout === 'aside' && !errored" class="m-0 flex flex-col">
          <div class="flex justify-between gap-3 border-b border-border py-2.5 text-body-sm">
            <dt class="text-ink-muted">{{ t('connections.mt5.lastSync') }}</dt>
            <dd class="m-0 font-semibold tabular-nums">{{ lastContact ? ago(lastContact) : t('connections.mt5.never') }}</dd>
          </div>
          <div class="flex justify-between gap-3 py-2.5 text-body-sm">
            <dt class="text-ink-muted">{{ t('connections.mt5.dealsMods') }}</dt>
            <dd class="m-0 font-semibold tabular-nums">{{ conn.stats.deals_today }} · {{ conn.stats.mods_today }}</dd>
          </div>
        </dl>
        <TtButton v-if="status === 'connected'" class="self-start" variant="secondary" size="sm" icon="sync" :loading="busy === 'sync'" @click="syncNow">
          {{ t('connections.mt5.syncNow') }}
        </TtButton>
      </template>
      <TtButton v-if="!conn || errored" variant="primary" block icon="link" :loading="busy === 'ctrader'" @click="connectCtrader">
        {{ conn ? t('connections.ctrader.reconnect') : t('connections.ctrader.connect') }}
      </TtButton>
    </template>

    <p v-if="notice" class="m-0 text-body-sm text-ink-muted" role="status">{{ notice }}</p>
    <TtAlert v-if="errorKey" :variant="errorKey.endsWith('notConfigured') ? 'info' : 'loss'" :title="t(errorKey)" />

    <ApiKeyDialog v-if="fullKey" v-model:open="keyDialog" :account-name="account.name" :api-key="fullKey" />
    <TtModal v-model:open="confirmRotate" size="sm" :title="t('connections.key.rotateTitle')">
      <p class="m-0 text-body text-ink-muted">{{ t('connections.key.rotateBody') }}</p>
      <template #footer>
        <TtButton variant="secondary" @click="confirmRotate = false">{{ t('connections.cancel') }}</TtButton>
        <TtButton variant="danger" :loading="busy === 'key'" @click="createKey">{{ t('connections.key.rotateConfirm') }}</TtButton>
      </template>
    </TtModal>
  </section>
</template>
