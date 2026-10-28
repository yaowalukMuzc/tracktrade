<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import TtButton from '@/components/ui/TtButton.vue'
import TtModal from '@/components/ui/TtModal.vue'

// Small destructive confirmation (delete setup, remove example image).
defineProps<{ title: string; body: string; confirm: string; loading?: boolean }>()
const open = defineModel<boolean>('open', { default: false })
defineEmits<{ confirm: [] }>()
const { t } = useI18n()
</script>

<template>
  <TtModal v-model:open="open" :title="title" size="sm">
    <p class="m-0 text-body text-ink-muted">{{ body }}</p>
    <slot />
    <template #footer>
      <TtButton variant="ghost" @click="open = false">{{ t('playbook.form.cancel') }}</TtButton>
      <TtButton variant="danger" icon="delete" :loading="loading" @click="$emit('confirm')">{{ confirm }}</TtButton>
    </template>
  </TtModal>
</template>
