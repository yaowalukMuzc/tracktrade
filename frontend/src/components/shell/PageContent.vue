<template>
  <!-- Gutter space-4 mobile / space-6 ≥768 / 32px desktop; content max 1240px (screens.css .content). -->
  <div class="flex w-full max-w-[1240px] flex-col gap-3 px-4 py-4 md:gap-6 md:px-6 lg:px-8 lg:pb-10 lg:pt-6">
    <slot />
  </div>
</template>
