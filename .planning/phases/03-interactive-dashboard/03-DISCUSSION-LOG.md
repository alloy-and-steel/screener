# Phase 3: Interactive Dashboard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 3-Interactive Dashboard
**Areas discussed:** Summary column preset, Top 20 panel (removed), Visual style, Methodology page format

---

## Summary Column Preset

### Gray area selection

| Option | Selected |
|--------|----------|
| Summary column preset | ✓ |
| Top 20 panel content | ✓ |
| Visual style | ✓ |
| Methodology page format | ✓ |

**Notes:** User noted the summary preset might not be 10 columns and wanted to see all columns listed before deciding. Also stated upfront that the Top 20 panel is not wanted.

---

## Summary Column Preset — Column Selection

All 43 columns from `results.json` were presented grouped by category. User selected:

**Chosen (13 columns):** Ticker, Price, CombinedScore, Lynch_Lynch_Status, Lynch_Lynch_Score, Lynch_Lynch_BuyPrice, Lynch_PEG_Status, Lynch_PEGY_Status, Graham_Graham_Status, Graham_Graham_Discount_Pct, Graham_Graham_FV, DefensiveScore, DefensiveLabel

---

## Top 20 Panel

| Option | Description | Selected |
|--------|-------------|----------|
| Implement FE-15/16/17 | Collapsible Top 20 panel above main table | |
| Remove from scope | Strike FE-15, FE-16, FE-17 entirely | ✓ |

**User's choice:** Remove — stated explicitly before area discussion began.

---

## Visual Style

### Overall look

| Option | Description | Selected |
|--------|-------------|----------|
| Clean / minimal | White background, system font | |
| Dark mode default | Dark background, light text | ✓ |
| Branded / styled | Custom header, color accent, custom font | |

**User's choice:** Dark mode default

---

### Page header

| Option | Description | Selected |
|--------|-------------|----------|
| Title + freshness badge only | Minimal header | |
| Title + nav links + freshness badge | Full header with nav | ✓ |
| Nav bar only | Compact single bar | |

**User's choice:** Title + nav links + freshness badge

---

### Dark color palette

| Option | Description | Selected |
|--------|-------------|----------|
| Deep navy | GitHub dark (#0d1117) | |
| Charcoal / neutral dark | Neutral dark (#1c1c1c) | |
| Nord color scheme | Arctic blue palette | ✓ |

**User's choice:** Nord color scheme
**Notes:** User said "I'm a fan of the Nord color scheme. Think we can make something like that work and be intuitive?" — confirmed yes, Nord Aurora maps directly to traffic-light signals.

---

### Traffic-light cell colors

| Option | Description | Selected |
|--------|-------------|----------|
| Adjust for dark | More saturated Nord Aurora colors | ✓ |
| Keep existing values | SIGNAL_COLORS RGB floats as-is | |

**User's choice:** Adjust for dark (Nord Aurora: #a3be8c / #ebcb8b / #bf616a)

---

### Row striping

| Option | Description | Selected |
|--------|-------------|----------|
| Subtle alternating rows | Nord surface variants | |
| Flat rows, hover only | | |
| You decide | Claude's discretion | ✓ |

**User's choice:** You decide

---

### Font

| Option | Description | Selected |
|--------|-------------|----------|
| System font stack | Zero load time | |
| Inter (Google Fonts) | Clean data table font | |
| JetBrains Mono for data, system for labels | Monospace numeric alignment | ✓ |

**User's choice:** JetBrains Mono for data cells, system font for labels/headings

---

## Methodology Page Format

### Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Sections with anchored headings | H2/H3 + anchor links at top | |
| Single scrollable page, no nav | Simple top-to-bottom | |
| Tabbed sections | Lynch / Graham / Defensive / Scoring tabs | ✓ |

**User's choice:** Tabbed sections

---

### Content fidelity

| Option | Description | Selected |
|--------|-------------|----------|
| Full reformat for web | Proper HTML, prose, definition lists, tables | ✓ |
| Light reformat | Verbatim text in ul/pre tags | |
| Port as-is | Single pre block | |

**User's choice:** Full reformat for web (Recommended)

---

## Claude's Discretion

- Row striping style: use subtle alternating Polar Night variants, best judgment on readability
- Tab implementation: vanilla JS, no library needed
- Column header label abbreviations for long JSON names
- Exact column widths and Tabulator layout options

## Deferred Ideas

- Top 20 panel (FE-15/16/17) — not wanted, not deferred
- Dark/light mode toggle — already in v2 backlog
- Column visibility picker — already in v2 backlog
