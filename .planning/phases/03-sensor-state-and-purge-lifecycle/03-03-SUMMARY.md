---
phase: 03-sensor-state-and-purge-lifecycle
plan: 03-03
subsystem: purge-lifecycle
tags: [klipper, purge, routing, pause-ownership, pytest]

requires:
  - phase: 03-01
    provides: Recursion-free purge adapter contract and durable purge candidates
  - phase: 03-02
    provides: Sensor authority and guarded explicit-state authorization
  - phase: 02-03
    provides: Active-route transition pause ownership and failure containment
provides:
  - Public PURGE_TOOL and guarded manual purge-state commands
  - Shared recursion-free purge authority with save-before-publish truth
  - Conditional purge for ordinary active-print logical selections
  - Conditional purge integrated before active-route mapping publication
affects: [phase-4-fallback, phase-5-integration-verification]

tech-stack:
  added: []
  patterns: [conditional selection purge, explicit pause ownership, mapping-state merge]

key-files:
  created:
    - tests/test_tool_fallback_purge.py
  modified:
    - klippy/extras/tool_fallback.py
    - tests/test_tool_fallback_routing.py

key-decisions:
  - "Public PURGE_TOOL always invokes the distinct configured adapter once, while automatic selection preserves the already-purged fast path."
  - "Unknown-authority purge is operator-authorized and establishes loaded+purged durable truth after adapter success."
  - "Active-route mapping candidates are rebuilt from post-purge canonical state so mapping persistence cannot overwrite successful purge truth."
  - "ROUTE-05 remains partial pending Phase 4 temperature transfer and complete safe-stage execution."

requirements-completed: [PURGE-01, PURGE-02, PURGE-03, PURGE-04, PURGE-05]
requirements-partially-addressed: [ROUTE-05]

completed: 2026-06-08
---

# Phase 3 Plan 03: Purge Lifecycle And Selection Integration Summary

**Recursion-free durable purge authority integrated with ordinary selection and active-route transitions**

## Accomplishments

- Registered public `PURGE_TOOL`, `MARK_TOOL_PURGED`, and
  `MARK_TOOL_UNPURGED` commands with canonical tool validation, unknown-authority
  warnings, known-unloaded rejection, guarded manual authorization, and exact no-op
  persistence suppression.
- Implemented one internal purge authority that invokes only the distinct configured
  adapter with canonical `TOOL=Tn`, then persists and publishes purge truth only after
  adapter success.
- Added conditional purge coordination for ordinary logical selection: printing jobs
  use one owned pause and resume only after complete success; already-paused jobs never
  resume; outside-print selection reports unpurged state without purging.
- Integrated conditional purge into active remap, restore, and reset after physical
  selection and before mapping persistence/resume, preserving prior route truth on
  purge failures.
- Added focused purge lifecycle, ordering, authorization, warning, recursion, no-op,
  and failure-containment coverage while preserving Phase 2 routing regressions.

## Task Commits

1. **Task 1: Implement recursion-free purge authority and manual purge-state commands** - `43bca34`
2. **Task 2: Coordinate conditional purge for ordinary logical selection** - `0241cbc`
3. **Task 3: Integrate conditional purge with active route transitions** - `c0b3cf5`
4. **Post-task contract fix: Preserve explicit repurge semantics** - `0769bc4`

## Deviations from Plan

**[Rule 1 - Bug] Explicit repurge fast-path conflict** - Found during final contract
audit after Task 3. The shared purge authority initially skipped the adapter whenever a
tool was already marked purged, which was correct for automatic selection but violated
the explicit public `PURGE_TOOL` contract. Added a narrow `force` path for public purge
so it invokes the adapter exactly once without unnecessary persistence, while automatic
selection retains its fast path. Files modified: `klippy/extras/tool_fallback.py`,
`tests/test_tool_fallback_purge.py`. Verification: focused purge tests and full suite
passed. Commit: `0769bc4`.

**Total deviations:** 1 auto-fixed bug. **Impact:** Public explicit purge semantics now
match the command contract without adding duplicate automatic purge behavior.

## Issues Encountered

- Phase 2 routing-only persistence/rollback tests used unpurged default tools and began
  failing at the newly inserted purge stage. Those regressions were kept scoped to
  routing by explicitly seeding purged tools; dedicated Phase 3 tests now cover purge
  ordering and purge-stage failures.

## Deferred Work

- ROUTE-05 remains partial until Phase 4 adds temperature transfer and complete safe
  transition stage execution.
- Automatic backup traversal, fallback execution, heating, timeout stages, external
  notifications, and real-printer UAT remain deferred.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback*.py` - PASS
- `pytest -q tests/test_tool_fallback_purge.py` - PASS, 21 tests
- `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_state.py` -
  PASS, 108 tests
- `pytest -q` - PASS, 211 tests
- `git diff --check` - PASS
- Public `PURGE_TOOL` distinct-adapter recursion audit - PASS
- PURGE-01 through PURGE-05 complete; ROUTE-05 remains partial - PASS
- Real-printer purge and pause/resume UAT - intentionally deferred

## Self-Check: PASSED

All implementation and summary artifacts exist, task commits are present, every
acceptance criterion has automated coverage, the full suite passes, public purge cannot
resolve to itself, failure paths do not resume incomplete transitions or publish false
route/purge truth, and Phase 4/5 boundaries remain intact.

---
*Phase: 03-sensor-state-and-purge-lifecycle*
*Completed: 2026-06-08*
