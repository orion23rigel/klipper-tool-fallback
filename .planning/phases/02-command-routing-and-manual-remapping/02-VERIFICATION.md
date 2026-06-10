---
phase: "02"
slug: command-routing-and-manual-remapping
verified: 2026-06-07T08:59:07-04:00
status: passed
score: 4/4
requirements_verified:
  - ROUTE-02
  - ROUTE-03
  - ROUTE-04
requirements_partially_verified:
  - ROUTE-05
gaps: []
human_verification:
  - Representative Klipper installation and printer-specific macro compatibility
  - Active-print transition behavior on representative hardware
---

# Phase 02: Command Routing And Manual Remapping Verification

## Result

**Status:** PASSED

Phase 02 achieved its roadmap goal. Configured public `Tn` handlers are captured and
replaced transactionally, logical selections resolve persistent mappings and invoke
saved physical handlers without public-command recursion, and users can persistently
remap, restore, reset, or directly select physical tools under the planned authorization
rules.

Active remap, restore, and reset operations share a guarded transition coordinator with
pause ownership, private physical selection, save-before-publish persistence, rollback,
and failure containment. This verifies only the Phase 02 transition-ownership portion of
ROUTE-05. Complete ROUTE-05 remains intentionally deferred pending Phase 03 conditional
purge and Phase 04 temperature-transfer/stage execution.

No implementation gaps were found within the Phase 02 boundary.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every configured public `Tn` handler is captured and replaced as one fail-closed ready-time transaction. | VERIFIED | `_handle_ready()`, `_capture_physical_handlers()`, `_install_logical_handlers()`, and `_restore_physical_handlers()` in `klippy/extras/tool_fallback.py:98-142`; missing-handler, replacement-failure, and later-ready-failure tests pass. |
| 2 | Logical `Tn` commands resolve current persistent mappings and directly invoke saved physical handlers without recursion. | VERIFIED | `_route_logical()` and `_select_physical()` in `klippy/extras/tool_fallback.py:148-165`; tests prove mapped physical command identity, no public redispatch, no ordinary-selection write, and ownership publication only after success. |
| 3 | Manual remap, restore, and reset operations are immutable, canonical, atomic, and restart-persistent. | VERIFIED | `FallbackState.with_mapping()`, `with_identity_mapping()`, and `with_identity_mappings()` in `klippy/extras/tool_fallback_state.py:137-158`, plus save-before-publish command handling in `tool_fallback.py:81-96,166-182`; state and routing tests pass. |
| 4 | Direct physical bypass is recursion-free, preserves logical ownership and policy, and is unavailable during printing or paused jobs. | VERIFIED | `cmd_SELECT_PHYSICAL_TOOL()` in `klippy/extras/tool_fallback.py:73-79`; authorization, validation, direct-call, and ownership tests pass. |
| 5 | Changed active routes use one guarded transition coordinator that preserves pause ownership and contains failures. | VERIFIED | `_transition_active_route()` in `klippy/extras/tool_fallback.py:184-228`; ordered success, already-paused, unknown ownership, reentrancy, pause/selection/persistence/rollback/resume failure, and active-reset atomicity tests pass. |
| 6 | Heating and conditional purge are not falsely claimed as implemented. | VERIFIED | Explicit empty integration hooks remain at `klippy/extras/tool_fallback.py:230-238`; roadmap, plans, summaries, and validation consistently leave final ROUTE-05 completion to Phases 03 and 04. |

## Requirement Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ROUTE-02 | SATISFIED | Ready-time interception replaces configured logical `Tn` commands; each invocation resolves the current persisted mapping and calls the mapped saved physical handler. |
| ROUTE-03 | SATISFIED | Original physical handlers are retained in a read-only mapping and invoked directly with clean synthetic physical `Tn` command identity; public routing commands are never redispatched internally. |
| ROUTE-04 | SATISFIED | `REMAP_TOOL`, `RESTORE_TOOL`, and `RESET_TOOL_MAPPINGS` validate canonical configured names, suppress no-ops, save before publication, survive restart, and preserve prior state on persistence failure. |
| ROUTE-05 | PARTIALLY SATISFIED | Phase 02 verifies active-route transition ownership and routing safety: pause ownership, warning, private selection, persistence, rollback, guarded resume, reentrancy prevention, and failure containment. It does not yet perform temperature transfer or conditional purge, so the complete safe transition requirement remains open. |

No orphaned Phase 02 requirements or unplanned requirement claims were found.

## Failure And Safety Evidence

- Missing configured physical handlers, partial wrapper installation, and later ready
  failures restore original public handlers and leave runtime routing unpublished.
- Physical-handler failure does not publish false active logical or selected physical
  ownership.
- Mapping mutation failures preserve the previously published state.
- Public physical bypass rejects both `printing` and `paused` states.
- Active-route transitions reject unknown selected-physical ownership and reentrancy.
- Pause or selection failure prevents persistence and resume.
- Persistence failure preserves published mapping state, attempts direct physical
  rollback, reports rollback failure when applicable, and does not resume.
- Existing user-owned pauses are never resumed by the extension.
- Active reset publishes inactive and active identity mappings together only after the
  active transition succeeds.

## Automated Verification

| Command | Result |
|---------|--------|
| `python3 -m py_compile klippy/extras/tool_fallback.py klippy/extras/tool_fallback_config.py klippy/extras/tool_fallback_state.py` | PASS |
| `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_state.py` | PASS: 88 passed |
| `pytest -q` | PASS: 140 passed |
| `git diff --check` | PASS |

Pytest emitted environment-level `pytest-asyncio` deprecation warnings; no test failed
and no Phase 02 behavior depends on asyncio.

## Deferred Items

- **ROUTE-05 completion:** Phase 03 must integrate conditional purge, and Phase 04 must
  integrate temperature transfer and remaining safe-transition stages.
- **Real-printer UAT:** Representative Klipper macro command identity and active-print
  remap behavior require a live installation and supervised hardware testing. Per user
  direction and `02-VALIDATION.md`, these remain deferred until the software is more
  feature complete and Phase 05 integration verification begins.
- Sensor state, backup traversal, automatic fallback, stage timeouts, heater control,
  purge execution, and external notifications remain outside Phase 02.

## Residual Risk

The automated suite uses focused Klipper fakes. It strongly verifies ordering,
authorization, persistence consistency, and failure containment, but cannot prove
compatibility with every printer-specific original `Tn` macro or physical toolchanger.
That residual integration risk is accepted by the explicit real-printer UAT deferral.

No material gap remains within Phase 02 scope.

