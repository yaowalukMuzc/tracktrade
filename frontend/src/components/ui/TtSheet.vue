<script setup lang="ts">
import { ref, useId } from 'vue'
import { useDialog } from './dialog'

// Bottom sheet for quick logging (in-trade prompt, daily mood, revision reason, day detail).
// Slides up 250ms ease-out with radius-xl top corners (README › Screen patterns). Desktop callers usually prefer TtModal.
defineProps<{ title: string; subtitle?: string }>()
const open = defineModel<boolean>('open', { default: false })
const panel = ref<HTMLElement>()
const titleId = `sheet-${useId()}`
useDialog(open, panel, () => (open.value = false))
</script>

<template>
  <Teleport to="body">
    <Transition name="tt-sheet">
      <div v-if="open" class="tt-scrim" @click.self="open = false">
        <div ref="panel" class="tt-sheet md:mx-auto md:max-w-[560px]" role="dialog" aria-modal="true" :aria-labelledby="titleId" tabindex="-1">
          <span class="tt-sheet__grab" aria-hidden="true" />
          <header>
            <h2 :id="titleId" class="m-0 text-h3">{{ title }}</h2>
            <p v-if="subtitle" class="m-0 text-body-sm text-ink-muted">{{ subtitle }}</p>
          </header>
          <slot />
          <footer v-if="$slots.footer" class="flex gap-2"><slot name="footer" /></footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
