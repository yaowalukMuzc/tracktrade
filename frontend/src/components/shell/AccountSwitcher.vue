<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import { useAccountsStore } from '@/stores/accounts'
import { useSessionStore } from '@/stores/session'

// F-02 AC3: filters every screen by "All accounts" or one account.
defineProps<{ block?: boolean }>()

const accounts = useAccountsStore()
const session = useSessionStore()
const { t } = useI18n()

const open = ref(false)
const root = ref<HTMLElement>()

const label = computed(() =>
  session.isMentor ? t('shell.mentorWorkspace') : (accounts.selected?.name ?? t('shell.allAccounts')),
)

function choose(id: string | null) {
  accounts.select(id)
  open.value = false
}

function onDocClick(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') open.value = false
}
onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div ref="root" class="relative" :class="{ 'w-full': block }">
    <button
      type="button"
      class="tt-chip"
      :class="block ? 'h-10 w-full justify-between rounded-md' : 'max-w-[180px]'"
      :aria-label="t('shell.switchAccount')"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :disabled="session.isMentor"
      @click="open = !open"
    >
      <span class="flex min-w-0 items-center gap-1.5">
        <AppIcon name="accounts" :size="16" />
        <span class="truncate">{{ label }}</span>
      </span>
      <AppIcon v-if="!session.isMentor" name="chevronDown" :size="16" />
    </button>

    <ul v-if="open" class="tt-menu mt-1" :class="block ? 'left-0 right-0' : 'right-0'" role="listbox">
      <li role="option" :aria-selected="accounts.selectedId === null">
        <button type="button" class="tt-menu__item" :class="{ 'tt-menu__item--on': accounts.selectedId === null }" @click="choose(null)">
          <span class="flex-1">{{ t('shell.allAccounts') }}</span>
          <AppIcon v-if="accounts.selectedId === null" name="check" :size="16" />
        </button>
      </li>
      <li v-for="a in accounts.active" :key="a.id" role="option" :aria-selected="accounts.selectedId === a.id">
        <button type="button" class="tt-menu__item" :class="{ 'tt-menu__item--on': accounts.selectedId === a.id }" @click="choose(a.id)">
          <span class="flex-1 whitespace-nowrap">{{ a.name }}</span>
          <AppIcon v-if="accounts.selectedId === a.id" name="check" :size="16" />
        </button>
      </li>
    </ul>
  </div>
</template>
