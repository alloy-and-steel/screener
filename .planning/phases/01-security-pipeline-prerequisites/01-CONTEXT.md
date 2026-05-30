# Phase 1: Security & Pipeline Prerequisites - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the repository safe to publish and establish the correct GitHub Actions CI infrastructure — before any new output code runs. Covers: credential removal, git history audit, workflow file relocation, pipeline permissions/identity/commit guards, and the `.nojekyll` + `.gitignore` prerequisites needed by later phases.

</domain>

<decisions>
## Implementation Decisions

### Git History Remediation (SEC-02)
- **D-01:** Phase 1 runs a git history audit using `git log -S <key_string>` to confirm whether the Finnhub API key is present in any commit.
- **D-02:** Both branches are planned so the executor can follow the matching path autonomously:
  - **Key found:** Run `git filter-repo` to scrub the key string from all commits, force-push rewritten history. Surface as a manual step: go to finnhub.io, regenerate the API key, update the `FINNHUB_API_KEY` GitHub Actions secret.
  - **Key not found:** No history action required; proceed to SEC-01 fix only.
- **D-03:** SEC-01 fix: replace `FINNHUB_API_KEY = "REMOVED_API_KEY"` in `diagnose_finnhub.py:16` with `os.environ["FINNHUB_API_KEY"]` — no fallback, no error handling beyond the environment lookup.

### Actions Workflow (CI-01 – CI-06)
- **D-04:** `screener.yml` moves from the repo root to `.github/workflows/screener.yml` in Phase 1. The file is currently invisible to GitHub Actions at its present location.
- **D-05:** Phase 1 adds the full commit/push steps (CI-01 through CI-04) — not just permissions and identity. Phase 2 only needs to add the Python JSON writer; the workflow infrastructure is complete after Phase 1.
- **D-06:** Conditional commit uses a shell conditional pattern (CI-04): `if ! git diff --quiet docs/data/results.json; then git commit -m "..." && git push; fi`. Compact, self-contained, no step outputs or IDs needed.

### docs/ Directory (CI-05, CI-06)
- **D-07:** Phase 1 creates `docs/.nojekyll` only. No placeholder `index.html`. All other `docs/` content defers to Phase 2 (`docs/data/`) and Phase 3 (`docs/index.html`, `docs/methodology.html`).
- **D-08:** `.gitignore` receives `!docs/data/results.json` exception (after the existing `!.planning/*.json` line). Order matters — the exception must follow the `*.json` glob.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — Phase 1 requirements: SEC-01, SEC-02, CI-01, CI-02, CI-03, CI-04, CI-05, CI-06 (with exact acceptance criteria)
- `.planning/ROADMAP.md` — Phase 1 goal and success criteria (5 items)

### Files Being Modified
- `diagnose_finnhub.py` — contains hardcoded key at line 16; SEC-01 target
- `screener.yml` — workflow file being modified and relocated to `.github/workflows/`
- `.gitignore` — receives `!docs/data/results.json` exception for CI-06

### Codebase Analysis
- `.planning/codebase/CONCERNS.md` — CRITICAL severity item: hardcoded API key; confirms `.py` files are tracked and not gitignored

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `screener.yml` existing env block already has `FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}` — the secret reference is already wired; only the code-side fix is needed for SEC-01.

### Established Patterns
- `.gitignore` currently uses `!.planning/*.json` as a glob exception pattern — `!docs/data/results.json` follows the same convention.
- `screener.yml` already uses `actions/checkout@v4` and `actions/setup-python@v5` — git operations should use the standard `git config user.name/email` + `git add` + `git commit` + `git push` shell pattern consistent with Actions conventions.

### Integration Points
- `docs/` directory does not exist yet — `docs/.nojekyll` creation will create it.
- `docs/data/results.json` does not exist yet — the `.gitignore` exception and conditional commit guard anticipate Phase 2's output but do not depend on it being present.
- After filter-repo force push, any existing GitHub remote clone would need `git fetch --all` + reset — acceptable since this is a new project with no collaborators yet.

</code_context>

<specifics>
## Specific Ideas

- Conditional commit shell pattern (CI-04): `if ! git diff --quiet docs/data/results.json; then git commit -m "chore: update results.json" && git push; fi`
- `git filter-repo` (if key found): `git filter-repo --string-callback "return data.replace(b'<key>', b'REMOVED')"` or `--path-glob` approach — researcher should confirm the exact flag for string replacement
- Manual key rotation step: "Go to https://finnhub.io → Dashboard → API Keys → Regenerate. Then update the FINNHUB_API_KEY secret in GitHub repository Settings → Secrets and variables → Actions."

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Security & Pipeline Prerequisites*
*Context gathered: 2026-05-29*
