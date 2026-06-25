import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Project Pages site is served under /screener/, so assets and the same-origin
// data fetch resolve against that base (import.meta.env.BASE_URL).
//
// Dedicated port 7273 = "SCRE"(ener) on a phone keypad — memorable, and clear of
// pie's lab/trader dev servers. strictPort fails loudly if 7273 is taken rather
// than silently hopping to another port (so the screener is always at the URL
// you expect). Dev: http://localhost:7273/screener/
export default defineConfig({
  base: '/screener/',
  plugins: [react(), tailwindcss()],
  server: { port: 7273, strictPort: true },
  preview: { port: 7273, strictPort: true },
})
