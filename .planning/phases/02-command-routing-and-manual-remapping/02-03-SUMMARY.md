---
phase: 02-command-routing-and-manual-remapping
plan: 02-03
subsystem: routing
tags: [klipper, gcode, transitions, pause-ownership, pytest]

requires:
  - phase: 02-02
    provides: Persistent manual mapping commands and private physical selection
provides:
  - Guarded active-print route transition coordinator
  - Pause ownership and ownership-safe resume behavior
  - Persistence rollback and active-reset atomicity
  - Failure-containment coverage for active mapping changes
affects: [phase-3-conditional-purge, phase-4-temperature-transfer, phase-5-uat]

tech-stack:
  added: []
  patterns: [pause ownership, guarded transition sequencing, best-effort physical rollback]

key-files:
  created: []
  modified:
    - klippy/extras/tool_fallback.py
    - tests/conftest.py
    - tests/test_tool_fallback_routing.py

key-decisions:
  - "Active remap, restore, and reset operations share one reentrancy-guarded coordinator."
  - "Only a pause successfully initiated by the extension may be resumed by the extension."
  - "Persistence failure after selection preserves published state and attempts direct physical rollback."
  - "Pre-selection and post-selection extension points reserve later temperature-transfer and conditional-purge integration without implementing either behavior."

patterns-established:
  - "Changed active routes pause, warn, select privately, persist, and resume only after full success."
  - "Active reset publishes its complete identity candidate only after the active physical transition succeeds."

requirements-completed: []
requirements-partially-addressed: [ROUTE-05]

completed: 2026-06-07
---

# Phase 2 Plan 03: Active Print Transition Ownership Summary

**Guarded active-route transitions with pause ownership, persistence rollback, and failure containment**

## Performance

- **Tasks:** 3
- **Files modified:** 3
- **Full suite:** 140 passing tests

## Accomplishments

- Extended the fake Klipper adapter with mutable print state, ordered pause/resume script
  recording, and independent script failure injection.
- Replaced interim active-route rejection with one guarded coordinator shared by active
  remap, restore, and reset operations.
- Preserved existing user-owned pauses and resumed only pauses successfully initiated by
  the extension after the full Phase 2 transition sequence succeeded.
- Added best-effort physical rollback after persistence failure and combined reporting
  when rollback also fails.
- Proved active reset does not publish inactive identity changes before its active
  physical transition and complete candidate persistence succeed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend fakes for print state and adapter script sequencing** - `be9adfd` (test)
2. **Task 2: Implement guarded active-route transition coordination** - `a86335d` (feat)
3. **Task 3: Contain failures and prove atomic active reset behavior** - `87a275b` (feat)

## Files Created/Modified

- `klippy/extras/tool_fallback.py` - Active transition coordination, pause ownership,
  extension-stage hooks, persistence rollback, and guard cleanup.
- `tests/conftest.py` - Mutable print state plus ordered pause/resume recording and
  targeted script failure injection.
- `tests/test_tool_fallback_routing.py` - Ordered transition, ownership, reentrancy,
  failure-containment, rollback, resume-failure, and active-reset atomicity coverage.

## Decisions Made

- Pause before reporting the planned route warning so pause failure prevents every later
  transition stage.
- Reject changed active-route transitions when selected physical ownership is unknown.
- Keep temperature-transfer and conditional-purge hooks explicit but empty until their
  owning later phases integrate them.
- Publish a successfully persisted mapping even if the subsequent owned resume fails,
  while surfacing the resume failure and leaving the print paused.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None. Real-printer UAT remains explicitly deferred until Phase 5 feature-complete
integration verification.

## Requirement Status

ROUTE-05 remains partially addressed. Phase 2 now owns routing-transition sequencing and
failure containment; complete ROUTE-05 verification still depends on Phase 3 conditional
purge and Phase 4 temperature-transfer/stage execution.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback*.py` - PASS
- `pytest -q tests/test_tool_fallback_routing.py -k "print_state or script or pause"` - PASS, 12 tests
- `pytest -q tests/test_tool_fallback_routing.py -k "active or pause or transition or reentrant"` - PASS, 21 tests
- `pytest -q tests/test_tool_fallback_routing.py -k "failure or rollback or resume or reset"` - PASS, 22 tests
- `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_state.py` - PASS, 88 tests
- `pytest -q` - PASS, 140 tests
- `git diff --check` - PASS

## Self-Check: PASSED

All key files exist, all three task commits are present, every task acceptance criterion
is covered by automated tests, plan-level verification passes, ROUTE-05 remains partial,
and real-printer UAT remains deferred.

---
*Phase: 02-command-routing-and-manual-remapping*
*Completed: 2026-06-07*
