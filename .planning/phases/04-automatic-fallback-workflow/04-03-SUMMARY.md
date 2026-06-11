---
phase: 04-automatic-fallback-workflow
plan: 04-03
subsystem: automatic-fallback-orchestration
tags: [klipper, runout, fallback, heating, resume, pytest]

requires:
  - phase: 04-01
    provides: Explicit pause ownership, backup resolution, and runtime checkpoints
  - phase: 04-02
    provides: Fail-closed heater shutdown and destination preheat stages
provides:
  - Confirmed-runout automatic fallback orchestration
  - Guarded heating-timeout recovery through RESUME
  - Pre-selection source shutdown, destination preheat, and readiness waiting
  - Failure containment without automatic rollback or second selection
affects: [phase-5-notifications-integration-verification]

tech-stack:
  added: []
  patterns: [ordered fallback stages, guarded resume, fail-closed checkpoint]

key-files:
  modified:
    - klippy/extras/tool_fallback.py
    - tests/test_tool_fallback_fallback.py
    - tests/test_tool_fallback_sensor.py
    - tests/test_tool_fallback_routing.py

key-decisions:
  - "Authoritative runout commands seed debounce and confirmed-runout workflow state."
  - "Only an explicitly owned heating-timeout checkpoint may continue through normal RESUME."
  - "Source shutdown, destination preheat, and readiness waiting complete before selection proceeds."
  - "Automatic fallback failure never triggers physical rollback or a second candidate selection."

requirements-completed: [FALL-01, FALL-02, FALL-03, FALL-04, FALL-05, FALL-06, FALL-07, FALL-08, ROUTE-05]
requirements-partially-addressed: []

completed: 2026-06-09
---

# Phase 4 Plan 03: Complete Automatic Fallback And Failure Containment Summary

**Complete ordered automatic fallback with guarded recovery and fail-closed containment**

## Accomplishments

- Connected authoritative runout and insert commands to deterministic debounce and
  confirmed-runout workflow state.
- Completed automatic fallback ordering across source shutdown, backup resolution,
  destination preheat, physical selection, asynchronous heating readiness, conditional
  purge, canonical mapping persistence, and owned-only resume.
- Added guarded `RESUME` handling for recoverable heating-timeout checkpoints while
  rejecting incomplete or unowned fallback recovery.
- Preserved paused, visible failure checkpoints and prohibited automatic physical
  rollback or a second candidate selection after selection begins.
- Kept external notifications, example integration, and real-printer UAT outside
  Phase 4 scope.

## Implementation Commits

1. **Authoritative runout and debounce seeding** - `05d60ff`
2. **Remove implementation debug output** - `6aa6b28`
3. **Guarded heating-timeout resume** - `ea6df22`
4. **Pre-selection transition stages and resume reentrancy guard** - `d730d1d`
5. **Pass command context through pre-selection transition stages** - `9c3dcc3`

The implementation was merged by PR #1 in `d51f2c2`. Planning completion was recorded
in `15caa6c`, and release `v1.0.0` was created.

## Deviations from Plan

**[Recovery - Missing artifact]** The implementation, tests, milestone completion, and
release were already merged, but this plan summary was not created. The safe-resume
gate prevented duplicate execution. This summary was reconstructed from the merged
implementation, commit history, completion record, and fresh verification results.

**Total deviations:** 1 planning-artifact recovery.  
**Impact:** No production or test code changed during reconciliation.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback.py klippy/extras/tool_fallback_config.py klippy/extras/tool_fallback_state.py` - PASS
- `pytest -q tests/test_tool_fallback_fallback.py` - PASS, 41 tests
- `pytest -q tests/test_tool_fallback_sensor.py tests/test_tool_fallback_purge.py tests/test_tool_fallback_routing.py` - PASS, 96 tests
- `pytest -q` - PASS, 252 tests
- `git diff --check` - PASS
- External notification and example-integration scope audit - PASS; no adapter or
  examples directory was introduced.

## Issues Encountered

- Existing `pytest-asyncio` deprecation warnings remain; no behavioral failures occurred.
- A milestone integration audit found blocked-stage continuation, missing purge-overrun
  enforcement, lost resume-failure checkpoints, and missing logical-route publication.
  These and a guarded-resume blocked-stage continuation were corrected with regression
  coverage; the full suite now passes 260 tests.

## Self-Check: PASSED

The merged implementation commits are present, all plan verification commands pass,
the full regression suite is green, Phase 4 scope remains contained, and the missing
summary now reconciles artifact-based progress with the recorded completed milestone.

---
*Phase: 04-automatic-fallback-workflow*
*Completed: 2026-06-09*
