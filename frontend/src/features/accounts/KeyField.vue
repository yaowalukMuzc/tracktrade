<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import TtButton from '@/components/ui/TtButton.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'

// API key in a sunken mono box + copy (screens/source/WAccounts.dc.html `.code`). The full key exists only right
// after it was created (PLAN M13); with just the masked hint the copy button stays disabled and says why.
// `copyButton`: a labelled "คัดลอก key" button under the box instead of the icon (04-ConnectBroker), + #actions slot.
const props = defineProps<{ display: string; copyValue?: string | null; label: string; copyButton?: boolean }>()
const { t } = useI18n()
const copied = ref(false)

async function copy() {
  if (!props.copyValue) return
  try {
    await navigator.clipboard.writeText(props.copyValue)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    /* clipboard blocked — the key is still selectable */
  }
}
</script>

<template>
  <div class="tt-field">
    <span class="tt-label">{{ label }}</span>
    <div class="flex gap-2">
      <code
        class="min-w-0 flex-1 select-all break-all rounded-sm bg-surface-sunken px-3 py-2.5 font-mono text-[13px] font-medium leading-5 text-ink"
        data-testid="api-key"
      >{{ display }}</code>
      <TtIconButton
        v-if="!copyButton"
        :icon="copied ? 'check' : 'copy'"
        :label="copied ? t('connections.mt5.copied') : copyValue ? t('connections.mt5.copy') : t('connections.mt5.copyHidden')"
        :disabled="!copyValue"
        :title="copyValue ? undefined : t('connections.mt5.copyHidden')"
        @click="copy"
      />
    </div>
    <div v-if="copyButton" class="mt-2 flex flex-wrap items-center gap-2">
      <TtButton variant="secondary" size="sm" :icon="copied ? 'check' : 'copy'" :disabled="!copyValue" @click="copy">
        {{ copied ? t('connections.mt5.copied') : t('connections.mt5.copyKey') }}
      </TtButton>
      <slot name="actions" />
    </div>
    <span class="sr-only" role="status"><template v-if="copied">{{ t('connections.mt5.copied') }}</template></span>
  </div>
</template>
