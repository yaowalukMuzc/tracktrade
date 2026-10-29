<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import EaInstallSteps from './EaInstallSteps.vue'
import KeyField from './KeyField.vue'

// The one time the full API key is visible (F-08 AC1, NFR "keys stored hashed", PLAN M13).
defineProps<{ accountName: string; apiKey: string }>()
const open = defineModel<boolean>('open', { default: false })
const { t } = useI18n()
</script>

<template>
  <TtResponsiveDialog v-model:open="open" :title="t('connections.key.title', { name: accountName })">
    <div class="tt-stack">
      <TtAlert variant="warning" icon="key" :title="t('connections.key.once')" />
      <KeyField :label="t('connections.key.label')" :display="apiKey" :copy-value="apiKey" />
      <EaInstallSteps />
    </div>
    <template #footer>
      <TtButton variant="primary" @click="open = false">{{ t('connections.key.done') }}</TtButton>
    </template>
  </TtResponsiveDialog>
</template>
