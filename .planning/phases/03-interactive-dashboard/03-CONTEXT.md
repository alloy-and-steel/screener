# Phase 3: Interactive Dashboard - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the complete GitHub Pages frontend: a static `docs/index.html` + `docs/methodology.html`
that reads `docs/data/results.json` and renders a Nord-themed, dark-mode, filterable
Tabulator table with a Summary/Full column preset toggle, per-column filters, a Buy Signals
toggle, a ticker search box, and a linked methodology page with tabbed sections.

The Top 20 panel (FE-15, FE-16, FE-17) is **out of scope** — removed by user decision.

</domain>

<decisions>
## Implementation Decisions

### Summary Column Preset (FE-13)
- **D-01:** Summary preset shows exactly these 13 columns (in order):
  `Ticker`, `Price`, `CombinedScore`, `Lynch_Lynch_Status`, `Lynch_Lynch_Score`,
  `Lynch_Lynch_BuyPrice`, `Lynch_PEG_Status`, `Lynch_PEGY_Status`,
  `Graham_Graham_Status`, `Graham_Graham_Discount_Pct`, `Graham_Graham_FV`,
  `DefensiveScore`, `DefensiveLabel`
- **D-02:** Full preset shows all columns from `results.json` (all 43 columns including Error).
- **D-03:** Default view on load is Summary preset.

### Top 20 Panel — REMOVED
- **D-04:** FE-15, FE-16, FE-17 are removed from scope. No Top 20 panel. User decision.

### Visual Style
- **D-05:** Dark mode by default (no light/dark toggle). Nord color scheme throughout.
- **D-06:** Nord Polar Night palette:
  - Page background: `#2e3440`
  - Table/surface background: `#3b4252`
  - Alternating row / element: `#434c5e`
  - Muted borders/separators: `#4c566a`
  - Primary text: `#eceff4` (Snow Storm)
  - Secondary text: `#d8dee9`
  - Accent (links, active states, toggle highlights): `#88c0d0` (Frost)
- **D-07:** Traffic-light cell colors use Nord Aurora (adjusted for dark backgrounds):
  - Green (Buy / Pass / Strong Buy / Deep Buy): background `#a3be8c`, text `#2e3440`
  - Yellow (Hold / Watch / Borderline / Reasonable): background `#ebcb8b`, text `#2e3440`
  - Red (Avoid / Fail / Rich): background `#bf616a`, text `#eceff4`
  - These replace the existing `_GREEN`/`_YELLOW`/`_RED` RGB floats from `SIGNAL_COLORS`
    (those were designed for white Google Sheets cells).
- **D-08:** Page header contains: project title (`Lynch & Graham Screener`) + nav links
  (Dashboard | Methodology) + freshness badge (`Data as of [date]`), all in one top bar.
  Stale-data warning banner (FE-09) appears below the header when data > 3 days old.
- **D-09:** Row striping: Claude's discretion — subtle alternating rows using Polar Night
  surface variants (`#3b4252` / `#434c5e`) to aid readability across 40+ columns.
- **D-10:** Font: JetBrains Mono (Google Fonts) for all data cells and numeric values.
  System font stack (`-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif`) for
  headings, labels, buttons, and nav. Single Google Fonts import for JetBrains Mono.

### Methodology Page (DOC-01, DOC-02)
- **D-11:** `docs/methodology.html` uses tabbed sections (JS tabs, no page reload):
  - Tab 1: Lynch Signals (Lynch_Status, PEG_Band, scoring formula, category definitions)
  - Tab 2: Graham Signals (Graham_Status, intrinsic value versions A/B, discount %)
  - Tab 3: Defensive Checklist (8-point checklist table, scoring, DefensiveLabel thresholds)
  - Tab 4: Data Sources (Finnhub, yfinance, FRED, universe construction)
- **D-12:** Content is fully reformatted for web — NOT ported verbatim from `DOCS_CONTENT`.
  Use proper HTML: prose paragraphs, `<dl>` definition lists for signal value meanings,
  `<table>` for the 8-point defensive checklist, and `<h2>`/`<h3>` heading hierarchy.
  The `DOCS_CONTENT` in `stock_screener.py` is the canonical source of truth for facts
  and formulas; the HTML presentation should be readable documentation, not a text dump.
- **D-13:** Two-item nav (DOC-02) shared between `index.html` and `methodology.html`:
  Dashboard link | Methodology link. Active page link visually highlighted.

### Column Name Mapping (technical — no discussion needed)
- **D-14:** The actual JSON column names differ from REQUIREMENTS.md shorthand. The frontend
  MUST use the real JSON names:
  | Requirements name | Actual JSON column |
  |-------------------|--------------------|
  | Lynch_Status      | Lynch_Lynch_Status |
  | Lynch_PEG_Band    | Lynch_Lynch_PEG_Band |
  | Graham_Status     | Graham_Graham_Status |
  | Defensive         | DefensiveLabel |
  | Status_Combined   | Show |
  The `SIGNAL_COLORS` mapping in `stock_screener.py` uses the shorthand names (the dict
  was written for internal use). The frontend color logic must key off the actual JSON names.

### Claude's Discretion
- Row striping style (D-09): use subtle alternating Polar Night variants, best judgment on
  exact opacity/shade for readability with 40+ columns.
- Tab implementation: vanilla JS is fine; no need for a library just for tabs.
- Column header labels: may abbreviate long JSON names for display
  (e.g., `Lynch_Lynch_Status` → `Lynch Status`, `Graham_Graham_Discount_Pct` → `Graham Disc%`).
- Exact column widths and Tabulator layout options (frozen columns, column sizing).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Data & Color Logic
- `stock_screener.py` lines 667–716 — `SIGNAL_COLORS` dict: signal column → value → color.
  The JSON column names differ (see D-14); use this for color logic but remap to actual names.
- `docs/data/results.json` — Live data file; check actual column names and value types
  before writing any Tabulator column definitions.
- `stock_screener.py` lines 770–1068 — `DOCS_CONTENT` list: source of truth for all
  methodology text, signal definitions, formulas, and checklist criteria.

### Requirements
- `.planning/REQUIREMENTS.md` — FE-01 through FE-14, DOC-01, DOC-02 (FE-15/16/17 removed).
- `.planning/ROADMAP.md` — Phase 3 success criteria (6 items; item 5 re Top 20 is superseded
  by D-04 removal).

### Prior Phase Outputs
- `.planning/phases/01-security-pipeline-prerequisites/01-01-SUMMARY.md`
- `.planning/phases/02-json-output-pipeline/02-01-SUMMARY.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SIGNAL_COLORS` (stock_screener.py:678) — complete color mapping for all signal columns.
  Remap keys to actual JSON names (D-14) and replace RGB float values with Nord Aurora hex.
- `DOCS_CONTENT` (stock_screener.py:770) — all methodology text already written; reformat
  for HTML rather than rewriting from scratch.
- `docs/data/results.json` — 516 rows, 43 columns; already served by Pages.

### Established Patterns
- No existing frontend — `docs/` contains only `.nojekyll` and `data/.gitkeep`.
  Both HTML files (`index.html`, `methodology.html`) are new.
- Tabulator 6.x via jsDelivr CDN (decided in Phase 0 / ROADMAP.md) — no npm, no build step.
- Cache-bust fetch: `fetch('data/results.json?v=' + Date.now())` (CLAUDE.md gotcha).

### Integration Points
- `docs/index.html` fetches `docs/data/results.json` (relative path: `data/results.json`).
- `docs/methodology.html` has no data dependency — static content only.
- Both pages share the same nav and Nord CSS — extract shared styles to a `docs/style.css`.

</code_context>

<specifics>
## Specific Ideas

- Nord color scheme reference: https://www.nordtheme.com/docs/colors-and-palettes
  (Polar Night for backgrounds, Snow Storm for text, Frost for accents, Aurora for signals)
- JetBrains Mono via Google Fonts:
  `<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">`
- Tabulator dark theme: Tabulator 6.x ships a `tabulator-midnight` theme via CDN —
  use it as a base and override with Nord Polar Night colors.
- Tab pattern for methodology: simple `<button class="tab-btn">` array with
  `aria-selected`, toggling `hidden` on `<section>` panels. No library needed.
- `Show` column (bool as string "True"/"False") is the buy-signal filter column (FE-11).
  Tabulator filter: `function(headerValue, rowValue) { return rowValue === "True"; }`

</specifics>

<deferred>
## Deferred Ideas

- Top 20 panel (FE-15, FE-16, FE-17) — removed by user decision; not deferred to a future
  phase, simply not wanted.
- Dark/light mode toggle — v2 backlog (already in ROADMAP.md deferred items).
- Column visibility picker beyond Summary/Full — v2 backlog.

</deferred>

---

*Phase: 3-Interactive Dashboard*
*Context gathered: 2026-05-30*
