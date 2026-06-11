---
phase: 03-sensor-state-and-purge-lifecycle
plan: 03-01
subsystem: sensor-runtime
tags: [klipper, sensors, state, configuration, pytest]

requires:
  - phase: 02-03
    provides: Transactional ready-time routing and active transition ownership
provides:
  - Optional sensor configuration with explicit unknown-authority degradation
  - Non-recursive configured purge-adapter contract
  - Immutable durable filament and purge state candidates
  - Deterministic reactor timers and filament-sensor test fakes
  - Ready-time sensor runtime records and JSON-safe authority status
affects: [03-02-debounce-and-explicit-state, 03-03-purge-lifecycle, phase-4-fallback]

tech-stack:
  added: []
  patterns: [runtime-only sensor authority, immutable state candidates, bounded polling]

key-files:
  created:
    - tests/test_tool_fallback_sensor.py
  modified:
    - klippy/extras/tool_fallback_config.py
    - klippy/extras/tool_fallback_state.py
    - klippy/extras/tool_fallback.py
    - tests/conftest.py
    - tests/test_tool_fallback_config.py
    - tests/test_tool_fallback_state.py
    - tests/test_tool_fallback_extension.py

key-decisions:
  - "Omitted filament sensors degrade tools to unknown authority; explicit blank values remain configuration errors."
  - "Configured purge adapters default to _TOOL_FALLBACK_PURGE and cannot resolve to public PURGE_TOOL."
  - "Sensor authority, readings, timer handles, and outage acknowledgement remain runtime-only."
  - "Ready-time sensor resolution occurs after canonical routing/state publication and never aborts for unavailable or invalid sensors."

requirements-completed: []
requirements-partially-addressed: [STATE-03, SENS-01, SENS-03, SENS-04, PURGE-01, PURGE-05]

completed: 2026-06-08
---

# Phase 3 Plan 01: Durable State And Sensor Runtime Foundation Summary

**Graceful sensor authority, immutable durable transitions, and purge-adapter recursion prevention**

## Accomplishments

- Made per-tool filament sensors optional while preserving strict validation for explicit
  blank values and existing heater/timing contracts.
- Changed the configured purge adapter default to `_TOOL_FALLBACK_PURGE` and rejected
  every normalized adapter form that invokes public `PURGE_TOOL`.
- Added immutable loaded, unloaded, failed-runout, purged, and unpurged state candidates
  with exact no-op identity and `loaded=false => purged=false` enforcement.
- Added deterministic reactor timer, filament sensor, and strict integer parsing fakes.
- Added ready-time runtime sensor records, bounded polling, graceful unknown-authority
  degradation, and deterministic JSON-safe status.

## Task Commits

1. **Task 1: Migrate configuration and extend deterministic runtime fakes** - `011692d`
2. **Task 2: Add immutable durable filament and purge state candidates** - `e91bf51`
3. **Task 3: Resolve sensors gracefully and publish runtime authority status** - `49b26a4`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Deferred Work

- Plan 03-02 owns symmetric debounce, durable sensor-confirmed transitions, outage
  acknowledgement behavior, and explicit filament-state commands.
- Plan 03-03 owns public purge commands and conditional purge integration.
- Automatic fallback traversal, heating, notifications, and real-printer UAT remain
  deferred to later phases.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback*.py` - PASS
- `pytest -q tests/test_tool_fallback_config.py tests/test_tool_fallback_state.py` -
  PASS, 106 tests
- `pytest -q tests/test_tool_fallback_sensor.py tests/test_tool_fallback_extension.py` -
  PASS, 20 tests
- `pytest -q` - PASS, 175 tests
- `git diff --check` - PASS
- Purge adapter default and normalized recursion rejection contract - PASS
- Real-printer UAT - intentionally deferred

## Self-Check: PASSED

All task commits are present, every plan acceptance criterion has automated coverage,
the complete suite passes, persisted schema remains version 1, runtime-only sensor
fields are absent from persisted state, and real-printer UAT remains deferred.

---
*Phase: 03-sensor-state-and-purge-lifecycle*
*Completed: 2026-06-08*
