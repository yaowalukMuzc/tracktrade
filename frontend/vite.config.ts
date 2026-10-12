import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'TrackTrade',
        short_name: 'TrackTrade',
        description: 'Trading Journal & Trade Lifecycle',
        lang: 'th',
        display: 'standalone',
        start_url: '/',
        background_color: '#F6F7F0',
        theme_color: '#F6F7F0',
        // TODO: add 192/512 icons once a logo mark is supplied (design-system README › Logo).
        icons: [],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,woff2}'],
        navigateFallback: '/index.html',
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
    fs: { allow: ['..'] },
  },
})
