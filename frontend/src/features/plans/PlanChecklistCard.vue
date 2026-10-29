<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtBadge from '@/components/ui/TtBadge.vue'

// components/Checklist.md — setup checklist inside the plan (F-06 AC3). Required items block the lock;
// after a lock attempt the missing ones get `tt-check--missing` and the card a loss border.
const props = defineProps<{
  setupName: string
  items: { id: string; text: string; is_required: boolean; checked: boolean }[]
  /** Required ids to flag (after a lock attempt). */
  missing: string[]
  highlight: boolean
  readonly: boolean
}>()
const emit = defineEmits<{ toggle: [id: string] }>()
const { t } = useI18n()

const done = computed(() => props.items.filter((i) => i.checked).length)
const requiredOk = computed(() => props.items.every((i) => !i.is_required || i.checked))
</script>

<template>
  <section class="tt-card pb-1" :class="{ '!border-loss': highlight }" data-testid="plan-checklist">
    <div class="flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">
        {{ setupName ? t('plans.sections.checklist', { setup: setupName }) : t('plans.sections.checklistPlain') }}
      </h2>
      <TtBadge v-if="items.length" :variant="requiredOk ? 'profit' : 'warning'" class="tt-num">
        {{ t('plans.checklist.count', { done, total: items.length }) }}
      </TtBadge>
    </div>
    <p v-if="!items.length" class="m-0 py-3 text-body-sm text-ink-muted">{{ t('plans.checklist.empty') }}</p>
    <div class="flex flex-col" :class="{ 'mt-1': items.length }">
      <button
        v-for="item in items"
        :key="item.id"
        type="button"
        role="checkbox"
        class="tt-check"
        :class="{ 'tt-check--done': item.checked, 'tt-check--missing': !item.checked && missing.includes(item.id) }"
        :aria-checked="item.checked"
        :disabled="readonly"
        @click="emit('toggle', item.id)"
      >
        <span class="tt-check__box"><AppIcon v-if="item.checked" name="check" :size="16" /></span>
        <span class="tt-check__text">
          {{ item.text }}
          <TtBadge v-if="item.is_required" :variant="!item.checked && missing.includes(item.id) ? 'loss' : 'neutral'" class="ml-1 align-middle">
            {{ t('plans.checklist.required') }}
          </TtBadge>
        </span>
      </button>
    </div>
    <p v-if="readonly && items.length" class="m-0 pb-3 text-caption text-ink-subtle">{{ t('plans.checklist.frozen') }}</p>
  </section>
</template>
