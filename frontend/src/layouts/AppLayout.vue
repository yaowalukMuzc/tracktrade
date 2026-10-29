<script setup lang="ts">
import { onMounted } from 'vue'
import SideNav from '@/components/shell/SideNav.vue'
import AppBar from '@/components/shell/AppBar.vue'
import BottomNav from '@/components/shell/BottomNav.vue'
import { useInboxStore } from '@/stores/inbox'

// The shell is only rendered for a signed-in user, so this is where the nav badges start updating.
const inbox = useInboxStore()
onMounted(() => inbox.start())
</script>

<template>
  <!-- ≥1024px: 240px sidebar + content. Below: AppBar + content + 5-item BottomNav. -->
  <div class="min-h-dvh bg-bg text-ink lg:flex">
    <aside class="hidden flex-none lg:sticky lg:top-0 lg:block lg:h-dvh">
      <SideNav />
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <AppBar class="lg:hidden" />
      <main class="flex-1 pb-[calc(64px+env(safe-area-inset-bottom))] lg:pb-0">
        <RouterView />
      </main>
    </div>

    <BottomNav class="fixed inset-x-0 bottom-0 z-30 lg:hidden" />
  </div>
</template>
