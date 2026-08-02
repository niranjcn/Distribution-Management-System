import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: true,
  },
  plugins: [
    react(),
    VitePWA({
      // autoUpdate: the new service worker calls skipWaiting() on install so a
      // stale worker never keeps intercepting /api after a deploy. (With
      // 'prompt', old workers stayed active and bypassed the HTTP cache.)
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'logo.png'],
      manifest: {
        name: 'KannurVision PDIC — Distribution Management',
        short_name: 'KannurVision PDIC',
        description: 'KannurVision PDIC Network Manager — Track devices, manage distributions, approvals, returns, and defects.',
        theme_color: '#166534',
        background_color: '#ffffff',
        display: 'standalone',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/icons/icon-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/icons/icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/icons/icon-maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        navigateFallback: '/index.html',
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        // NOTE: API requests are deliberately NOT cached by the service worker.
        // Letting them fall through to the browser's native HTTP cache lets the
        // backend's ETag / 304 conditional caching work directly (browser sends
        // If-None-Match, backend returns 304 without running the endpoint).
        // This drops offline API support in exchange for a faster online
        // experience. See backend app/middleware/conditional_cache.py.
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365,
              },
            },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    open: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      }
    }
  },
  preview: {
    open: false,
  },
})
