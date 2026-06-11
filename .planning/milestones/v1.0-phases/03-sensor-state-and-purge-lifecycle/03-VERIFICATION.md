---
phase: "03"
slug: sensor-state-and-purge-lifecycle
verified: 2026-06-08
status: passed
requirements_verified:
  - STATE-03
  - SENS-01
  - SENS-02
  - SENS-03
  - SENS-04
  - PURGE-01
  - PURGE-02
  - PURGE-03
  - PURGE-04
  - PURGE-05
requirements_partially_verified:
  - ROUTE-05
gaps: []
human_verification:
  - Real filament sensor hook behavior on representative Klipper hardware
  - Printer-specific purge macro behavior and pause/resume integration
  - Full fallback workflow including heating and backup traversal
---

# Phase 03: Sensor State And Purge Lifecycle Verification

## Result

**Status:** PASSED

Phase 03 satisfies its scoped requirements. The implementation adds graceful runtime
sensor authority, continuous symmetric debounce, sensor-confirmed durable filament
transitions, guarded explicit filament and purge state commands, recursion-free purge
execution, and conditional purge for active-print selections.

ROUTE-05 is only partially satisfied. Phase 03 adds conditional purge to ordinary
logical selections and active route transitions, but complete safe transition behavior
still depends on Phase 04 temperature transfer, fallback traversal, stage timeout, and
full fallback workflow work.

No implementation gaps were found within the Phase 03 boundary.

## Requirement Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| STATE-03 | SATISFIED | Startup publishes reconciled persisted state, then sensor readings become authoritative only after debounce. Unknown sensors preserve durable loaded/purged/failed history without presenting it as verified authority. See `ToolFallback._initialize_sensor_runtime()`, `_observe_sensor_reading()`, `_sensor_debounce_handler()`, and `FallbackState.with_reconciled_filament_loaded()`. Covered by startup reconciliation, unknown status, and persistence failure tests. |
| SENS-01 | SATISFIED | Per-tool `filament_sensor` configuration is optional; configured sensors are resolved at ready and read through strict `get_status()` validation. Missing, disabled, malformed, or failing sensors degrade to explicit unknown authority. Covered by sensor startup/status tests. |
| SENS-02 | SATISFIED | Insertions and removals share one restartable generation/deadline debounce path. Equal repeated polling does not extend deadlines, oscillation invalidates stale candidates, and expiry re-reads authority before committing. Covered by symmetric debounce and stale candidate tests. |
| SENS-03 | SATISFIED | Confirmed unloading clears `loaded` and `purged`; only selected-tool active-job runout marks `failed`. Ordinary unload and explicit unload preserve failed state as planned. Covered by runout and state candidate tests. |
| SENS-04 | SATISFIED | Confirmed insertion and explicit loaded state set `loaded=true`, clear `failed`, and mark unpurged. Covered by insert and explicit state tests. |
| PURGE-01 | SATISFIED | Public `PURGE_TOOL` invokes the distinct configured adapter and publishes `purged=true` only after adapter success and state persistence. Adapter and persistence failures preserve published unpurged state. |
| PURGE-02 | SATISFIED | No manual extrusion or unrelated script path mutates purge state; only explicit purge lifecycle commands and conditional purge do. |
| PURGE-03 | SATISFIED | Active-print logical selection of an unpurged tool pauses, selects, purges, persists purge state, publishes logical ownership, and resumes only on success. Active route transitions reuse Phase 2 pause ownership and purge before mapping persistence. |
| PURGE-04 | SATISFIED | Outside active prints, unpurged selections complete without running purge and report that the selected tool remains unpurged. |
| PURGE-05 | SATISFIED | `MARK_TOOL_PURGED` and `MARK_TOOL_UNPURGED` enforce canonical tools, known-unloaded rejection, unknown-authority warning, active-tool authorization, no-op behavior, and save-before-publish persistence. |
| ROUTE-05 | PARTIAL | Conditional purge is now integrated into active route transitions. Temperature transfer, fallback traversal, timeout stages, and complete safe transition execution remain intentionally deferred to Phase 04. |

## Behavioral Audit

| Behavior | Status | Evidence |
|----------|--------|----------|
| Graceful unknown sensor behavior | VERIFIED | Missing sensor configuration, missing objects, disabled status, malformed status, and status exceptions all reach ready with `authority=unknown`; routing remains installed. Unknown authority preserves durable state and emits selection/purge warnings instead of blocking ordinary use. |
| Debounce correctness | VERIFIED | Runtime uses generation and deadline checks, equal readings do not extend the deadline, stale callbacks are ignored, and authority is re-read at expiry before any durable write. Tests cover startup debounce, repeated polling, oscillation, stale cancellation, and persistence failure. |
| Outage pause once | VERIFIED | A selected physical tool becoming unknown while printing warns and pauses once only after `PAUSE` succeeds. Pause failure remains retryable, already-paused jobs do not claim ownership, and restored authority clears acknowledgement only after a fresh debounce. |
| Explicit state authorization | VERIFIED | `SET_TOOL_FILAMENT_STATE`, `MARK_TOOL_PURGED`, and `MARK_TOOL_UNPURGED` allow inactive tools during printing and reject selected-tool changes while actively printing; selected-tool changes are allowed while paused or outside a print. These commands do not trigger fallback or resume. |
| Purge recursion prevention | VERIFIED | `purge_gcode` defaults to `_TOOL_FALLBACK_PURGE` and normalized adapter values resolving to `PURGE_TOOL` are rejected. Public `PURGE_TOOL` calls only the configured adapter with `TOOL=Tn`. |
| Conditional purge ordering | VERIFIED | Ordinary active selection orders `PAUSE -> physical select -> purge adapter -> purge persist -> logical completion -> RESUME`. Active route transitions order `PAUSE -> physical select -> purge adapter -> purge persist -> mapping persist -> RESUME`. |
| Failure containment | VERIFIED | Purge adapter, purge persistence, selection, mapping persistence, pause, rollback, and resume failures keep incomplete work paused where applicable and prevent false logical mapping or purge success publication. |
| Scope boundaries | VERIFIED | Phase 03 does not implement backup traversal, automatic fallback execution, temperature transfer, heating, stage timeouts, external notifications, or real-printer UAT. The Phase 4 temperature hook remains explicit and empty. |

## Source Evidence

- `klippy/extras/tool_fallback_config.py`: optional `filament_sensor`, strict blank-value rejection, non-recursive purge adapter default and validation.
- `klippy/extras/tool_fallback_state.py`: immutable loaded/unloaded/failed/purged/unpurged candidates, invariant enforcement, schema v1 persistence.
- `klippy/extras/tool_fallback.py`: runtime sensor records, polling/debounce handlers, outage handling, explicit commands, purge authority, conditional selection purge, and active-transition purge integration.
- `tests/test_tool_fallback_sensor.py`: graceful startup, authority restoration, symmetric debounce, runout/insert semantics, explicit state authorization, outage pause/acknowledgement coverage.
- `tests/test_tool_fallback_purge.py`: public purge, manual purge state, unknown-authority warnings, no extrusion inference, conditional purge ordering, and purge failure containment coverage.
- `tests/test_tool_fallback_routing.py`: regression coverage that sensor hooks do not mutate routes or select backups, plus Phase 2 transition safety still passes with purge integration.

## Automated Verification

| Command | Result |
|---------|--------|
| `python3 -m py_compile klippy/extras/tool_fallback.py klippy/extras/tool_fallback_config.py klippy/extras/tool_fallback_state.py` | PASS |
| `pytest -q tests/test_tool_fallback_sensor.py tests/test_tool_fallback_purge.py` | PASS: 46 passed |
| `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_state.py tests/test_tool_fallback_config.py tests/test_tool_fallback_extension.py` | PASS: 165 passed |
| `pytest -q` | PASS: 211 passed |
| `git diff --check` | PASS |

Pytest emitted environment-level `pytest-asyncio` deprecation warnings. No warning
indicates a Phase 03 behavioral failure.

## Deferred Items

- **ROUTE-05 completion:** Phase 04 must add temperature transfer, safe stage execution,
  timeouts, and complete fallback transition behavior.
- **Automatic fallback:** backup graph traversal, failed-heater shutdown, persistent
  fallback remapping, transient recovery ownership, and exhausted-backup handling remain
  Phase 04 work.
- **Notifications and integration documentation:** meaningful external notifications,
  example configurations, and integration docs remain Phase 05 work.
- **Real-printer UAT:** live Klipper sensor hook behavior, printer-specific purge macros,
  and hardware pause/resume interactions remain assigned to Phase 05 by the milestone
  plan; this scheduling was not an explicit user deferral.

## Residual Risk

The automated suite uses deterministic Klipper fakes and strongly verifies state,
ordering, authorization, and failure containment. It cannot prove physical sensor
polarity, real `filament_switch_sensor` macro timing, or printer-specific purge macro
compatibility. Those risks are accepted by the explicit Phase 05 real-printer UAT
deferral.

No material gap remains within Phase 03 scope.
