<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { connectionsApi } from '@/api/connections'
import { realtime } from '@/api/ws'
import type { IconName } from '@/lib/icons'
import EaInstallSteps from '@/features/accounts/EaInstallSteps.vue'
import KeyField from '@/features/accounts/KeyField.vue'
import { actionErrorKey } from '@/features/accounts/useConnections'
import { useOnboarding } from './useOnboarding'

// Broker step (screens/mobile/04-ConnectBroker.png; step 3 of screens/web/02-WOnboarding.png). F-08 AC1:
// MT5 → the account's API key in full (once) + EA download + "รอสัญญาณจาก EA…" until the first deal arrives;
// cTrader → OAuth; manual → straight to adding trades.
const { state, t } = useOnboarding()

const busy = ref(false)
const errorKey = ref('')
const account = computed(() => state.account!)
const platform = computed(() => account.value.platform)

async function makeKey() {
  busy.value = true
  errorKey.value = ''
  try {
    state.apiKey = (await connectionsApi.createMt5Key(account.value.id)).api_key
  } catch (e) {
    errorKey.value = actionErrorKey(e)
  } finally {
    busy.value = false
  }
}

async function connectCtrader() {
  busy.value = true
  errorKey.value = ''
  try {
    window.location.assign((await connectionsApi.ctraderAuthorize(account.value.id)).authorize_url)
  } catch (e) {
    errorKey.value = actionErrorKey(e)
    busy.value = false
  }
}

const download = () => connectionsApi.downloadEa().catch(() => (errorKey.value = 'connections.actionError'))

let off: (() => void) | undefined
onMounted(() => {
  if (platform.value === 'mt5' && !state.apiKey) void makeKey()
  off = realtime.on((msg) => {
    if (msg.type === 'sync.first_deal' || msg.type === 'position.created') state.firstDeal = true
  })
})
onBeforeUnmount(() => off?.())

const PRIMARY: Record<'mt5' | 'ctrader' | 'manual', { icon: IconName; title: string; sub: string }> = {
  mt5: { icon: 'connection', title: 'onboarding.broker.mt5', sub: 'onboarding.broker.mt5Sub' },
  ctrader: { icon: 'link', title: 'onboarding.broker.ctrader', sub: 'onboarding.broker.ctraderSub' },
  manual: { icon: 'scan', title: 'onboarding.broker.manualTitle', sub: 'onboarding.broker.manualSub' },
}
const primary = computed(() => PRIMARY[platform.value])
/** Other ways in (design: a list with chevrons). Broker links belong to an account of that platform. */
const others = computed(() =>
  [
    { key: 'scan', icon: 'scan' as IconName, to: { name: 'trade-new', query: { mode: 'scan' } } },
    { key: 'manual', icon: 'editRow' as IconName, to: { name: 'trade-new', query: { mode: 'manual' } } },
  ].filter((o) => !(platform.value === 'manual' && o.key === 'manual')),
)
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="tt-card tt-stack !border-brand-700 outline outline-1 outline-brand-700" data-testid="broker-primary">
      <div class="flex items-center gap-3">
        <span class="grid size-9 flex-none place-items-center rounded-md bg-brand-100 text-brand-700"><AppIcon :name="primary.icon" /></span>
        <span class="flex min-w-0 flex-1 flex-col">
          <span class="text-[15px] font-semibold leading-5">{{ t(primary.title) }}</span>
          <span class="text-caption text-ink-muted">{{ t(primary.sub) }}</span>
        </span>
        <TtBadge variant="solid">{{ t('onboarding.broker.selected') }}</TtBadge>
      </div>

      <template v-if="platform === 'mt5'">
        <TtSkeleton v-if="busy && !state.apiKey" :lines="1" height="40px" />
        <template v-else-if="state.apiKey">
          <KeyField :label="t('onboarding.broker.keyLabel', { name: account.name })" :display="state.apiKey" :copy-value="state.apiKey" copy-button>
            <template #actions>
              <TtButton variant="ghost" size="sm" icon="download" @click="download">{{ t('connections.mt5.download') }}</TtButton>
            </template>
          </KeyField>
          <p class="m-0 text-caption text-ink-muted">{{ t('connections.key.once') }}</p>
          <EaInstallSteps />
          <TtAlert v-if="state.firstDeal" variant="profit" :title="t('onboarding.broker.firstDealTitle')" :body="t('onboarding.broker.firstDealBody')" />
          <TtAlert v-else variant="warning" icon="clock" :title="t('connections.mt5.waitingTitle')" :body="t('connections.mt5.waitingBody')" />
        </template>
      </template>

      <template v-else-if="platform === 'ctrader'">
        <p class="m-0 text-body-sm text-ink-muted">{{ t('connections.ctrader.intro') }}</p>
        <TtButton variant="primary" block icon="link" :loading="busy" @click="connectCtrader">{{ t('connections.ctrader.connect') }}</TtButton>
      </template>

      <p v-else class="m-0 text-body-sm text-ink-muted">{{ t('onboarding.broker.manualBody') }}</p>

      <TtAlert v-if="errorKey" :variant="errorKey.endsWith('notConfigured') ? 'info' : 'loss'" :title="t(errorKey)">
        <template v-if="platform === 'mt5' && !state.apiKey" #action>
          <TtButton size="sm" variant="secondary" @click="makeKey">{{ t('connections.retry') }}</TtButton>
        </template>
      </TtAlert>
    </section>

    <ul class="tt-list">
      <li v-for="o in others" :key="o.key">
        <RouterLink :to="o.to" class="tt-list__row">
          <span class="grid size-9 flex-none place-items-center rounded-md bg-surface-sunken text-ink-muted"><AppIcon :name="o.icon" /></span>
          <span class="flex min-w-0 flex-1 flex-col">
            <span class="text-[15px] font-semibold leading-5">{{ t(`onboarding.broker.row.${o.key}`) }}</span>
            <span class="text-caption text-ink-muted">{{ t(`onboarding.broker.row.${o.key}Sub`) }}</span>
          </span>
          <AppIcon name="forward" class="text-ink-subtle" />
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
