<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { useDesktop } from '@/composables/useDesktop'
import { useAccountsStore } from '@/stores/accounts'
import { useInboxStore } from '@/stores/inbox'
import { useSessionStore } from '@/stores/session'
import MatchPicker from './MatchPicker.vue'
import { pnlDirection, pnlText } from './model'
import { useMatchQueue } from './useMatchQueue'

// /trades/match — mobile match queue, one trade at a time "1 / 2" (screens/mobile/12-MatchQueue.png, F-10 AC2–AC3).
// Desktop has the same picker as a modal on /trades, so a wide window is sent there.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const desktop = useDesktop()
const accounts = useAccountsStore()
const session = useSessionStore()
const inbox = useInboxStore()
const tz = computed(() => session.user?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone)
const startId = computed(() => (typeof route.query.id === 'string' ? route.query.id : null))

const q = useMatchQueue({ accountId: () => accounts.selected?.id, onMatched: () => void inbox.refreshTrades() })
onMounted(async () => {
  if (desktop.value) {
    void router.replace({ name: 'trades', query: { match: startId.value ?? '1' } })
    return
  }
  await accounts.ensureLoaded().catch(() => undefined)
  void q.load(startId.value)
})
// Last one handled → back to the list.
watch(q.done, (finished) => {
  if (finished && q.items.value.length) void router.replace({ name: 'trades' })
})

const current = computed(() => q.current.value)
const counter = computed(() => (current.value ? `${q.index.value + 1} / ${q.items.value.length}` : ''))
const hasEligible = computed(() => !!current.value?.candidates.some((c) => c.eligible))
const pnlClass = { up: 'tt-pnl--up', down: 'tt-pnl--down', flat: 'tt-pnl--flat' }
</script>

<template>
  <div class="flex min-h-dvh flex-col bg-bg text-ink">
    <header class="tt-appbar sticky top-0 z-30">
      <RouterLink to="/trades" class="tt-iconbtn tt-iconbtn--bare" :aria-label="t('trades.match.back')"><AppIcon name="back" /></RouterLink>
      <h1 class="tt-appbar__title">{{ t('trades.match.title') }}</h1>
      <TtBadge v-if="counter" variant="warning" data-testid="match-counter">{{ counter }}</TtBadge>
    </header>

    <main class="flex flex-1 flex-col gap-4 px-4 py-4 pb-[calc(96px+env(safe-area-inset-bottom))]">
      <TtSkeleton v-if="q.state.value === 'loading' || q.state.value === 'idle'" :lines="4" height="72px" />
      <TtAlert v-else-if="q.state.value === 'error'" variant="loss" :title="t('trades.match.loadFailed')">
        <template #action><TtButton size="sm" @click="q.load(startId)">{{ t('trades.error.retry') }}</TtButton></template>
      </TtAlert>
      <div v-else-if="!current" class="tt-card">
        <TtEmpty icon="success" :message="t('trades.match.empty')">
          <TtButton to="/trades">{{ t('trades.match.back') }}</TtButton>
        </TtEmpty>
      </div>
      <template v-else>
        <p class="m-0 text-body-sm text-ink-muted">{{ hasEligible ? t('trades.match.intro') : t('trades.match.introNone') }}</p>
        <section class="tt-card flex flex-col gap-3">
          <div class="flex items-center gap-2">
            <b class="text-[15px]">{{ current.position.symbol_code }}</b>
            <TtBadge :variant="current.position.direction">{{ t(`trading.direction.${current.position.direction}`) }}</TtBadge>
            <TtBadge variant="outline">{{ t(`trades.source.${current.position.source}`) }}</TtBadge>
            <span class="flex-1" />
            <span class="tt-pnl text-num" :class="pnlClass[pnlDirection(current.position)]">{{ pnlText(current.position, 'money') }}</span>
          </div>
          <MatchPicker
            v-model="q.choice.value"
            :position="current.position"
            :first-entry="current.first_entry"
            :candidates="current.candidates"
            :tz="tz"
            compact
            part="summary"
          />
        </section>
        <MatchPicker
          :key="current.position.id"
          v-model="q.choice.value"
          :position="current.position"
          :first-entry="current.first_entry"
          :candidates="current.candidates"
          :tz="tz"
          compact
          part="options"
        />
        <TtAlert v-if="q.saveError.value" variant="loss" :title="t('trades.match.failed')" />
      </template>
    </main>

    <footer
      v-if="current"
      class="fixed inset-x-0 bottom-0 z-30 flex items-center gap-3 border-t border-border bg-surface px-4 pb-[calc(12px+env(safe-area-inset-bottom))] pt-3"
    >
      <TtButton variant="ghost" :disabled="q.saving.value" @click="q.skip">{{ t('trades.match.skip') }}</TtButton>
      <TtButton variant="primary" block class="flex-1" :loading="q.saving.value" data-testid="match-confirm" @click="q.confirm">
        {{ t('trades.match.confirm') }}
      </TtButton>
    </footer>
  </div>
</template>
