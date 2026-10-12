<script setup lang="ts">
import { ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import { useDialog } from './dialog'

// Centered dialog on `overlay` (radius-xl, shadow-lg). Used for the match queue and confirmations on desktop.
withDefaults(defineProps<{ title: string; subtitle?: string; size?: 'sm' | 'md' | 'lg'; dismissible?: boolean }>(), {
  size: 'md',
  dismissible: true,
})
const open = defineModel<boolean>('open', { default: false })
const { t } = useI18n()
const panel = ref<HTMLElement>()
const titleId = `modal-${useId()}`
useDialog(open, panel, () => (open.value = false))
</script>

<template>
  <Teleport to="body">
    <Transition name="tt-sheet">
      <div v-if="open" class="tt-scrim p-4" @click.self="dismissible && (open = false)">
        <div
          ref="panel"
          class="tt-modal"
          :class="size !== 'md' && `tt-modal--${size}`"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
        >
          <header class="tt-modal__head">
            <div class="min-w-0 flex-1">
              <h2 :id="titleId" class="tt-modal__title">{{ title }}</h2>
              <p v-if="subtitle" class="tt-modal__sub">{{ subtitle }}</p>
            </div>
            <button v-if="dismissible" type="button" class="tt-iconbtn tt-iconbtn--bare -mr-2 -mt-1" :aria-label="t('ui.close')" @click="open = false">
              <AppIcon name="close" />
            </button>
          </header>
          <slot />
          <footer v-if="$slots.footer" class="tt-modal__foot"><slot name="footer" /></footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
