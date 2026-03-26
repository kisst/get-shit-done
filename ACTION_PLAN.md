# ACTION PLAN: Sync Fork with Upstream + Python Feature Parity

**Date:** 2026-03-26
**Branch:** sync-upstream-v1.29
**Related Work:** [PURGE-NODE-TRACES]WORK_SUMMARY[2026-03-02].md

## Objective

Merge upstream changes (v1.22.0 → v1.29.0) into the Python-only fork, port all new upstream functionality to Python, and ensure comprehensive test coverage.

## Current State

- **Fork (origin/main):** v1.22.0 + 4 commits (Python port, 5,463 LOC, 12 modules, 68 commands, 51 tests)
- **Upstream (upstream/main):** v1.29.0 (~100 commits ahead, +6,715 lines in Node.js tooling, +20,473 lines in tests)
- **Divergence:** Fork deleted all `.cjs` files; upstream heavily modified them. Direct merge is not feasible.

## Strategy: Option A — Cherry-pick non-code + port new features

---

## STAGE 1: Merge Non-Code Upstream Changes ✅

- [x] **1.1** Create branch `sync-upstream-v1.29` from current `main`
- [x] **1.2** Cherry-pick/merge upstream changes — 217 files, +40,329/-910 lines
- [x] **1.3** Update `get-shit-done/templates/config.json` to match upstream schema
- [x] **1.4** Verified no Node.js tooling pulled in, no merge conflicts

**WORK SUMMARY:** Checked out all non-code paths from upstream/main: agents (7 new + updates), commands (26 new), workflows (24 new + updates), templates (6 new), references, docs (4 languages), CI/config, JS hooks (as reference).

---

## STAGE 2: Port New Upstream Node.js Functionality to Python ✅

### 2A: New Module — `security.py` ✅
- [x] `validate_path()` — path traversal prevention with symlink resolution
- [x] `require_safe_path()` — convenience wrapper raising ValueError
- [x] `scan_for_injection()` — 18 injection patterns + strict mode
- [x] `sanitize_for_prompt()` — strip zero-width chars, neutralize XML tags
- [x] `sanitize_for_display()` — filter protocol leak markers
- [x] `validate_shell_arg()` — null byte / command substitution detection
- [x] `safe_json_parse()` — size-limited JSON parsing
- [x] `validate_phase_number()` — standard + custom ID validation
- [x] `validate_field_name()` — regex injection prevention

### 2B: New Module — `workstream.py` ✅
- [x] `migrate_to_workstreams()` — flat-to-workstream migration with rollback
- [x] `cmd_workstream_create()` — create with auto-migration
- [x] `cmd_workstream_list()` — list with completion stats
- [x] `cmd_workstream_status()` — detailed single workstream status
- [x] `cmd_workstream_complete()` — archive with collision handling
- [x] `cmd_workstream_set()` / `cmd_workstream_get()` — active workstream management
- [x] `cmd_workstream_progress()` — progress summary across all workstreams
- [x] `get_other_active_workstreams()` — exclude archived

### 2C: New Module — `uat.py` ✅
- [x] `cmd_audit_uat()` — cross-phase UAT/VERIFICATION scanner
- [x] `cmd_render_checkpoint()` — UAT checkpoint rendering with path safety
- [x] `parse_uat_items()` — markdown item parser with categorization
- [x] `parse_verification_items()` — human_needed / gaps_found parsing
- [x] `parse_current_test()` — current test extraction
- [x] `build_checkpoint()` — ASCII checkpoint formatting
- [x] `categorize_item()` — blocker type classification

### 2D: New Module — `model_profiles.py` ✅
- [x] `get_agent_to_model_map_for_profile()` — per-agent model tier mapping
- [x] `format_agent_to_model_map_as_table()` — ASCII table formatting
- [x] Extended profiles for new agents (nyquist-auditor, ui-*)

### 2E: New Module — `profile_pipeline.py` ✅
- [x] `cmd_scan_sessions()` — Claude session history scanning
- [x] `cmd_extract_messages()` — user message extraction with filtering
- [x] `cmd_profile_sample()` — multi-project sampling with recency weighting
- [x] Context dump filtering, continuation detection

### 2F: New Module — `profile_output.py` ✅
- [x] `cmd_write_profile()` — profile data output with redaction
- [x] `cmd_profile_questionnaire()` — 8-dimension profiling questionnaire
- [x] `cmd_generate_dev_preferences()` — developer preferences artifact
- [x] `cmd_generate_claude_profile()` — CLAUDE.md profile section
- [x] `cmd_generate_claude_md()` — full CLAUDE.md management with GSD markers
- [x] Section management (extract, build, update, detect manual edits)

### 2G: Updates to Existing Modules ✅
- [x] `core.py` — Added: planning_root, planning_dir, planning_paths, strip_shipped_milestones, extract_current_milestone, get_milestone_phase_filter, read_subdirectories, detect_sub_repos, find_project_root, extract_one_liner_from_body, get_agents_dir, check_agents_installed
- [x] `state.py` — Added: state_extract_field (public), cmd_state_begin_phase, cmd_signal_waiting, cmd_signal_resume, _update_current_position_fields
- [x] `commands.py` — Added: cmd_todo_match_phase, cmd_stats, cmd_commit_to_subrepo
- [x] `phase.py` — Added: `--id` parameter support for custom phase IDs
- [x] `config.py` — Added: _load_raw_config helper
- [x] `verify.py` — Added: cmd_validate_agents

### 2H: Update `gsd-tools.py` Dispatcher ✅
- [x] Added routing for: state begin-phase/signal-waiting/signal-resume, commit-to-subrepo, todo match-phase, stats, audit-uat, uat render-checkpoint, workstream CRUD, scan-sessions, extract-messages, profile-sample, write-profile, profile-questionnaire, generate-dev-preferences, generate-claude-profile, generate-claude-md, agent-skills, validate agents, phase add --id

---

## STAGE 3: Port Python Hooks ✅
- [x] `gsd-prompt-guard.py` — prompt injection detection (advisory)
- [x] `gsd-workflow-guard.py` — workflow enforcement (advisory)

---

## STAGE 4: Comprehensive Test Suite ✅

### 4A: Fix Existing Tests ✅
- [x] Added conftest.py fixing import path issue — tests now run from project root

### 4B: Tests for New Modules ✅
- [x] `test_security.py` — 28 tests: path validation, injection detection, sanitization, JSON parsing, phase/field validation
- [x] `test_workstream.py` — 10 tests: CRUD, migration, active workstream tracking, archived filtering
- [x] `test_uat.py` — 16 tests: categorization, UAT parsing, verification parsing, checkpoint building
- [x] `test_model_profiles.py` — 7 tests: profile resolution, table formatting, extended agents
- [x] `test_profile.py` — 18 tests: format_bytes, message filtering, truncation, section management, dimensions

### 4C: Tests for Updated Modules ✅
- [x] `test_state_new.py` — 7 tests: state_extract_field (bold/plain/case), signal-waiting, signal-resume, begin-phase
- [x] `test_commands_new.py` — 3 tests: todo-match-phase, stats, commit-to-subrepo
- [x] `test_core_new.py` — 14 tests: planning paths, milestone filter, subdirectories, sub repos, project root, one-liner

---

## STAGE 5: Verification ✅

- [x] **5.1** Full test suite: **184 tests passed, 0 failures** (up from 51)
- [x] **5.2** `make test` passes
- [x] **5.3** `make check` (smoke tests) passes
- [x] **5.4** All module imports verified
- [x] **5.5** No Node.js tooling files accidentally pulled in

### Test Results

```
184 passed in 2.14s
```

### Files Added/Modified

**New Python Modules (6):**
- `get-shit-done/bin/lib_py/security.py` — Input validation and injection guards
- `get-shit-done/bin/lib_py/workstream.py` — Workstream CRUD and namespacing
- `get-shit-done/bin/lib_py/uat.py` — UAT/verification audit scanning
- `get-shit-done/bin/lib_py/model_profiles.py` — Agent model tier mapping
- `get-shit-done/bin/lib_py/profile_pipeline.py` — Session scanning and sampling
- `get-shit-done/bin/lib_py/profile_output.py` — Profile rendering and CLAUDE.md management

**New Python Hooks (2):**
- `hooks/gsd-prompt-guard.py` — Prompt injection detection
- `hooks/gsd-workflow-guard.py` — Workflow enforcement

**New Test Files (8):**
- `tests/python/conftest.py` — Import path fix
- `tests/python/test_security.py`
- `tests/python/test_workstream.py`
- `tests/python/test_uat.py`
- `tests/python/test_model_profiles.py`
- `tests/python/test_state_new.py`
- `tests/python/test_commands_new.py`
- `tests/python/test_core_new.py`
- `tests/python/test_profile.py`

**Updated Existing Modules (7):**
- `get-shit-done/bin/gsd-tools.py` — 18 new command routes
- `get-shit-done/bin/lib_py/core.py` — 13 new functions
- `get-shit-done/bin/lib_py/state.py` — 4 new functions + public state_extract_field
- `get-shit-done/bin/lib_py/commands.py` — 3 new functions
- `get-shit-done/bin/lib_py/phase.py` — custom ID support
- `get-shit-done/bin/lib_py/config.py` — _load_raw_config helper
- `get-shit-done/bin/lib_py/verify.py` — cmd_validate_agents

**Upstream Non-Code Files (217):**
- agents/, commands/, workflows/, templates/, references/, docs/, CI, READMEs
