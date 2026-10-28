import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['test/**/*.spec.ts'],
    globalSetup: ['test/global-setup.ts'],
    // One shared database: run files one at a time.
    fileParallelism: false,
    testTimeout: 20_000,
    hookTimeout: 120_000,
  },
})
