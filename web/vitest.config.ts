import { defineConfig } from 'vitest/config'

// Pure-logic unit tests only (no DOM): kept apart from vite.config.ts so the
// PWA plugin never runs under test.
export default defineConfig({ test: { include: ['src/**/*.test.ts'] } })
