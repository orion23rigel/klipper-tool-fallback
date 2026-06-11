---
phase: 03-sensor-state-and-purge-lifecycle
plan: 03-02
subsystem: sensor-runtime
tags: [klipper, sensors, debounce, state, pytest]

requires:
  - phase: 03-01
    provides: Graceful sensor runtime foundation and durable state candidates
provides:
  - Continuous symmetric per-tool sensor debounce
  - Debounced startup reconciliation with persistence-before-publication
  - `TOOL_FALLBACK_RUNOUT`, `TOOL_FALLBACK_INSERT`, and `SET_TOOL_FILAMENT_STATE`
  - Selected-tool sensor outage warning and one-time pause acknowledgement
  - Unknown-tool selection warnings without fallback traversal
affects: [03-03-purge-lifecycle, phase-4-fallback]

tech-stack:
  added: []
  patterns: [reactor debounce, save-before-publish, guarded operator authority]

key-files:
  created: []
  modified:
    - klippy/extras/tool_fallback.py
    - klippy/extras/tool_fallback_state.py
    - tests/test_tool_fallback_sensor.py
    - tests/test_tool_fallback_routing.py

key-decisions:
  - "Startup loaded reconciliation preserves an already-purged load while clearing failed."
  - "Runout and insert hooks restart sensor-authoritative debounce; they do not replace sensor authority."
  - "Explicit macro state changes are save-before-publish operator overrides and never trigger fallback or resume."
  - "Selected-tool authority loss while printing pauses once only after a successful pause command; pause failure remains retryable."
  - "A tool whose sensor authority is unknown remains selectable with warnings but cannot originate sensor-triggered fallback behavior."

requirements-completed: [STATE-03, SENS-01, SENS-02, SENS-03, SENS-04]
requirements-partially-addressed: []

completed: 2026-06-08
---

# Phase 3 Plan 02: Symmetric Debounce And Explicit Filament Authority Summary

**Trustworthy sensor-derived filament state with guarded macro authority and graceful outage handling**

## Accomplishments

- Added restartable per-tool debounce timers with generation/deadline checks, stale
  candidate cancellation, equal-poll non-extension, and symmetric insertion/removal
  confirmation.
- Reconciled startup sensor readings only after a full debounce interval, preserving
  loaded+purged state when still loaded and clearing failed only after persistence.
- Registered `TOOL_FALLBACK_RUNOUT`, `TOOL_FALLBACK_INSERT`, and
  `SET_TOOL_FILAMENT_STATE TOOL=Tn LOADED=0|1`.
- Implemented confirmed runout/insert semantics: selected-tool active-job runout marks
  failed; ordinary unload clears loaded/purged without marking failed; insertion loads,
  unpurges, and clears failed.
- Implemented explicit macro state authorization: inactive tools anytime, selected tool
  only outside a print or while paused.
- Added one-time selected-tool sensor outage warning/pause behavior, retryable pause
  failure, unknown-tool selection warnings, and debounce-gated authority restoration.
- Proved sensor events and explicit state commands do not mutate mappings, traverse
  backups, select backups, execute fallback, or auto-resume.

## Task Commits

1. **Task 1: Implement continuous symmetric debounce and startup reconciliation** - `bb65ab9`
2. **Task 2: Add event hooks and guarded explicit filament-state command** - `1f6c55e`
3. **Task 3: Handle sensor outages once and restore authority safely** - `62efbc9`

## Deviations from Plan

**[Rule 2 - Missing Critical Helper] Startup-loaded reconciliation helper** -
Found during: Task 1. The prior state module had `with_filament_loaded()`, but that
helper intentionally marks new filament unpurged and could not satisfy the required
startup case where persisted loaded+purged plus confirmed loaded must preserve purged
while clearing failed. Added `with_reconciled_filament_loaded()` to
`klippy/extras/tool_fallback_state.py` and covered it through startup reconciliation
tests. Verification: focused debounce tests, full sensor suite, state/routing suite,
and full suite passed. Commit: `bb65ab9`.

**Total deviations:** 1 auto-fixed missing implementation helper.
**Impact:** Positive; the helper narrows behavior to the required startup/restored
authority semantics and does not change persisted schema version.

## Issues Encountered

None.

## Deferred Work

- Plan 03-03 owns public purge commands, manual purge-state commands, and conditional
  purge during active-print selection.
- Automatic backup traversal, heating, notifications, timeout stages, and real-printer
  UAT remain deferred.
- Phase 3 still does not claim transient-resume ownership for standard sensor pauses.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback*.py` - PASS
- `pytest -q tests/test_tool_fallback_sensor.py -k "startup or reconcile or debounce or timer or stale or symmetric"` - PASS, 8 tests
- `pytest -q tests/test_tool_fallback_sensor.py tests/test_tool_fallback_routing.py -k "runout or insert or SET_TOOL_FILAMENT_STATE or failed or mapping"` - PASS, 10 tests
- `pytest -q tests/test_tool_fallback_sensor.py -k "outage or unknown or acknowledged or reenable or pause or backup"` - PASS, 10 tests
- `pytest -q tests/test_tool_fallback_sensor.py` - PASS, 25 tests
- `pytest -q tests/test_tool_fallback_state.py tests/test_tool_fallback_routing.py` - PASS, 108 tests
- `pytest -q` - PASS, 190 tests
- `git diff --check` - PASS
- Scope audit for sensor paths: PASS. No sensor path traverses backups, changes
  mappings, selects a fallback tool, executes heating/purge, sends notifications, or
  auto-resumes an ambiguous pause.
- Real-printer sensor and disable/re-enable UAT - intentionally deferred.

## Self-Check: PASSED

All task commits are present, every task acceptance criterion has automated coverage,
plan-level verification passes, schema version remains unchanged, runtime-only sensor
fields are not persisted, Phase 3 fallback traversal and purge/heating boundaries remain
intact, and real-printer UAT remains deferred.

---
*Phase: 03-sensor-state-and-purge-lifecycle*
*Completed: 2026-06-08*
