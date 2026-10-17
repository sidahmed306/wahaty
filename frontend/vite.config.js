import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'

// En local, le site appelle le backend Django (port 8000) à travers Vite : pas de souci de CORS.
const BACKEND = 'http://127.0.0.1:8000'

const pwa = VitePWA({
  registerType: 'autoUpdate',
  injectRegister: false, // enregistré dans main.jsx : rechargement automatique à chaque nouvelle version
  includeAssets: ['favicon.png', 'apple-touch-icon.png', 'logo-mark.webp'],
  manifest: {
    name: 'TRC إرث النخيل',
    short_name: 'TRC',
    description: 'تمور واحات آدرار – Les dattes des oasis de l’Adrar',
    lang: 'ar',
    dir: 'rtl',
    start_url: '/',
    display: 'standalone',
    background_color: '#faf6ef',
    theme_color: '#189448',
    icons: [
      { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: '/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  },
  workbox: {
    // Nouvelle version : elle remplace tout de suite l'ancienne (pas de vieux code gardé en mémoire).
    skipWaiting: true,
    clientsClaim: true,
    cleanupOutdatedCaches: true,
    navigateFallback: '/index.html',
    navigateFallbackDenylist: [/^\/api\//, /^\/admin\//, /^\/media\//],
    globPatterns: ['**/*.{js,css,html,png,webp,woff2}'],
    // Polices : seulement l'arabe et le latin de base en avance (les autres alphabets au besoin).
    globIgnores: ['**/*-{cyrillic,vietnamese,latin-ext}-*.woff2'],
    runtimeCaching: [
      {
        // Pages publiques (variétés, oasis, régions) : lisibles même sans réseau.
        urlPattern: ({ url }) => /\/api\/(varieties|oases|regions)\//.test(url.pathname),
        handler: 'NetworkFirst',
        options: { cacheName: 'catalogue', networkTimeoutSeconds: 5 },
      },
      {
        urlPattern: ({ request }) => request.destination === 'font',
        handler: 'CacheFirst',
        options: { cacheName: 'fonts', expiration: { maxEntries: 20 } },
      },
      {
        urlPattern: ({ request }) => request.destination === 'image',
        handler: 'CacheFirst',
        options: {
          cacheName: 'images',
          expiration: { maxEntries: 200, maxAgeSeconds: 30 * 24 * 3600 },
        },
      },
    ],
  },
})

export default defineConfig(({ mode }) => ({
  plugins: [react(), mode === 'test' ? null : pwa],
  server: {
    proxy: {
      '/api': BACKEND,
      '/media': BACKEND,
      '/admin': BACKEND,
      '/static': BACKEND,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    css: false,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/test/**', 'src/main.jsx', 'src/**/*.test.{js,jsx}'],
    },
  },
}))
