---
phase: 05-notifications-integration-and-verification
plan: 05-01
subsystem: runtime-backup-policy
tags: [klipper, persistence, backup-policy, gcode, pytest]

requires:
  - phase: 04-automatic-fallback-workflow
    provides: Ordered loop-safe backup resolution and atomic canonical persistence
provides:
  - Pure immutable one-tool and all-tool ordered backup policy candidates
  - Immediate SET_TOOL_BACKUPS, RESTORE_TOOL_BACKUPS, and RESET_TOOL_BACKUPS commands
  - Strict runtime backup parsing and save-before-publish application helpers
affects: [05-02-backup-operation-queue, 05-03-notifications]

tech-stack:
  added: []
  patterns: [normalized frozen operation records, immutable candidates, save-before-publish]

key-files:
  created:
    - tests/test_tool_fallback_backups.py
  modified:
    - klippy/extras/tool_fallback_state.py
    - klippy/extras/tool_fallback.py
    - tests/test_tool_fallback_state.py

key-decisions:
  - "Runtime backup operations are normalized into frozen BackupOperation records before candidate construction."
  - "Immediate backup changes reject active workflow or transition contexts until the queued-operation contract is added by Plan 05-02."
  - "Reset-all validates and builds one complete candidate, then performs at most one persistence write."

patterns-established:
  - "Backup policy mutation: normalize complete operation, build immutable candidate from current state, save once, then publish."
  - "Exact backup-policy no-ops report the complete canonical policy and explicitly state no write."

requirements-completed: [BACKUP-01, BACKUP-02, BACKUP-03, BACKUP-05]

duration: 9 min
completed: 2026-06-11
---

# Phase 05 Plan 01: Atomic Runtime Backup Policy Commands Summary

**Atomic ordered backup-policy candidates and immediate G-Code commands with strict validation, no-op suppression, and save-before-publish persistence**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-11T18:54:00Z
- **Completed:** 2026-06-11T19:03:15Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added immutable one-tool and complete all-tool backup replacement operations that
  preserve schema v1, unrelated canonical state, requested order, and loop-safe cycles.
- Registered immediate set, restore, and reset backup-policy commands through one
  normalized candidate and persistence path.
- Added deterministic coverage for parsing, persistence ordering, no-op writes,
  failed-save non-publication, hardware neutrality, and future resolver behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pure ordered-backup state candidates** - `02a1a17` (feat)
2. **Task 2: Register and apply immediate backup-policy commands atomically** - `d20fb59` (feat)

## Files Created/Modified

- `klippy/extras/tool_fallback_state.py` - Pure immutable one-tool and all-tool backup
  policy candidate operations.
- `klippy/extras/tool_fallback.py` - Frozen operation record, strict parser, shared
  candidate/application path, and three immediate G-Code handlers.
- `tests/test_tool_fallback_state.py` - State candidate, rejection, immutability,
  ordering, no-op, and cycle-safe resolver coverage.
- `tests/test_tool_fallback_backups.py` - Immediate command, persistence, feedback,
  hardware-neutrality, and future-resolution coverage.

## Decisions Made

- Kept Plan 05-01 strictly immediate: commands reject active workflow and transition
  contexts without action, leaving ordered queueing and drains to Plan 05-02.
- Used configured immutable defaults only for explicit restore/reset operations;
  persisted runtime policy otherwise remains authoritative.
- Kept runtime operation records out of persisted schema v1.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first Task 2 commit attempt hit a sandbox read-only `.git/index.lock`; the same
  required non-destructive commit succeeded with approved git write access.
- Existing `pytest-asyncio` deprecation warnings remain; no behavioral failures occurred.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback_state.py klippy/extras/tool_fallback.py` - PASS
- `pytest -q tests/test_tool_fallback_state.py -k "backup or cycle"` - PASS, 18 tests
- `pytest -q tests/test_tool_fallback_state.py tests/test_tool_fallback_backups.py` - PASS, 90 tests
- `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_fallback.py` - PASS, 98 tests
- `pytest -q` - PASS, 292 tests
- `git diff --check` - PASS
- Persisted schema audit - PASS; schema remains v1 with no operation or queue records.
- Save ordering audit - PASS; changed immediate operations save once before publication,
  exact no-ops save zero times, and failed saves do not publish.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for Plan 05-02 to queue the same normalized `BackupOperation` records and reuse
  `_backup_candidate()` and `_apply_backup_operation()`.
- No blockers for deterministic queue integration.

## Self-Check: PASSED

Both task commits exist, all created files are present, every task acceptance criterion
and plan-level verification passed, and the persisted state contract remains schema v1.

---
*Phase: 05-notifications-integration-and-verification*
*Completed: 2026-06-11*
