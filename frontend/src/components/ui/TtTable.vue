<script setup lang="ts" generic="R extends Record<string, unknown>">
// screens.css .tbl — sunken header, hairline rows, numbers right-aligned + tabular. Wide tables scroll inside the box.
export interface Column {
  key: string
  label: string
  align?: 'left' | 'right' | 'center'
  width?: string
}

const props = defineProps<{
  columns: Column[]
  rows: R[]
  rowKey: keyof R
  /** Shown when `rows` is empty. */
  empty?: string
  /** Accessible table caption (visually hidden). */
  caption?: string
  minWidth?: string
  clickable?: boolean
}>()
const emit = defineEmits<{ rowClick: [row: R] }>()

const alignClass = (a?: Column['align']) => (a === 'right' ? 'tt-tbl__r' : a === 'center' ? 'tt-tbl__c' : undefined)
function onRowKey(e: KeyboardEvent, row: R) {
  if (props.clickable && (e.key === 'Enter' || e.key === ' ')) {
    e.preventDefault()
    emit('rowClick', row)
  }
}
</script>

<template>
  <div class="tt-tblwrap">
    <table class="tt-tbl" :style="{ minWidth }">
      <caption v-if="caption" class="sr-only">{{ caption }}</caption>
      <thead>
        <tr>
          <th v-for="c in columns" :key="c.key" scope="col" :class="alignClass(c.align)" :style="{ width: c.width }">{{ c.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="String(row[rowKey])"
          :class="{ 'tt-tbl__link': clickable }"
          :tabindex="clickable ? 0 : undefined"
          @click="clickable && emit('rowClick', row)"
          @keydown="onRowKey($event, row)"
        >
          <td v-for="c in columns" :key="c.key" :class="alignClass(c.align)">
            <slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]">{{ row[c.key] }}</slot>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="tt-tbl__empty">{{ empty }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
