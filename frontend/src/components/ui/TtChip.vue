<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'

// components/Chip.md — selectable pill for multi-select tags. Emotion tags carry valence.
withDefaults(
  defineProps<{
    selected?: boolean
    valence?: 'pos' | 'neg' | 'neutral'
    /** Dashed "create tag" chip. */
    add?: boolean
    dot?: boolean
    size?: 'sm' | 'md'
  }>(),
  { size: 'md' },
)
defineEmits<{ click: [MouseEvent] }>()
</script>

<template>
  <button
    type="button"
    class="tt-chip"
    :class="{
      'tt-chip--on': selected,
      'tt-chip--pos': valence === 'pos',
      'tt-chip--neg': valence === 'neg',
      'tt-chip--add': add,
      'tt-chip--sm': size === 'sm',
    }"
    :aria-pressed="add ? undefined : !!selected"
    @click="$emit('click', $event)"
  >
    <AppIcon v-if="add" name="add" :size="16" />
    <i v-else-if="dot" class="tt-chip__dot" />
    <slot />
  </button>
</template>
