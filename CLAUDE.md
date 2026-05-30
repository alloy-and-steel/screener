# Lynch & Graham Screener — Project Guide

## Project

GitHub Pages migration of a Python Lynch/Graham stock screener. Replaces Google Sheets output with a static interactive dashboard. See `.planning/PROJECT.md` for full context.

**Core value:** A public shareable URL showing Lynch/Graham buy signals — no Google account required.

**Stack:** Python 3.11, Tabulator 6.x (CDN), vanilla JS, GitHub Pages (`docs/`), GitHub Actions.

## GSD Workflow

This project uses Get Shit Done (GSD) for planning and execution.

**Planning artifacts:**
- `.planning/PROJECT.md` — project context and requirements
- `.planning/ROADMAP.md` — 4-phase execution plan
- `.planning/REQUIREMENTS.md` — 27 requirements with REQ-IDs
- `.planning/STATE.md` — current progress

**Phase sequence:** 1 (Security) → 2 (JSON pipeline) → 3 (Dashboard) → 4 (Cleanup)

**Workflow commands:**
- `/gsd-plan-phase N` — plan the next phase
- `/gsd-execute-phase N` — execute a planned phase
- `/gsd-progress` — view current status

## Key Decisions

- **`docs/` on `main` branch** — Pages source; no gh-pages branch
- **`docs/data/results.json`** — screener output committed by Actions
- **Tabulator 6.x via jsDelivr CDN** — no npm, no build step
- **Full Google removal in Phase 4** — Sheets stays as safety net until Phase 3 verified
- **CLN phase is always last** — never remove Google code before dashboard confirmed

## Critical Gotchas

- `.gitignore` has `*.json` — any new JSON file needs an explicit `!path/to/file.json` exception
- `GITHUB_TOKEN` needs `permissions: contents: write` in `screener.yml` — default is read-only
- `diagnose_finnhub.py` previously had a hardcoded API key — fixed in Phase 1
- Cache-bust the `results.json` fetch: `?v=${Date.now()}`
- Minimum-row guard on JSON write: abort if < 100 rows (prevents silent empty-file commits)
