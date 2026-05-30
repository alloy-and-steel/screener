# Phase 1: Security & Pipeline Prerequisites - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 1-Security & Pipeline Prerequisites
**Areas discussed:** Git history remediation, screener.yml move + commit steps scope, docs/ directory extent

---

## Git History Remediation

### Question 1 — History cleanup strategy if key is confirmed

| Option | Description | Selected |
|--------|-------------|----------|
| Rotate key + filter-repo | Rewrite history, force push, rotate Finnhub key | |
| Rotate key only | New key makes committed string useless; leave history | |
| Audit only, decide after | Audit first, surface finding before taking action | ✓ |

**User's choice:** Audit only, decide after

---

### Question 2 — What to prepare as the conditional path

| Option | Description | Selected |
|--------|-------------|----------|
| Pause and surface to you | Stop executor at checkpoint if key found, ask before acting | |
| Plan both paths in the plan | Write if-found and if-not-found branches; executor follows autonomously | ✓ |

**User's choice:** Plan both paths in the plan

---

### Question 3 — What the "key found" branch should do

| Option | Description | Selected |
|--------|-------------|----------|
| Rotate key + rewrite history | git filter-repo scrub + force push + key rotation | ✓ |
| Rotate key only | New key makes committed string dead; no history rewrite | |

**User's choice:** Rotate key + rewrite history (Recommended)

---

### Question 4 — How to handle Finnhub key rotation

| Option | Description | Selected |
|--------|-------------|----------|
| Document as a manual step | Executor surfaces: go to finnhub.io, regenerate, update secret | ✓ |
| Just fix the code, skip rotation | Remove hardcoded string only; don't touch the live key | |

**User's choice:** Document as a manual step (Recommended)

---

## screener.yml move + commit steps scope

### Question 1 — Full commit/push steps now vs prerequisites only

| Option | Description | Selected |
|--------|-------------|----------|
| Full commit/push steps now | Move file, add permissions + identity + git commit/push steps (CI-01–CI-04) | ✓ |
| Prerequisites only | Move file, add permissions + identity; defer commit/push to Phase 2 | |

**User's choice:** Full commit/push steps now (Recommended)

---

### Question 2 — Conditional commit pattern (CI-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Shell conditional | `if ! git diff --quiet ...; then git commit ... && git push; fi` | ✓ |
| Step output pattern | Separate check step sets output; commit steps use `if: steps.X.outputs.changed == 'true'` | |

**User's choice:** Shell conditional (Recommended)

---

## docs/ Directory Extent

### Question 1 — What to create beyond .nojekyll

| Option | Description | Selected |
|--------|-------------|----------|
| Just .nojekyll | Minimum for CI-05; all other docs/ content defers to later phases | ✓ |
| Add a minimal placeholder index.html | "Coming soon" page so Pages URL shows something during Phases 2–3 | |

**User's choice:** Just .nojekyll (Recommended)

---

## Claude's Discretion

None — all areas had clear user selections.

## Deferred Ideas

None — discussion stayed within phase scope.
