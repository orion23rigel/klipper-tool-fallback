---
phase: 03
slug: sensor-state-and-purge-lifecycle
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-08
---

# Phase 03 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none |
| **Quick run command** | `pytest -q tests/test_tool_fallback_sensor.py tests/test_tool_fallback_purge.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | < 10 seconds |

## Sampling Rate

- **After every task commit:** Run the task-specific pytest command from the plan.
- **After every plan wave:** Run `pytest -q`.
- **Before phase verification:** Run `python3 -m py_compile klippy/extras/tool_fallback*.py && pytest -q`.
- **Max feedback latency:** 10 seconds.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | STATE-03, SENS-01 | T-03-01 | Missing or unavailable sensors degrade to unknown without aborting startup | integration | `pytest -q tests/test_tool_fallback_sensor.py -k "startup or unknown or unavailable"` | No - Wave 0 | Pending |
| 03-01-02 | 01 | 1 | SENS-02 | T-03-02 | Reactor debounce commits only stable readings and ignores stale timers | integration | `pytest -q tests/test_tool_fallback_sensor.py -k "debounce or timer"` | No - Wave 0 | Pending |
| 03-01-03 | 01 | 1 | STATE-03, SENS-03, SENS-04 | T-03-03 | Immutable state helpers preserve invariants for loaded/unloaded/failed/purged transitions | unit | `pytest -q tests/test_tool_fallback_state.py -k "filament or purge or failed"` | Yes | Pending |
| 03-02-01 | 02 | 2 | SENS-01, SENS-03, SENS-04 | T-03-04 | Runout/insert hooks and explicit macro state changes cannot trigger fallback or resume directly | integration | `pytest -q tests/test_tool_fallback_sensor.py -k "runout or insert or SET_TOOL_FILAMENT_STATE"` | No - Wave 0 | Pending |
| 03-02-02 | 02 | 2 | SENS-01, SENS-02 | T-03-05 | Selected-tool sensor outage pauses once and restores authority after valid re-enable debounce | integration | `pytest -q tests/test_tool_fallback_sensor.py -k "outage or acknowledged or reenable"` | No - Wave 0 | Pending |
| 03-03-01 | 03 | 3 | PURGE-01, PURGE-02, PURGE-05 | T-03-06 | Public purge and manual purge-state commands cannot recurse or publish false purge state | integration | `pytest -q tests/test_tool_fallback_purge.py -k "PURGE_TOOL or MARK_TOOL"` | No - Wave 0 | Pending |
| 03-03-02 | 03 | 3 | PURGE-03, PURGE-04, ROUTE-05 | T-03-07 | Active-print selection purges unpurged tools with owned pause/failure containment | integration | `pytest -q tests/test_tool_fallback_purge.py tests/test_tool_fallback_routing.py -k "conditional or purge or active"` | No - Wave 0 | Pending |

## Wave 0 Requirements

- [ ] `tests/test_tool_fallback_sensor.py` - sensor resolution, polling, debounce, runout/insert, unknown authority, explicit macro state.
- [ ] `tests/test_tool_fallback_purge.py` - public purge, manual purge-state commands, adapter recursion prevention, conditional purge integration.
- [ ] `tests/conftest.py` - fake filament sensor, reactor timer advancement, sensor enable/disable, purge script failures and ordered event assertions.
- [ ] Existing pytest infrastructure covers framework setup.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real `filament_switch_sensor` runout/insert hook behavior and `SET_FILAMENT_SENSOR` disable/re-enable behavior | SENS-01, SENS-02 | Requires a live Klipper installation and representative electrical sensor setup | Deferred until Phase 5 integration verification. |
| Printer-specific purge adapter execution and pause/resume interaction during actual tool selection | PURGE-01, PURGE-03, ROUTE-05 | Requires a safe live printer and operator supervision | Deferred until Phase 5 integration verification. |

## Validation Sign-Off

- [x] All tasks have automated verification or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing test references.
- [x] No watch-mode flags.
- [x] Feedback latency < 10 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-08
