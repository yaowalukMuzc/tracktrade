<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// screens/web/01-WLogin.png: ≥1024px split — Lavender brand panel (brand-600 + on-brand text, never white) | form.
// Below 1024px only the form column shows, on `surface` (screens/mobile/01-Main.png, 02-Register.png).
const { t } = useI18n()
const dims = ['analysis', 'planning', 'execution', 'risk', 'discipline', 'emotion'] as const
</script>

<template>
  <div class="flex min-h-dvh bg-surface text-ink lg:grid lg:grid-cols-2">
    <!-- The lavender panel looks the same in both themes, so pin its tokens to light. -->
    <section data-theme="light" class="hidden flex-col gap-8 bg-brand-600 p-12 text-on-brand lg:flex">
      <span class="tt-wordmark text-[24px] !text-on-brand">{{ t('app.name') }}</span>
      <div class="mt-auto flex max-w-[480px] flex-col gap-4">
        <h2 class="m-0 text-[40px] font-bold leading-[48px] tracking-[-0.02em]">{{ t('auth.pitchTitle') }}</h2>
        <p class="m-0 text-[17px] leading-7 opacity-90">{{ t('auth.pitchBody') }}</p>
      </div>
      <ul class="m-0 grid max-w-[480px] list-none grid-cols-3 gap-2 p-0" :aria-label="t('auth.dimensions')">
        <li v-for="d in dims" :key="d" class="auth-dim rounded-md px-3 py-2.5 text-[13px] font-semibold leading-[18px]">
          {{ t(`dimensions.${d}`) }}
        </li>
      </ul>
    </section>
    <section class="flex min-w-0 flex-1 flex-col lg:items-center lg:justify-center lg:px-6 lg:py-12">
      <slot />
    </section>
  </div>
</template>

<style scoped>
/* Translucent tile over the brand panel, derived from tokens (the mock used a raw rgba white). */
.auth-dim { background: color-mix(in srgb, var(--surface) 16%, transparent); }
</style>
