<script setup lang="ts">
import { computed } from 'vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtRadioCard from '@/components/ui/TtRadioCard.vue'
import type { IconName } from '@/lib/icons'
import { useOnboarding, type ImportMethod } from './useOnboarding'

// Import-method choice (F-08 preview). Broker sync ships in Phase 4, so MT5 / cTrader are marked "coming soon"
// and only explained — no fake API key or "connected" state. The choice is not persisted yet.
const { state, t } = useOnboarding()

const options = computed<{ value: ImportMethod; icon: IconName; title: string; subtitle: string; later: boolean }[]>(() => [
  { value: 'mt5', icon: 'connection', title: t('onboarding.import.mt5'), subtitle: t('onboarding.import.mt5Sub'), later: true },
  { value: 'ctrader', icon: 'link', title: t('onboarding.import.ctrader'), subtitle: t('onboarding.import.ctraderSub'), later: true },
  { value: 'manual', icon: 'scan', title: t('onboarding.import.manual'), subtitle: t('onboarding.import.manualSub'), later: false },
])
</script>

<template>
  <section class="tt-card tt-stack max-lg:!border-0 max-lg:!bg-transparent max-lg:!p-0" aria-labelledby="ob-import">
    <div class="flex items-center justify-between gap-2 max-lg:hidden">
      <h2 id="ob-import" class="m-0 text-h3">{{ t('onboarding.import.title') }}</h2>
      <span class="text-caption text-ink-muted">{{ t('onboarding.import.hint') }}</span>
    </div>
    <div role="radiogroup" :aria-label="t('onboarding.import.label')" class="grid gap-3 lg:grid-cols-2">
      <TtRadioCard
        v-for="o in options"
        :key="o.value"
        v-model="state.method"
        name="import-method"
        :value="o.value"
        :icon="o.icon"
        :title="o.title"
        :subtitle="o.subtitle"
        :badge="o.later ? t('onboarding.import.later') : undefined"
      />
    </div>
    <TtAlert v-if="state.method !== 'manual'" :title="t('onboarding.import.laterTitle')" :body="t('onboarding.import.laterBody')" />
  </section>
</template>
