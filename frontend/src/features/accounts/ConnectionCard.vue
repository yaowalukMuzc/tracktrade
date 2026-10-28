<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import type { Account } from '@/api/accounts'

// Broker connection of the selected account. MT5 EA / cTrader sync is Phase 4 (F-08): until then
// every account shows "ไม่เชื่อมต่อ" and says so plainly — no fake API key or sync status.
defineProps<{ account: Account }>()
const { t } = useI18n()
</script>

<template>
  <section class="tt-card tt-stack">
    <div class="flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">
        {{ t('accounts.connection.cardTitle', { platform: t(`accounts.platform.${account.platform}`), broker: account.broker }) }}
      </h2>
      <TtBadge variant="outline">{{ t('accounts.connection.none') }}</TtBadge>
    </div>
    <p class="m-0 text-body-sm text-ink-muted">
      {{ account.platform === 'manual' ? t('accounts.connection.manual') : t('accounts.connection.notYet') }}
    </p>
  </section>
</template>
