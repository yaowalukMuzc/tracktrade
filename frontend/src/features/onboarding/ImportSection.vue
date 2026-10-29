<script setup lang="ts">
import { computed, watch } from 'vue'
import TtRadioCard from '@/components/ui/TtRadioCard.vue'
import type { IconName } from '@/lib/icons'
import { useOnboarding, type ImportMethod } from './useOnboarding'

// "ถัดไป: นำเข้าเทรด" (screens/web/02-WOnboarding.png). The method and the account's platform are the same choice
// seen from two sides, so they stay in step: MT5 (EA) ⇄ platform MT5, cTrader ⇄ cTrader, Screenshot ⇄ manual.
const { state, t } = useOnboarding()

const options = computed<{ value: ImportMethod; icon: IconName; title: string; subtitle: string }[]>(() => [
  { value: 'mt5', icon: 'connection', title: t('onboarding.import.mt5'), subtitle: t('onboarding.import.mt5Sub') },
  { value: 'ctrader', icon: 'link', title: t('onboarding.import.ctrader'), subtitle: t('onboarding.import.ctraderSub') },
  { value: 'manual', icon: 'scan', title: t('onboarding.import.manual'), subtitle: t('onboarding.import.manualSub') },
])

watch(
  () => state.form.platform,
  (p) => (state.method = p),
  { immediate: true },
)
watch(
  () => state.method,
  (m) => (state.form.platform = m),
)
</script>

<template>
  <section class="tt-card tt-stack" aria-labelledby="ob-import">
    <div class="flex items-center justify-between gap-2">
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
      />
    </div>
  </section>
</template>
