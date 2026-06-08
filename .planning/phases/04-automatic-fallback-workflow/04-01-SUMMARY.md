---
phase: 04-automatic-fallback-workflow
plan: 04-01
subsystem: automatic-fallback-foundation
tags: [klipper, runout, fallback, graph, checkpoint, pytest]

requires:
  - phase: 03-sensor-state-and-purge-lifecycle
    provides: Symmetric sensor debounce, durable runout state, and routing guards
provides:
  - Explicit validated runout pause ownership and owned-only transient recovery
  - Pure deterministic backup graph resolution with one fresh exhaustion rescan
  - Runtime-only workflow checkpoints, JSON-safe status, and conflict guards
affects: [04-02-heater-transfer, 04-03-complete-automatic-fallback]

tech-stack:
  added: []
  patterns: [runtime checkpoint, pure snapshot resolver, generation-stage guard]

key-files:
  created:
    - tests/test_tool_fallback_fallback.py
  modified:
    - klippy/extras/tool_fallback.py
    - tests/conftest.py

key-decisions:
  - "PAUSE_OWNED defaults to false and is accepted only for the selected tool in a paused active-job context."
  - "Pending runout ownership is held only by the runtime workflow checkpoint, never SensorRuntime."
  - "One-snapshot graph resolution is pure; fresh-state rescan remains extension orchestration."
  - "Unknown active logical ownership remains None rather than guessing a mapping."

requirements-completed: [FALL-01, FALL-02, FALL-03, FALL-04, FALL-05]
requirements-partially-addressed: [FALL-08]

completed: 2026-06-08
---

# Phase 4 Plan 01: Runout Ownership Graph Resolution And Runtime Foundation Summary

**Fail-closed ownership, deterministic backup resolution, and visible runtime workflow state**

## Accomplishments

- Added strict `PAUSE_OWNED=0|1` parsing and validation against selected-tool, paused,
  active-job context without inferring ownership from pause state alone.
- Kept pending runout ownership outside sensor runtime, persisted confirmed failed
  runout before coordinator handoff, and resumed confirmed transients exactly once only
  when explicitly owned.
- Added a pure ordered depth-first resolver that traverses failed/unloaded
  intermediaries, contains loops, suppresses duplicate work, trusts persisted
  eligibility under unknown sensor authority, and reports deterministic categories.
- Added separate fresh-snapshot rescan orchestration that performs exactly one second
  complete scan after exhaustion.
- Added runtime-only workflow checkpoints, JSON-safe status, generation/stage advancement
  validation, and conflict guards for logical selection, physical bypass, all mapping
  commands including inactive changes, and conflicting runout workflows.

## Task Commits

1. **Task 1: Add explicit pause ownership and transient recovery** - `601285b`
2. **Task 2: Implement pure ordered DFS backup resolution and re-scan** - `959d169`
3. **Task 3: Add runtime checkpoint status and workflow conflict guards** - `666095b`
4. **Final safety fix: Avoid guessing fallback logical ownership** - `7ca79a8`

## Deviations from Plan

**[Rule 1 - Bug] Unavailable-sensor hook could create a blocking checkpoint** -
Found during: Task 3 regression review. Checkpoint creation originally occurred before
verifying that the sensor was available and reporting unloaded. Moved pending-workflow
creation after successful sensor status validation and added regression coverage.
Files modified: `klippy/extras/tool_fallback.py`,
`tests/test_tool_fallback_fallback.py`. Verification: focused fallback, sensor, routing,
and full suites passed. Commit: `666095b`.

**[Rule 1 - Safety Bug] Unknown logical ownership was guessed from mappings** -
Found during: final invariant audit. Pending runout creation could select the first
logical mapping when no active logical route was known. Removed the guess so later
workflow stages can fail closed with `logical_tool=None`. Files modified:
`klippy/extras/tool_fallback.py`, `tests/test_tool_fallback_fallback.py`.
Verification: focused suites and full suite passed. Commit: `7ca79a8`.

**Total deviations:** 2 auto-fixed bugs.
**Impact:** Both fixes strengthen fail-closed behavior without expanding Phase 04-01
scope or changing persisted schema.

## Independent Risk Review

- Verified there are no `SensorRuntime.pending_runout_context` references.
- Verified coordinator handoff occurs only after successful failed-runout persistence,
  including an injected persistence-failure regression.
- Verified inactive mapping changes and public physical bypass are conflict-guarded.
- Verified pure one-snapshot resolution is separate from exactly-one fresh rescan.
- Verified ownership requires explicit `PAUSE_OWNED`, selected tool, paused state, and
  active-job context.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback*.py` - PASS
- `pytest -q tests/test_tool_fallback_fallback.py tests/test_tool_fallback_sensor.py` -
  PASS, 50 tests
- `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_state.py` -
  PASS, 108 tests
- `pytest -q` - PASS, 236 tests
- `git diff --check` - PASS
- Persisted schema-v1 runtime-field audit - PASS; no checkpoint, ownership,
  graph-report, timer, target-temperature, or heater fields exist in
  `tool_fallback_state.py`.
- Confirmed-runout ordering audit - PASS; callback is after successful
  persistence and is not reached on persistence failure.
- Real-printer UAT and external notifications remain deferred to Phase 5.

## Issues Encountered

Only environment-level `pytest-asyncio` deprecation warnings; no behavioral failures.

## Next Plan Readiness

Plan 04-02 can build heater transfer, stage deadlines, and guarded resume behavior on
the runtime checkpoint and conflict-guard foundation.

## Self-Check: PASSED

All task and safety-fix commits are present, every task acceptance criterion has
automated coverage, all plan verification commands pass, runtime workflow state remains
outside persisted schema v1, and unrelated dirty files were not modified or staged.

---
*Phase: 04-automatic-fallback-workflow*
*Completed: 2026-06-08*
