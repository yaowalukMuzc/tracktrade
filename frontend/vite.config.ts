/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

// Dev server proxies both backends on the same origin, so the Better Auth session cookie is first-party:
//   /api/auth/* -> auth service (Better Auth), everything else under /api -> FastAPI (+ WebSocket).
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'
const authTarget = process.env.AUTH_PROXY_TARGET ?? 'http://localhost:3000'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'TrackTrade',
        short_name: 'TrackTrade',
        description: 'Trading Journal & Trade Lifecycle',
        lang: 'th',
        display: 'standalone',
        start_url: '/',
        // Manifest colors can't read CSS variables: these are tokens.json `bg` (light) values.
        background_color: '#F6F7F0',
        theme_color: '#F6F7F0',
        // Temporary "TT" mark on brand-600 until a logo is supplied (PLAN §8.2). Regenerate: npm run icons.
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@ds': fileURLToPath(new URL('../design-system', import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5179,
    strictPort: true,
    fs: { allow: ['..'] },
    proxy: {
      // Host header is kept (no changeOrigin): Better Auth checks Origin against its trusted origins.
      '/api/auth': { target: authTarget },
      '/api': { target: apiTarget, changeOrigin: true, ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    css: false,
  },
})
