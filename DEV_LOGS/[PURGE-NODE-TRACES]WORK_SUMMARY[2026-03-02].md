# ACTION_PLAN: Purge All Node.js Traces

**Date:** 2026-03-02
**Branch:** main
**Related Work:** Previous refactor to Python tooling (commit 3493ab6)

## Objective

Remove every trace that this project was ever a Node.js project. The Python replacements already exist — this is purely cleanup.

## Stage 1: Delete Node.js Files — COMPLETE

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 1.1 | Delete root package files | `package.json`, `package-lock.json` | DONE |
| 1.2 | Delete Node installer | `bin/install.js` | DONE |
| 1.3 | Delete Node build script | `scripts/build-hooks.js` | DONE |
| 1.4 | Delete JS hooks | `hooks/gsd-check-update.js`, `hooks/gsd-statusline.js`, `hooks/gsd-context-monitor.js` | DONE |
| 1.5 | Delete all CJS tooling | `get-shit-done/bin/gsd-tools.cjs`, `get-shit-done/bin/lib/*.cjs` (11 files) | DONE |
| 1.6 | Delete CJS test files | `tests/*.cjs` (14 files), `scripts/run-tests.cjs` | DONE |
| 1.7 | Delete backup file | `commands/gsd/new-project.md.bak` | DONE |

Empty directories `bin/`, `scripts/`, `get-shit-done/bin/lib/`, `get-shit-done/bin/` removed.

## Stage 2: Clean .gitignore — COMPLETE

- Removed `node_modules/` entry
- Updated `hooks/dist/` comment (removed "committed to npm, not git")
- Kept `coverage/` (still useful for Python coverage)

## Stage 3: Scrub Node References from Markdown Docs — COMPLETE

| # | File | Action | Status |
|---|------|--------|--------|
| 3.1 | `README.md` | Removed npm badges, replaced all `npx` instructions with `make install`, removed terminal.svg reference, rewrote install/update/uninstall/troubleshooting sections | DONE |
| 3.2 | `get-shit-done/workflows/update.md` | Replaced `npm view` with `git ls-remote`, replaced `npx` install with `git pull && make install` | DONE |
| 3.3 | `docs/context-monitor.md` | Replaced "npx get-shit-done-cc" with "make install" | DONE |
| 3.4-3.15 | Agent/reference/template docs | PRESERVED — all node/npm refs are about detecting USER project stacks, not GSD infrastructure | N/A |
| 3.16 | `assets/terminal.svg` | Deleted (showed `npx` command + broken font rendering) | DONE |
| 3.17 | `get-shit-done/workflows/help.md` | Replaced `npx` with `git pull && make install` | DONE |
| 3.18 | `.github/workflows/test.yml` | Rewrote from Node CI to Python CI (matrix: py 3.8/3.10/3.12) | DONE |

CHANGELOG.md left as-is — it's a historical record.

## Stage 4: Fix SVG Font Issue — COMPLETE

- `terminal.svg` deleted (broken fonts + showed `npx get-shit-done-cc`)
- Logo SVGs (`gsd-logo-2000.svg`, `gsd-logo-2000-transparent.svg`) preserved — they use block characters with `monospace` fallback that render correctly

## Stage 5: Verify — COMPLETE

### File scan
- `**/*.js` → 0 files
- `**/*.cjs` → 0 files
- `**/package*.json` → 0 files

### GSD-specific npm reference scan
Only remaining `npx`/`npm` mentions are in:
- `CHANGELOG.md` — historical record
- `get-shit-done/templates/codebase/testing.md` — user project examples (`[e.g., "npm test"]`)
- Agent docs — user project stack detection (`package.json`, `npm install`, `node_modules`)

### Tests
- `make check` — PASSED (3/3 checks)
- `python3 -m unittest discover -s tests/python -v` — PASSED (51/51 tests)

### Total files deleted: 33
### Total files modified: 6
