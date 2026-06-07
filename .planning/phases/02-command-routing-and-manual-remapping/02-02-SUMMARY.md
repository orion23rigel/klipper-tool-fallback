---
phase: 02-command-routing-and-manual-remapping
plan: 02-02
subsystem: routing
tags: [klipper, gcode, persistence, authorization, pytest]

requires:
  - phase: 02-01
    provides: Transactional handler capture and recursion-free logical routing
provides:
  - Immutable canonical mapping mutation helpers
  - Authorized recursion-free physical bypass
  - Persistent remap, restore, and reset commands
  - Interim fail-closed active-route mutation policy
affects: [02-03-active-transitions, phase-4-fallback]

tech-stack:
  added: []
  patterns: [save-before-publish mutation, private physical-selection authorization, fail-closed active-route dispatch]

key-files:
  created: []
  modified:
    - klippy/extras/tool_fallback.py
    - klippy/extras/tool_fallback_state.py
    - tests/conftest.py
    - tests/test_tool_fallback_routing.py
    - tests/test_tool_fallback_state.py

key-decisions:
  - "All mapping commands build immutable candidates and persist them before publishing runtime state."
  - "Public physical bypass is authorized by print state while internal selection remains a private direct-handler path."
  - "Active-print mutations that change the active logical route fail closed until Plan 02-03 installs transition ownership."

patterns-established:
  - "Exact no-op mapping mutations return the existing state object and perform no write or selection."
  - "Inactive logical routes may be changed during active jobs without selecting physical hardware."

requirements-completed: [ROUTE-03, ROUTE-04]

duration: 4 min
completed: 2026-06-07
---

# Phase 2 Plan 02: Persistent Manual Mapping Commands Summary

**Canonical persistent mapping commands with authorized physical bypass and fail-closed active-print route protection**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-07T12:47:43Z
- **Completed:** 2026-06-07T12:50:45Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added pure immutable remap, single-restore, and all-identity reset operations with route-specific validation.
- Added `SELECT_PHYSICAL_TOOL`, `REMAP_TOOL`, `RESTORE_TOOL`, and `RESET_TOOL_MAPPINGS`.
- Enforced save-before-publish consistency, no-op suppression, restart persistence, and direct-bypass print-state authorization.
- Rejected active-route changes during printing and paused jobs while allowing inactive-route persistence-only changes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pure canonical mapping mutation helpers** - `f882437` (feat)
2. **Task 2: Implement authorized physical bypass and persistence helper** - `ce3a8d4` (feat)
3. **Task 3: Implement persistent remap, restore, and reset commands** - `78d7551` (feat)

## Files Created/Modified

- `klippy/extras/tool_fallback_state.py` - Pure canonical mapping candidate helpers.
- `klippy/extras/tool_fallback.py` - Manual commands, active-print authorization, and save-before-publish mutation handling.
- `tests/conftest.py` - Mutable `FakePrintStats` support.
- `tests/test_tool_fallback_state.py` - Mapping immutability, validation, preservation, ordering, and no-op tests.
- `tests/test_tool_fallback_routing.py` - Bypass, mapping command, persistence, restart, and active-print policy tests.

## Decisions Made

- Treat both `printing` and `paused` as active for public physical bypass and route-change authorization.
- Return before print-state inspection for exact no-op candidates so no-op commands remain side-effect free.
- Keep Phase 2 mapping commands persistence-only outside the future guarded active-route transition coordinator.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None. Real-printer UAT remains deferred until the software is more feature complete.

## Next Phase Readiness

Plan 02-03 can replace the narrow fail-closed active-route branch with guarded pause,
selection, persistence, rollback, and resume ownership.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback*.py` - PASS
- `pytest -q tests/test_tool_fallback_state.py tests/test_tool_fallback_routing.py` - PASS, 78 tests
- `pytest -q` - PASS, 130 tests
- `git diff --check` - PASS

## Self-Check: PASSED

All five modified implementation/test files exist, all three task commits are present,
all task acceptance criteria are covered by automated tests, and every plan-level
verification passes.

---
*Phase: 02-command-routing-and-manual-remapping*
*Completed: 2026-06-07*
