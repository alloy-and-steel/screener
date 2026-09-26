import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// Project Pages site is served under /screener/, so assets and the same-origin
// data fetch resolve against that base (import.meta.env.BASE_URL).
//
// Dedicated port 7273 = "SCRE"(ener) on a phone keypad — memorable, and clear of
// pie's lab/trader dev servers. strictPort fails loudly if 7273 is taken rather
// than silently hopping to another port (so the screener is always at the URL
// you expect). Dev: http://localhost:7273/screener/
export default defineConfig({
  base: '/screener/',
  plugins: [
    react(),
    tailwindcss(),
    // Service worker: the app shell is precached, so the site opens instantly
    // and offline. `prompt` = a new deploy waits in the background until the
    // user taps "Update" (Toasts.tsx) instead of swapping code under them.
    VitePWA({
      registerType: 'prompt',
      injectRegister: false, // registered by useRegisterSW in Toasts.tsx
      manifest: {
        name: 'Screener3000',
        short_name: 'Screener',
        description: 'Three independent stock screens — Azqato, Lynch, Graham — over the S&P 500, Dow, Nasdaq-100 and more.',
        theme_color: '#0b0d10',
        background_color: '#0b0d10',
        display: 'standalone',
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // The dataset is NOT precached: it changes every weekday without the
        // app changing. Network-first keeps it current online and serves the
        // last copy offline; useDataset.ts polls it to offer fresh data.
        globPatterns: ['**/*.{js,css,html,svg,png}'],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.endsWith('/data/results.json'),
            handler: 'NetworkFirst',
            options: { cacheName: 'screener-data', networkTimeoutSeconds: 6, expiration: { maxEntries: 2 } },
          },
        ],
      },
    }),
  ],
  server: { port: 7273, strictPort: true },
  preview: { port: 7273, strictPort: true },
})
