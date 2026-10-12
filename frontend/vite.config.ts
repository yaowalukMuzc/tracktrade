/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

// Dev server proxies the API so the refresh cookie (path /api/v1/auth) stays same-origin.
// In docker compose the web container points this at http://api:8000.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

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
    fs: { allow: ['..'] },
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true, ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    css: false,
  },
})
