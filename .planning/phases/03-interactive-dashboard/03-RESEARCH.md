# Phase 3: Interactive Dashboard - Research

**Researched:** 2026-05-30
**Domain:** Static GitHub Pages dashboard — Tabulator 6.x, Nord CSS, vanilla JS
**Confidence:** HIGH (CDN URLs verified against live CDN; Tabulator API cross-verified via npm registry, GitHub source, and official documentation references)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Summary preset shows exactly these 13 columns (in order): `Ticker`, `Price`, `CombinedScore`, `Lynch_Lynch_Status`, `Lynch_Lynch_Score`, `Lynch_Lynch_BuyPrice`, `Lynch_PEG_Status`, `Lynch_PEGY_Status`, `Graham_Graham_Status`, `Graham_Graham_Discount_Pct`, `Graham_Graham_FV`, `DefensiveScore`, `DefensiveLabel`
- **D-02:** Full preset shows all columns from `results.json` (all 43 columns including Error).
- **D-03:** Default view on load is Summary preset.
- **D-04:** FE-15, FE-16, FE-17 (Top 20 panel) are removed from scope.
- **D-05:** Dark mode by default (no light/dark toggle). Nord color scheme throughout.
- **D-06:** Nord Polar Night palette: page background `#2e3440`, table/surface `#3b4252`, alternating row `#434c5e`, muted borders `#4c566a`, primary text `#eceff4`, secondary text `#d8dee9`, accent `#88c0d0`
- **D-07:** Traffic-light cell colors — Green: `#a3be8c` bg / `#2e3440` text; Yellow: `#ebcb8b` bg / `#2e3440` text; Red: `#bf616a` bg / `#eceff4` text
- **D-08:** Header: project title + nav links + freshness badge. Stale-data warning banner (FE-09) below header when data > 3 days old.
- **D-09:** Row striping: Claude's discretion — subtle alternating Polar Night variants (`#3b4252` / `#434c5e`).
- **D-10:** Font: JetBrains Mono (Google Fonts) for data cells/numerics. System font stack for headings/labels/buttons/nav.
- **D-11:** `docs/methodology.html` uses JS tabs (no page reload): Lynch Signals | Graham Signals | Defensive Checklist | Data Sources
- **D-12:** Methodology content reformatted for web from `DOCS_CONTENT` in `stock_screener.py`. HTML with prose, `<dl>`, `<table>`, heading hierarchy.
- **D-13:** Two-item nav shared between both pages. Active page link visually highlighted.
- **D-14:** Actual JSON column names differ from REQUIREMENTS.md shorthand (e.g., `Lynch_Lynch_Status` not `Lynch_Status`; `Show` not `Status_Combined`).

### Claude's Discretion
- Row striping style (D-09): subtle alternating Polar Night variants, best judgment on exact opacity/shade.
- Tab implementation: vanilla JS, no library.
- Column header labels: may abbreviate long JSON names.
- Exact column widths and Tabulator layout options (frozen columns, column sizing).

### Deferred Ideas (OUT OF SCOPE)
- Top 20 panel (FE-15, FE-16, FE-17) — removed by user decision.
- Dark/light mode toggle — v2 backlog.
- Column visibility picker beyond Summary/Full — v2 backlog.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FE-01 | Load Tabulator 6.x from jsDelivr CDN | Section 1: exact CDN URLs verified |
| FE-02 | All columns, sorted by `CombinedScore` desc on load | `initialSort` option; confirmed column name from JSON |
| FE-03 | Ticker column frozen | `frozen: true` in column definition |
| FE-04 | Header row sticky | Tabulator default behavior with `height` set on table container |
| FE-05 | Traffic-light background colors for signal columns | Cell formatter pattern; SIGNAL_COLORS mapping; Nord Aurora hex |
| FE-06 | Null/NaN displays as `—` | Custom formatter null-check pattern |
| FE-07 | Error rows hidden by default, toggle to reveal | `setFilter`/`addFilter` with custom function on `Error` column |
| FE-08 | "Data as of [date]" freshness badge | `generated_at` field from JSON; vanilla JS date formatting |
| FE-09 | Stale-data warning banner if data > 3 days | Date comparison in JS; conditional DOM show/hide |
| FE-10 | Cache-busting fetch | `fetch('data/results.json?v=' + Date.now())` |
| FE-11 | "Buy Signals Only" toggle — filter `Show === true` | `setFilter`/`removeFilter` on `Show` field |
| FE-12 | Per-column header filters: dropdown for categoricals, numeric for numerics | `headerFilter: "list"` with `valuesLookup: true`; `headerFilter: "input"` with `headerFilterFunc` |
| FE-13 | Summary/Full column preset toggle | `showColumn`/`hideColumn` API; defined column list from D-01 |
| FE-14 | Ticker text search box (client-side, instant filter) | `setFilter`/`removeFilter` on `Ticker` field with `like` comparator |
| DOC-01 | `docs/methodology.html` with ported methodology content | Vanilla JS tab pattern; DOCS_CONTENT canonical source |
| DOC-02 | Two-item nav header shared between pages | Shared `docs/style.css`; relative path `./style.css` |
</phase_requirements>

---

## Summary

Phase 3 builds a fully static GitHub Pages dashboard with no build step, no npm, and no server-side rendering. The sole runtime dependencies are Tabulator 6.4.0 (loaded from jsDelivr CDN) and JetBrains Mono (Google Fonts CDN). All other code is vanilla JS and hand-written CSS.

The data file (`docs/data/results.json`) has been confirmed to contain 516 rows and 43 columns. The top-level structure is `{ generated_at: "ISO string", rows: [...] }`. Column types are a mix of float, str, and bool — notably `Show` is a Python bool serialized to JSON as `true`/`false` (lowercase), and `Error` is `NaN` serialized as JSON `null` for normal rows and a float/string for error rows.

The Nord theme is applied by overriding the `tabulator_midnight` base CSS. That base theme uses direct hex values (not CSS custom properties), so overrides require targeting the same selectors with higher specificity or using a small custom CSS block after the CDN stylesheet.

**Primary recommendation:** Load Tabulator 6.4.0 via jsDelivr, use `headerFilter: "list"` with `valuesLookup: true` for categorical dropdowns, use `setFilter`/`removeFilter` for all programmatic filter actions, and apply Nord colors via a `docs/style.css` that overrides the midnight theme selectors.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Data fetch and parse | Browser / Client | — | Static file; no server needed |
| Table rendering and filtering | Browser / Client (Tabulator) | — | Client-side only; CDN library |
| Color coding / formatters | Browser / Client (Tabulator) | — | Cell formatters run in browser |
| Column preset toggle | Browser / Client | — | JS show/hide column API |
| Buy signal toggle | Browser / Client | — | Tabulator setFilter API |
| Error row toggle | Browser / Client | — | Tabulator setFilter API |
| Ticker search | Browser / Client | — | Tabulator setFilter with "like" |
| Freshness badge | Browser / Client | — | JS date math on generated_at |
| Navigation | Browser / Client | — | HTML href + CSS active-page highlight |
| Methodology tabs | Browser / Client | — | Vanilla JS tab pattern |
| CSS / styling | CDN / Static | Browser (overrides) | jsDelivr for base, docs/style.css for overrides |

---

## 1. Tabulator 6.x CDN URLs

**Package verified:** `tabulator-tables@6.4.0` on npm registry, published 2026-05-18. [VERIFIED: npm registry]

The file `tabulator.min.js` from jsDelivr self-reports `Tabulator v6.4.0 (c) Oliver Folkerd 2026`, confirming the CDN serves valid content. [VERIFIED: jsDelivr CDN]

```html
<!-- Tabulator 6.4.0 — midnight dark theme base -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tabulator-tables@6.4.0/dist/css/tabulator_midnight.min.css">

<!-- Tabulator 6.4.0 — core JS -->
<script src="https://cdn.jsdelivr.net/npm/tabulator-tables@6.4.0/dist/js/tabulator.min.js"></script>
```

**Available theme CSS files in `dist/css/`** (verified by fetching directory listing from jsDelivr): [VERIFIED: jsDelivr CDN]
- `tabulator_midnight.min.css` — dark base; use this
- `tabulator.min.css` — default light
- `tabulator_bootstrap5.min.css`, `tabulator_bulma.min.css`, etc. (not needed)

**Pin to 6.4.0, not `latest`** — unpinned CDN URLs break on major releases.

---

## 2. Tabulator Column Definition Patterns

### 2a. Frozen Column (FE-03)

```javascript
// Source: tabulator.info/docs/6.3/columns
{ title: "Ticker", field: "Ticker", frozen: true, width: 80 }
```

**Pitfall:** `frozen: true` combined with `layout: "fitDataFill"` can produce a spurious horizontal scrollbar (GitHub issue #2908). Use `layout: "fitData"` or set explicit `width` on the frozen column to avoid this. [VERIFIED: GitHub tabulator-tables issues]

### 2b. Basic Numeric Column

```javascript
{
  title: "Price",
  field: "Price",
  sorter: "number",
  formatter: numericFormatter,   // custom null-safe formatter (see Section 5)
  headerFilter: "input",
  headerFilterFunc: ">=",        // filter rows where value >= input
  headerFilterPlaceholder: "min"
}
```

### 2c. Signal Column with Color Formatter

```javascript
{
  title: "Lynch Status",
  field: "Lynch_Lynch_Status",
  formatter: signalFormatter,    // custom formatter (see Section 5)
  headerFilter: "list",
  headerFilterParams: { valuesLookup: true, clearable: true }
}
```

### 2d. Boolean Column (`Show`)

The `Show` field arrives from JSON as `true` or `false` (JSON boolean). [VERIFIED: py inspection of results.json]

```javascript
{
  title: "Buy?",
  field: "Show",
  visible: false,   // hidden column — only used for programmatic filter
}
```

### 2e. `initialSort` (FE-02)

```javascript
// Source: confirmed via tabulator Sort.js module + WebSearch cross-reference
var table = new Tabulator("#table", {
  initialSort: [
    { column: "CombinedScore", dir: "desc" }
  ]
});
```

### 2f. Layout Options

`layout: "fitData"` — columns size to their content; table may be narrower than container.
`layout: "fitDataFill"` — same as fitData but rows fill the full container width. **Avoid with frozen columns** (see pitfall in 2a).
`layout: "fitColumns"` — columns stretch to fill container; impractical for 43 columns. [VERIFIED: tabulator.info/docs/6.3/layout via WebSearch cross-reference]

**Recommendation for this project:** Use `layout: "fitData"` with a `height` CSS style on the table container. This avoids the frozen-column/fitDataFill bug and keeps horizontal scrolling clean.

### 2g. `renderHorizontal: "virtual"` — Do Not Use

The horizontal virtual DOM is experimental and has known de-sync issues with headers at large column counts (40+). Issues #3551 and #3741 on the Tabulator GitHub repo document header/content misalignment and poor toggle performance. [VERIFIED: GitHub tabulator-tables issues]

**Recommendation:** Do not set `renderHorizontal: "virtual"` for this project. Vertical virtual rendering (`renderVertical: "virtual"`) is the default and is reliable for 516 rows.

---

## 3. Tabulator Filter Patterns

### 3a. Dropdown Header Filter for Categorical Columns (FE-12)

Use `headerFilter: "list"` with `valuesLookup: true`. This auto-populates the dropdown from unique values in the column — no hardcoded option list needed. [CITED: tabulator.info/docs/6.4/filter via WebSearch]

```javascript
{
  title: "Lynch Status",
  field: "Lynch_Lynch_Status",
  headerFilter: "list",
  headerFilterParams: {
    valuesLookup: true,   // reads unique values from column data
    clearable: true       // adds an X button to clear the filter
  }
}
```

Applies to: `Lynch_Lynch_Status`, `Lynch_Lynch_Category`, `Lynch_Lynch_PEG_Band`, `Lynch_PEG_Status`, `Lynch_PEGY_Status`, `Graham_Graham_Status`, `DefensiveLabel`, `Indexes`.

### 3b. Numeric Header Filter (FE-12)

For numeric columns, use `headerFilter: "input"` with `headerFilterFunc: ">="` (or `<=`). This gives a simple text input that acts as a minimum threshold filter.

```javascript
{
  title: "Price",
  field: "Price",
  sorter: "number",
  headerFilter: "input",
  headerFilterFunc: ">=",
  headerFilterPlaceholder: "≥"
}
```

Alternative for exact-match or contains: use `headerFilterFunc: "like"` for string partial match.

### 3c. Programmatic Buy Signals Toggle (FE-11)

The `Show` column is a JSON boolean (`true`/`false`). [VERIFIED: py inspection of results.json]

```javascript
// Button toggle — active state
function enableBuyFilter() {
  table.setFilter("Show", "=", true);
}

function clearBuyFilter() {
  table.removeFilter("Show", "=", true);
}
```

### 3d. Error Row Hide/Show Toggle (FE-07)

The `Error` column is `null` for normal rows (Python `NaN` serializes to JSON `null`) and a non-null value for error rows. [VERIFIED: py inspection of results.json]

Default state: hide error rows (apply filter on load).

```javascript
// Custom filter function — show only rows where Error is null/undefined
function noErrorFilter(data) {
  return data.Error === null || data.Error === undefined;
}

// Apply on table load (error rows hidden by default)
table.setFilter(noErrorFilter);

// Toggle button
let errorsVisible = false;
function toggleErrors() {
  errorsVisible = !errorsVisible;
  if (errorsVisible) {
    table.removeFilter(noErrorFilter);
  } else {
    table.setFilter(noErrorFilter);
  }
}
```

**Important:** `removeFilter` requires passing the same function reference — store it in a variable, not inline. [ASSUMED — based on standard JS function reference equality; consistent with how Tabulator docs describe filter removal]

### 3e. Ticker Text Search (FE-14)

```javascript
// Source: Tabulator setFilter with "like" comparator
const searchInput = document.getElementById("ticker-search");
searchInput.addEventListener("input", function() {
  const val = this.value.trim();
  if (val) {
    table.setFilter("Ticker", "like", val.toUpperCase());
  } else {
    table.removeFilter("Ticker", "like", "");
  }
});
```

### 3f. Multiple Active Filters

`setFilter` replaces all programmatic filters. To stack the buy-signal filter AND the error-row filter, use an array:

```javascript
// Apply both filters together
table.setFilter([
  { field: "Show", type: "=", value: true },
  noErrorFilter   // function-type filter in array
]);
```

Or use `addFilter` to add to existing filters:
```javascript
table.addFilter("Show", "=", true);   // stacks on top of existing filters
```

**Note:** Header filters are separate from programmatic filters and are not cleared by `setFilter`. [CITED: tabulator.info/docs/6.4/filter via WebSearch]

---

## 4. Cell Color Formatter Patterns

### 4a. Signal Column Formatter (FE-05)

The `SIGNAL_COLORS` dict in `stock_screener.py` uses shorthand names. The frontend must remap to actual JSON column names (D-14). Nord Aurora colors replace the RGB float values.

**Color mapping (from D-07):**
- Green (Strong Buy, Buy, Deep Buy, Pass, Cheap): `#a3be8c` bg, `#2e3440` text
- Yellow (Hold, Watch, Borderline, Reasonable): `#ebcb8b` bg, `#2e3440` text
- Red (Avoid, Fail, Rich): `#bf616a` bg, `#eceff4` text

```javascript
// Source: Tabulator formatter documentation (tabulator.info/docs/6.4/format)
const SIGNAL_COLORS = {
  Lynch_Lynch_Status: {
    "Strong Buy": "green", "Buy": "green",
    "Hold": "yellow", "Avoid": "red"
  },
  Lynch_PEG_Status: {
    "Cheap": "green", "Reasonable": "yellow", "Rich": "red"
  },
  Lynch_PEGY_Status: {
    "Cheap": "green", "Reasonable": "yellow", "Rich": "red"
  },
  Lynch_Lynch_PEG_Band: {
    "Strong Buy": "green", "Buy": "green",
    "Hold": "yellow", "Avoid": "red"
  },
  Graham_Graham_Status: {
    "Deep Buy": "green", "Buy": "green",
    "Watch": "yellow", "Avoid": "red"
  },
  DefensiveLabel: {
    "Pass": "green", "Borderline": "yellow", "Fail": "red"
  },
  Show: {
    "true": "green"  // JSON boolean, compare as string in display; filter as bool
  }
};

const COLOR_STYLES = {
  green:  { bg: "#a3be8c", text: "#2e3440" },
  yellow: { bg: "#ebcb8b", text: "#2e3440" },
  red:    { bg: "#bf616a", text: "#eceff4" }
};

function makeSignalFormatter(field) {
  return function(cell) {
    const val = cell.getValue();
    if (val === null || val === undefined) return "—";
    const colorKey = (SIGNAL_COLORS[field] || {})[val];
    if (colorKey) {
      const el = cell.getElement();
      el.style.backgroundColor = COLOR_STYLES[colorKey].bg;
      el.style.color = COLOR_STYLES[colorKey].text;
      el.style.fontWeight = "600";
    }
    return val;
  };
}
```

### 4b. Null/NaN Display as Em Dash (FE-06)

Python `float('nan')` is serialized to JSON `null` (the json module converts NaN to null by default). [VERIFIED: py inspection of results.json — Error column is null for normal rows]

```javascript
function numericFormatter(cell, formatterParams) {
  const val = cell.getValue();
  if (val === null || val === undefined || (typeof val === "number" && isNaN(val))) {
    return "—";  // em dash
  }
  const decimals = formatterParams.decimals !== undefined ? formatterParams.decimals : 2;
  return typeof val === "number" ? val.toFixed(decimals) : val;
}
```

---

## 5. Scroll-to-Row and Row Highlight (FE-17 — REMOVED, but pattern documented)

FE-17 was removed (D-04). Pattern documented here in case ticker search needs scroll behavior.

```javascript
// Source: Tabulator scrollToRow docs — confirmed via WebSearch
table.scrollToRow(rowIdentifier, "center", false)
  .then(function() {
    table.selectRow(rowIdentifier);
  });
```

`scrollToRow` accepts a row index, row data object, or RowComponent. It returns a Promise. `selectRow` highlights the row. Row deselect: `table.deselectRow()`. [CITED: tabulator.info/docs/6.4/navigation via WebSearch]

---

## 6. Column Preset Toggle (FE-13)

```javascript
const SUMMARY_COLUMNS = [
  "Ticker", "Price", "CombinedScore",
  "Lynch_Lynch_Status", "Lynch_Lynch_Score", "Lynch_Lynch_BuyPrice",
  "Lynch_PEG_Status", "Lynch_PEGY_Status",
  "Graham_Graham_Status", "Graham_Graham_Discount_Pct", "Graham_Graham_FV",
  "DefensiveScore", "DefensiveLabel"
];

// All 43 column field names — derive from JSON data on load
let ALL_COLUMNS = [];  // populated after fetch

function applyPreset(preset) {
  ALL_COLUMNS.forEach(field => {
    if (preset === "summary") {
      SUMMARY_COLUMNS.includes(field)
        ? table.showColumn(field)
        : table.hideColumn(field);
    } else {
      table.showColumn(field);
    }
  });
}
```

**API verified:** `table.showColumn(fieldName)`, `table.hideColumn(fieldName)` — both accept field name string. [CITED: tabulator.info/docs/6.2/columns via WebSearch]

---

## 7. Nord CSS and Tabulator Midnight Theme Overrides

### 7a. Tabulator Midnight Theme Color Map

The midnight theme uses direct hex values (no CSS custom properties). [VERIFIED: fetched `tabulator_midnight.css` from jsDelivr] Key values to override:

| Selector | Midnight Value | Nord Override |
|----------|----------------|---------------|
| `.tabulator` background | `#222` | `#3b4252` (nord1 — table surface) |
| `.tabulator-header` background | `#333` | `#2e3440` (nord0 — header darker) |
| `.tabulator-row` (odd) | `#666` border | `#3b4252` (nord1) |
| `.tabulator-row:nth-child(even)` | `#444` | `#434c5e` (nord2) |
| `.tabulator-row:hover` | `#999` | `#4c566a` (nord3) |
| `.tabulator-cell` border-right | `#888` | `#4c566a` (nord3) |
| `.tabulator-header-filter input` | grey | `#2e3440` bg, `#eceff4` text |

### 7b. Recommended CSS Override Block (place in `docs/style.css`, after CDN link)

```css
/* ── Page layout ── */
body {
  background: #2e3440;
  color: #eceff4;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 0;
}

/* ── Tabulator Nord overrides ── */
.tabulator {
  background: #3b4252;
  border-color: #4c566a;
}

.tabulator .tabulator-header {
  background: #2e3440;
  border-bottom-color: #4c566a;
}

.tabulator .tabulator-header .tabulator-col {
  background: #2e3440;
  border-right-color: #4c566a;
  color: #eceff4;
}

.tabulator .tabulator-header .tabulator-col-title {
  color: #eceff4;
}

.tabulator .tabulator-tableholder .tabulator-table {
  background: #3b4252;
}

.tabulator .tabulator-row {
  background: #3b4252;
  border-bottom: 1px solid #4c566a;
  color: #eceff4;
}

.tabulator .tabulator-row:nth-child(even) {
  background: #434c5e;
}

.tabulator .tabulator-row:hover {
  background: #4c566a;
}

.tabulator .tabulator-cell {
  border-right-color: #4c566a;
  color: #eceff4;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.82rem;
}

/* Frozen column border */
.tabulator .tabulator-row .tabulator-frozen.tabulator-frozen-left {
  border-right: 2px solid #88c0d0;  /* frost accent */
}

/* Header filter inputs */
.tabulator .tabulator-header .tabulator-col .tabulator-header-filter input,
.tabulator .tabulator-header .tabulator-col .tabulator-header-filter select {
  background: #2e3440;
  color: #d8dee9;
  border: 1px solid #4c566a;
  border-radius: 3px;
  padding: 2px 4px;
}

/* Sort arrows */
.tabulator .tabulator-header .tabulator-col.tabulator-sortable .tabulator-col-title {
  padding-right: 16px;
}

/* Scrollbar styling */
.tabulator .tabulator-tableholder::-webkit-scrollbar { height: 6px; width: 6px; }
.tabulator .tabulator-tableholder::-webkit-scrollbar-track { background: #2e3440; }
.tabulator .tabulator-tableholder::-webkit-scrollbar-thumb { background: #4c566a; border-radius: 3px; }
```

### 7c. Nord Color Reference (from nordtheme.com — VERIFIED)

| Variable | Hex | Role in this project |
|----------|-----|----------------------|
| nord0 | `#2e3440` | Page background, header bg, dark text on green/yellow cells |
| nord1 | `#3b4252` | Table surface, odd rows |
| nord2 | `#434c5e` | Alternating even rows |
| nord3 | `#4c566a` | Borders, separators, hover |
| nord4 | `#d8dee9` | Secondary text |
| nord6 | `#eceff4` | Primary text, light text on red cells |
| nord8 | `#88c0d0` | Accent — links, active states, active tab, frozen border |
| nord11 | `#bf616a` | Aurora Red — Avoid/Fail/Rich background |
| nord13 | `#ebcb8b` | Aurora Yellow — Hold/Watch/Reasonable/Borderline background |
| nord14 | `#a3be8c` | Aurora Green — Buy/Strong Buy/Deep Buy/Pass/Cheap background |

---

## 8. JetBrains Mono from Google Fonts

[CITED: fonts.google.com/specimen/JetBrains+Mono — standard Google Fonts embed format]

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

CSS usage:
```css
font-family: "JetBrains Mono", monospace;
```

Apply only to data cells (`.tabulator-cell`) and numeric values — not to headings, buttons, or nav (D-10). [ASSUMED — format is standard Google Fonts embed; exact weight availability assumed from context file D-10 reference]

---

## 9. Static Multi-Page GitHub Pages (`docs/`)

### 9a. Shared CSS via Relative Paths

Both `docs/index.html` and `docs/methodology.html` live in the same directory. Relative path for shared stylesheet is identical in both:

```html
<link rel="stylesheet" href="style.css">
```

Sibling files in the same directory need no `./` prefix, though `./style.css` is equally valid. [ASSUMED — standard browser relative path resolution; consistent with GitHub Pages behavior for flat `docs/` layout]

### 9b. GitHub Pages Multi-File Gotchas

- `.nojekyll` file must exist in `docs/` root to prevent Jekyll from ignoring `_`-prefixed directories. Already handled by CI-05.
- GitHub Pages serves from `docs/` on `main` branch — no additional config needed for multi-file sites.
- Relative paths work correctly when files are siblings in `docs/` (same directory level). No `<base>` tag or `baseurl` needed for this flat structure.
- Inter-page links: `<a href="methodology.html">` from `index.html` is correct. [ASSUMED — standard HTML relative links; GitHub Pages does not rewrite relative URLs]

### 9c. Linking Between Pages

```html
<!-- In index.html -->
<nav>
  <a href="index.html" class="nav-link active" aria-current="page">Dashboard</a>
  <a href="methodology.html" class="nav-link">Methodology</a>
</nav>

<!-- In methodology.html -->
<nav>
  <a href="index.html" class="nav-link">Dashboard</a>
  <a href="methodology.html" class="nav-link active" aria-current="page">Methodology</a>
</nav>
```

Active state is hardcoded per page (no JS detection needed for two-page site).

---

## 10. Vanilla JS Tab Implementation (DOC-01, D-11)

Pattern from W3C WAI ARIA Authoring Practices Guide. [VERIFIED: w3.org/WAI/ARIA/apg/patterns/tabs/]

```html
<div role="tablist" aria-label="Methodology sections" class="tab-list">
  <button role="tab" id="tab-lynch"     aria-selected="true"  aria-controls="panel-lynch"     class="tab-btn active">Lynch Signals</button>
  <button role="tab" id="tab-graham"    aria-selected="false" aria-controls="panel-graham"    class="tab-btn">Graham Signals</button>
  <button role="tab" id="tab-defensive" aria-selected="false" aria-controls="panel-defensive" class="tab-btn">Defensive Checklist</button>
  <button role="tab" id="tab-sources"   aria-selected="false" aria-controls="panel-sources"   class="tab-btn">Data Sources</button>
</div>

<section role="tabpanel" id="panel-lynch"     aria-labelledby="tab-lynch">     <!-- Lynch content --> </section>
<section role="tabpanel" id="panel-graham"    aria-labelledby="tab-graham"    hidden> <!-- Graham content --> </section>
<section role="tabpanel" id="panel-defensive" aria-labelledby="tab-defensive" hidden> <!-- Defensive content --> </section>
<section role="tabpanel" id="panel-sources"   aria-labelledby="tab-sources"   hidden> <!-- Sources content --> </section>
```

```javascript
const tabs = document.querySelectorAll('[role="tab"]');

tabs.forEach((tab, i) => {
  tab.addEventListener("click", () => activateTab(tab));
  tab.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") activateTab(tabs[(i + 1) % tabs.length]);
    if (e.key === "ArrowLeft")  activateTab(tabs[(i - 1 + tabs.length) % tabs.length]);
  });
});

function activateTab(tab) {
  tabs.forEach(t => {
    t.setAttribute("aria-selected", "false");
    t.classList.remove("active");
  });
  tab.setAttribute("aria-selected", "true");
  tab.classList.add("active");
  tab.focus();

  document.querySelectorAll('[role="tabpanel"]').forEach(p => { p.hidden = true; });
  document.getElementById(tab.getAttribute("aria-controls")).hidden = false;
}
```

---

## 11. Data Shape and Column Classification

**Confirmed from live `results.json` inspection.** [VERIFIED: py inspection of results.json, 2026-05-30]

| Column | Type | Filter Type | Signal? |
|--------|------|-------------|---------|
| Ticker | str | text (like) | — |
| Price | float | numeric (>=) | — |
| EPS_TTM | float | numeric (>=) | — |
| EPS_Annual | str (JSON array as string) | none | — |
| DivYield_Pct | float | numeric (>=) | — |
| Growth_g_Pct | float | numeric (>=) | — |
| AAA_Yield | float | numeric (>=) | — |
| MarketCap_B | float | numeric (>=) | — |
| PB_Ratio | float | numeric (>=) | — |
| Lynch_PE | float | numeric (>=) | — |
| Lynch_PEG | float | numeric (>=) | — |
| Lynch_PEGY | float | numeric (>=) | — |
| Lynch_Lynch_Score | float | numeric (>=) | — |
| Lynch_FV_PEG | float | numeric (>=) | — |
| Lynch_FV_PEG_Con | float | numeric (>=) | — |
| Lynch_FV_GplusD | float | numeric (>=) | — |
| Lynch_Lynch_Category | str | dropdown (list) | — |
| Lynch_Lynch_BuyPrice | float | numeric (>=) | — |
| Lynch_PEG_Status | str | dropdown (list) | YES |
| Lynch_PEGY_Status | str | dropdown (list) | YES |
| Lynch_LV_Ratio | float | numeric (>=) | — |
| Lynch_Lynch_Status | str | dropdown (list) | YES |
| Lynch_Lynch_PEG_Band | str | dropdown (list) | YES |
| Lynch_Lynch_Discount_Pct | float | numeric (>=) | — |
| Graham_Graham_VA | float | numeric (>=) | — |
| Graham_Graham_VB | float | numeric (>=) | — |
| Graham_Graham_FV | float | numeric (>=) | — |
| Graham_Graham_Status | str | dropdown (list) | YES |
| Graham_Graham_Discount_Pct | float | numeric (>=) | — |
| DefensiveScore | float | numeric (>=) | — |
| DefensiveLabel | str | dropdown (list) | YES |
| Size_OK | float (0/1) | none | — |
| CurrRatio_OK | float (0/1) | none | — |
| DebtEq_OK | float (0/1) | none | — |
| EPS_Stability | float (0/1) | none | — |
| Div_Record | float (0/1) | none | — |
| EPS_Growth10Y | float (0/1) | none | — |
| PE_Limit | float (0/1) | none | — |
| PB_Limit | float (0/1) | none | — |
| CombinedScore | float | numeric (>=) | — |
| Show | bool | programmatic only (FE-11) | — |
| Indexes | str | dropdown (list) | — |
| Error | null/float | programmatic only (FE-07) | — |

**Total: 43 columns, 516 rows, top-level `generated_at` field.**

---

## 12. Table Initialization Blueprint

```javascript
// Source: Patterns assembled from verified Tabulator 6.4.0 API
fetch("data/results.json?v=" + Date.now())
  .then(r => r.json())
  .then(data => {
    updateFreshnessBadge(data.generated_at);

    var table = new Tabulator("#data-table", {
      data: data.rows,
      layout: "fitData",
      height: "calc(100vh - 140px)",  // sticky header via container height
      renderVertical: "virtual",       // default; explicit for clarity
      initialSort: [{ column: "CombinedScore", dir: "desc" }],
      selectable: 1,                   // for ticker search highlight
      columns: buildColumnDefs(),      // see column classification table
    });

    // Default filters on load
    table.setFilter(noErrorFilter);    // hide error rows (FE-07)

    // Wire up controls (FE-11, FE-13, FE-14)
    setupControls(table);

    // Default preset (FE-13)
    applyPreset(table, "summary");
  });
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Data table rendering | Custom `<table>` with sort/filter | Tabulator 6.4.0 | Virtual DOM, header filters, frozen columns, sort — all built in |
| Dropdown header filters | `<select>` injected into headers | `headerFilter: "list"` with `valuesLookup: true` | Tabulator auto-populates from data |
| Column show/hide | CSS classes or display:none on cells | `table.showColumn()` / `table.hideColumn()` | Tabulator manages internal state and re-renders |
| Horizontal scroll with sticky header | Custom JS scroll syncing | Tabulator's default — set `height` on container | Tabulator handles header/body scroll sync |
| Tab panels | Third-party library | 30-line vanilla JS pattern (Section 10) | No runtime dependency needed |

---

## Package Legitimacy Audit

> This phase uses CDN delivery, not `pip install` or `npm install`. The package `tabulator-tables` is loaded via jsDelivr CDN and is never installed as a project dependency. Standard slopcheck (PyPI/npm install flow) does not apply.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| tabulator-tables@6.4.0 | npm (CDN delivery via jsDelivr) | ~10 yrs (2014) | Millions/mo | github.com/tabulator-tables/tabulator | N/A — CDN only | Approved |

**Note:** `tabulator-tables` was verified via `npm view tabulator-tables version` → `6.4.0` (current, published 2026-05-18). The CDN file was fetched and confirmed to self-report `Tabulator v6.4.0 (c) Oliver Folkerd 2026`. [VERIFIED: npm registry + jsDelivr CDN]

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Common Pitfalls

### Pitfall 1: `frozen: true` + `layout: "fitDataFill"` = spurious horizontal scrollbar
**What goes wrong:** An extra horizontal scrollbar appears even when the table fits the viewport.
**Why it happens:** Tabulator adds the frozen column's width to the inner table width calculation without accounting for the fill behavior.
**How to avoid:** Use `layout: "fitData"` (not `fitDataFill`) when any column has `frozen: true`. Set a fixed container height instead of relying on fill behavior. [VERIFIED: GitHub tabulator-tables issue #2908]
**Warning signs:** Scrollbar appears immediately on load before any user interaction.

### Pitfall 2: `renderHorizontal: "virtual"` header de-sync with 40+ columns
**What goes wrong:** After horizontal scrolling, column headers and cell data misalign.
**Why it happens:** The horizontal virtual DOM is experimental and has known issues at large column counts.
**How to avoid:** Do not set `renderHorizontal: "virtual"`. Default `"basic"` works fine for 43 columns. [VERIFIED: GitHub tabulator-tables issues #3551, #3741]
**Warning signs:** Headers appear shifted relative to cell content after scrolling.

### Pitfall 3: `removeFilter` requires same function reference
**What goes wrong:** `table.removeFilter(noErrorFilter)` silently fails if `noErrorFilter` is defined inline each time.
**Why it happens:** JS function equality requires reference equality; a new function object never equals a stored one.
**How to avoid:** Define filter functions once at module scope and reference the same variable for both `setFilter` and `removeFilter`. [ASSUMED — standard JS; consistent with Tabulator filter API documentation]
**Warning signs:** Toggling "show errors" appears to do nothing.

### Pitfall 4: `Show` column is a JSON boolean, not a string
**What goes wrong:** Filtering `table.setFilter("Show", "=", "True")` matches nothing.
**Why it happens:** Python's `json.dumps` outputs `true`/`false` (lowercase) which JSON.parse returns as JS booleans, not strings.
**How to avoid:** Filter with `table.setFilter("Show", "=", true)` (JS boolean). [VERIFIED: py inspection — `Show: bool = True` in first row]
**Warning signs:** Buy Signals toggle appears active but shows all rows.

### Pitfall 5: `Error` column is `null` in JSON, not `NaN`
**What goes wrong:** Checking `data.Error === NaN` always returns false (NaN !== NaN in JS).
**Why it happens:** Python's json module serializes `float('nan')` as `null` per JSON spec. [VERIFIED: py inspection — `Error: float = nan` but arrives as `null` in JSON]
**How to avoid:** Check `data.Error === null || data.Error === undefined` in the filter function.
**Warning signs:** Error row filter appears to work but lets error rows through.

### Pitfall 6: `EPS_Annual` column is a string, not an array
**What goes wrong:** Attempting numeric formatting or sorting on `EPS_Annual` produces errors.
**Why it happens:** Python outputs the list as a JSON string like `"[24.96, 44.32, ...]"`, not a JSON array.
**How to avoid:** Treat `EPS_Annual` as a string column; skip numeric formatter; omit from Summary preset (already excluded per D-01). [VERIFIED: py inspection — `EPS_Annual: str = '[24.96, 44.32, 81.24, 70.0]'`]
**Warning signs:** Sort on `EPS_Annual` sorts lexicographically rather than numerically.

### Pitfall 7: `*.json` in `.gitignore` blocks `results.json`
**What goes wrong:** The CI step commits `docs/data/results.json`, but it is silently ignored.
**Why it happens:** `.gitignore` has a blanket `*.json` rule; requires `!docs/data/results.json` exception.
**How to avoid:** Already addressed by CI-06 in Phase 1/2. Verify this exception exists before Phase 3 testing.
**Warning signs:** `git status` shows `results.json` as untracked after CI run.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `removeFilter(fn)` requires same function reference | Section 3d | Error row toggle silently broken; fix: store filter fn at module scope |
| A2 | Shared `./style.css` relative path works from both `index.html` and `methodology.html` | Section 9a | CSS not loaded on methodology page; fix: verify in browser before marking done |
| A3 | Inter-page links like `methodology.html` work without full path on GitHub Pages | Section 9b | 404 on nav links; fix: test with Pages URL, not just local file system |
| A4 | JetBrains Mono weights 400 and 500 are available on Google Fonts | Section 8 | Font load fails; fallback to system monospace is acceptable |
| A5 | `headerFilter: "list"` with `valuesLookup: true` is available in Tabulator 6.4.0 | Section 3a | Dropdown filter fails; fix: use `headerFilter: "select"` with `headerFilterParams: {values: [...]}` as fallback |

---

## Open Questions

1. **`headerFilter: "list"` availability in 6.4.0**
   - What we know: Documented in 6.4 filter docs (cited via WebSearch); uses `valuesLookup: true` to auto-populate from data.
   - What's unclear: Whether the "list" editor type is bundled in the standard CDN build or requires a separate module.
   - Recommendation: Test on page load; if the filter doesn't render, fall back to `headerFilter: "select"` with an explicit `values` array built by scanning `data.rows`.

2. **Multiple simultaneous programmatic filters (error hide + buy signal)**
   - What we know: Tabulator has `addFilter` for stacking; `setFilter` replaces all programmatic filters.
   - What's unclear: Interaction between function-type filters and field-type filters in an array.
   - Recommendation: Use `addFilter`/`removeFilter` rather than `setFilter` to avoid stomping; test both toggles independently and together.

---

## Environment Availability

> Step 2.6: No external tools or CLI utilities required for Phase 3. All assets are CDN-loaded. The only runtime is a browser. No local build step, no npm install, no Python runtime needed at execution time.

---

## Validation Architecture

> `workflow.nyquist_validation` not found in `.planning/config.json` — treated as enabled.

### Test Framework

Phase 3 is a pure frontend (static HTML/JS/CSS) with no existing test infrastructure. Automated testing of the Tabulator integration is manual-only for v1.

| Property | Value |
|----------|-------|
| Framework | None — manual browser verification |
| Config file | None |
| Quick run command | Open `docs/index.html` via GitHub Pages URL |
| Full suite command | Manual checklist against all FE-xx requirements |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FE-01 | Tabulator loads from CDN | smoke | Open page, check no console errors | — |
| FE-02 | Table shows all columns, sorted CombinedScore desc | manual | Visual inspection | — |
| FE-03 | Ticker stays visible on horizontal scroll | manual | Scroll right in browser | — |
| FE-04 | Header stays visible on vertical scroll | manual | Scroll down in browser | — |
| FE-05 | Signal cells have correct color per value | manual | Compare colors to Nord Aurora hex | — |
| FE-06 | Null values show as em dash | manual | Check cells with null data | — |
| FE-07 | Error rows hidden; toggle shows them | manual | Toggle button; check row count | — |
| FE-08 | Freshness badge shows correct date | manual | Compare to `generated_at` in JSON | — |
| FE-09 | Stale banner shows if data > 3 days old | manual | Set system clock or mock date | — |
| FE-10 | Cache-bust param on fetch | smoke | Check Network tab in DevTools | — |
| FE-11 | Buy Signals toggle filters correctly | manual | Toggle; verify only Show=true rows remain | — |
| FE-12 | Per-column header filters work | manual | Try each filter type | — |
| FE-13 | Summary/Full preset toggles columns | manual | Toggle; verify 13 vs 43 columns | — |
| FE-14 | Ticker search filters instantly | manual | Type "APP" and verify | — |
| DOC-01 | methodology.html renders all tab content | manual | Click each tab | — |
| DOC-02 | Nav links correct on both pages | manual | Navigate between pages | — |

### Wave 0 Gaps

- [ ] No automated tests exist — all verification is manual browser testing
- [ ] A local HTTP server is needed for fetch to work (file:// URLs block fetch) — use `py -m http.server` in the `docs/` directory or push to Pages branch

---

## Security Domain

> `security_enforcement` not found in config — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in this phase |
| V3 Session Management | No | No sessions — fully static |
| V4 Access Control | No | Public read-only data |
| V5 Input Validation | Yes (partial) | Ticker search input — sanitized by Tabulator's "like" filter (no eval, no innerHTML injection) |
| V6 Cryptography | No | No crypto in static frontend |

### Known Threat Patterns for Static JS/CDN Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CDN supply chain compromise | Tampering | Pin to exact version `@6.4.0` — do not use `@latest` or unpinned URLs |
| XSS via cell formatter | Tampering | Use `cell.getValue()` return in formatters — never `innerHTML` with raw data |
| JSON injection | Tampering | N/A — fetch is read-only; JSON.parse is safe |
| Subresource integrity (SRI) | Tampering | Optional enhancement: add `integrity=` attribute to CDN link/script tags for SRI verification |

**SRI note (optional):** jsDelivr provides SRI hashes. Adding `integrity="sha512-..."` + `crossorigin="anonymous"` to the CDN tags prevents CDN-served file tampering. Not required for v1 but noted for security-conscious deployment.

---

## Sources

### Primary (HIGH confidence)
- npm registry — `npm view tabulator-tables version` → 6.4.0, published 2026-05-18
- jsDelivr CDN — fetched `tabulator.min.js` (self-reports v6.4.0) and `tabulator_midnight.css` (color values extracted)
- jsDelivr CDN directory listing — confirmed `tabulator_midnight.min.css` exists in `dist/css/`
- `docs/data/results.json` — inspected first row via Python; all 43 column names and types confirmed
- nordtheme.com/docs/colors-and-palettes — all Nord hex values confirmed
- w3.org/WAI/ARIA/apg/patterns/tabs/ — accessible tab pattern HTML/JS confirmed

### Secondary (MEDIUM confidence)
- WebSearch cross-referenced with GitHub tabulator-tables source — `initialSort`, `layout`, `renderHorizontal` options
- GitHub tabulator-tables issues #2908, #3551, #3741 — frozen+fitDataFill bug, renderHorizontal de-sync issues
- GitHub tabulator-tables issues #3041, #1382 — `headerFilter: "list"` with `valuesLookup` and `headerFilterParams`
- tabulator.info/docs/6.4 (403 on direct fetch; referenced via WebSearch snippets) — setFilter/removeFilter API, scrollToRow, showColumn/hideColumn

### Tertiary (LOW confidence)
- None used as authoritative

---

## Metadata

**Confidence breakdown:**
- Standard stack (CDN URLs, version): HIGH — live CDN and npm registry verified
- Column structure (field names, types): HIGH — live JSON file inspected
- Tabulator API (filters, formatters, column ops): MEDIUM — cross-verified via GitHub source and WebSearch; direct docs blocked (403)
- Tabulator pitfalls (frozen+fitDataFill, renderHorizontal): HIGH — GitHub issues verified
- Nord colors: HIGH — official nordtheme.com verified
- Tab pattern: HIGH — W3C WAI APG verified
- CSS override selectors for midnight theme: MEDIUM — extracted from live CDN CSS file; selectors may shift in future patch versions

**Research date:** 2026-05-30
**Valid until:** 2026-08-30 (stable library; CDN URLs pinned to 6.4.0)
