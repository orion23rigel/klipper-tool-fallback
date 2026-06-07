---
phase: 02-command-routing-and-manual-remapping
plan: 02-01
subsystem: routing
tags: [klipper, gcode, routing, transactions, pytest]

requires:
  - phase: 01-03
    provides: Ready-time canonical state publication and status surfaces
provides:
  - Transactional ready-time capture and replacement of configured Tn handlers
  - Recursion-free logical routing through saved physical handlers
  - Transient active-logical, selected-physical, and transition status
affects: [02-02-manual-mapping, 02-03-active-transitions, phase-4-fallback]

tech-stack:
  added: []
  patterns: [recoverable handler interception, direct physical invocation, publish ownership after success]

key-files:
  created:
    - tests/test_tool_fallback_routing.py
  modified:
    - klippy/extras/tool_fallback.py
    - tests/conftest.py
    - tests/test_tool_fallback_extension.py

key-decisions:
  - "Configured public Tn handlers are captured, replaced, and persisted as one fail-closed ready-time transaction."
  - "Logical routes directly invoke saved physical handlers with clean synthetic physical command identity."
  - "Active logical and selected physical ownership remain transient and publish only after physical selection succeeds."

patterns-established:
  - "Ready-time routing interception restores all original handlers on any failure before publication."
  - "Ordinary logical selection resolves the current canonical mapping without writing persisted state."

requirements-completed: [ROUTE-02, ROUTE-03]

completed: 2026-06-07
---

# Phase 2 Plan 01: Transactional Handler Capture And Logical Routing Summary

**Fail-closed public Tn interception with recursion-free mapped physical selection and transient ownership**

## Performance

- **Tasks:** 3
- **Files modified:** 4
- **Full suite:** 95 passing tests

## Accomplishments

- Extended the Klipper fake harness with observable synthetic G-code commands and registered-command invocation.
- Added transactional capture, replacement, and rollback for every configured public `Tn` handler at ready time.
- Routed logical commands through the current persisted mapping by directly invoking saved physical handlers.
- Added transient ownership and transition status that resets to unknown after restart.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend the Klipper fake harness for routing contracts** - `fa9553d` (test)
2. **Task 2: Implement fail-closed ready-time capture and replacement** - `a8a06b0` (feat)
3. **Task 3: Route logical commands without recursion and expose ownership** - `9fc8321` (feat)

## Files Created/Modified

- `klippy/extras/tool_fallback.py` - Transactional interception, logical routing, physical invocation, and transient status.
- `tests/conftest.py` - Synthetic command creation and command invocation support.
- `tests/test_tool_fallback_extension.py` - Ready-handler setup and transient status regression coverage.
- `tests/test_tool_fallback_routing.py` - Capture, rollback, direct routing, ownership, and restart tests.

## Decisions Made

- Perform state reconciliation, handler capture, wrapper installation, persistence, and runtime publication as one recoverable ready transaction.
- Create a clean parameterless physical `Tn` command for saved handler invocation instead of redispatching public G-code.
- Keep routing ownership out of schema v1 because persisted mappings are policy, not hardware-selection truth.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- An initial rollback test compared the full command registry and incorrectly included the unrelated status command. The assertion was narrowed to configured public tool handlers before Task 2 was committed.

## User Setup Required

None. Real-printer UAT remains deferred until the software is more feature complete.

## Next Phase Readiness

The routing layer is ready for Plan 02-02 to add persistent manual remap, restore,
reset, and physical-bypass commands.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback*.py` - PASS
- `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_extension.py` - PASS, 22 tests
- `pytest -q` - PASS, 95 tests
- `git diff --check` - PASS

## Self-Check: PASSED

All key files exist, all three task commits are present, all acceptance criteria are
covered by automated tests, and every plan-level verification passes.

---
*Phase: 02-command-routing-and-manual-remapping*
*Completed: 2026-06-07*
