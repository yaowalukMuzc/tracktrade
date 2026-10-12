<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import { directionOf, formatMoney, formatR } from '@/lib/format'

// components/PnL.md — every P/L shows a sign (+ / −); color is never the only signal.
// In `r_only` mentor views the money value is never rendered (F-22 AC2).
const props = withDefaults(
  defineProps<{
    money?: number | null
    r?: number | null
    currency?: string
    size?: 'display' | 'lg' | 'md' | 'sm'
    arrow?: boolean
    visibility?: 'currency' | 'r_only'
    compact?: boolean
  }>(),
  { currency: 'USD', size: 'md', visibility: 'currency' },
)

const showMoney = computed(() => props.visibility === 'currency' && props.money != null)
const primary = computed(() => (showMoney.value ? props.money! : (props.r ?? 0)))
const dir = computed(() => directionOf(primary.value))
const sizeClass = { display: 'text-display', lg: 'text-num-lg', md: 'text-num', sm: 'text-num-sm' }
</script>

<template>
  <span class="tt-pnl" :class="[`tt-pnl--${dir}`, sizeClass[size]]">
    <AppIcon v-if="arrow && dir !== 'flat'" :name="dir === 'up' ? 'up' : 'down'" :size="size === 'sm' ? 16 : 20" />
    <template v-if="showMoney">{{ formatMoney(money!, currency, { compact }) }}</template>
    <template v-else-if="r != null">{{ formatR(r) }}</template>
    <span v-if="showMoney && r != null" class="tt-pnl__r">{{ formatR(r) }}</span>
  </span>
</template>
