---
phase: 11-user-prompt-flow
plan: 01
subsystem: tool-fallback
tags: [prompt-flow, undefined-tool, timeout, user-interaction]
dependency_graph:
  requires: [phase-10-undefined-tool-detection]
  affects: [phase-12-fallback-integration]
tech_stack:
  added: []
  patterns: [reactor-advance-polling, sentinel-flag-coordination, pause-resume-flow]
key_files:
  created: []
  modified:
    - klippy/extras/tool_fallback_config.py
    - klippy/extras/tool_fallback.py
    - klippy/extras/tool_fallback_state.py
    - tests/test_tool_fallback_extension.py
decisions:
  - D-01: undefined_tool_timeout defaults to 300.0s (5 minutes), validated as positive finite float
  - D-04: Pause uses existing pause_gcode mechanism, same as _on_confirmed_runout
  - D-06: Checkpoint stage advanced to "waiting_for_user" (source stays "undefined_tool")
  - D-12: Sentinel flag _undefined_tool_pending cleared by cmd_DEFINE_TOOL_BACKUP, not by polling state dict
  - D-13: Polling loop uses reactor.advance(0.1) — same pattern as _wait_for_heater_readiness
  - D-17: Default tool for timeout = first configured tool (lowest number)
  - D-19: Timeout uses new UNDEFINED_TOOL_TIMEOUT notification event with TIMEOUT reason code
  - D-23: Flow triggered from within cmd_TOOL_FALLBACK_TN itself after checkpoint creation
  - D-24: Polling loop used over reactor timer callback (simpler, consistent with existing code)
metrics:
  duration: ~45m
  completed: 2026-06-29
status: complete

# One-liner: Undefined tool prompt flow with configurable timeout, sentinel-flag coordination, and automatic fallback to first configured tool

## Objective

Implement the core user prompt flow: when Phase 10 detects an undefined tool, pause the print, display a prompt, wait for the user to define a backup tool (with configurable timeout), and resume.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Allow DEFINE_TOOL_BACKUP during waiting_for_user stage**
- **Found during:** Task 2 implementation
- **Issue:** `_guard_workflow_operation` blocked all operations during any checkpoint, including `DEFINE_TOOL_BACKUP` which is the only way users can respond to the prompt
- **Fix:** Added special case in `_guard_workflow_operation` to allow "tool backup definition" when checkpoint stage is "waiting_for_user"
- **Files modified:** klippy/extras/tool_fallback.py
- **Commit:** fc11145

**2. [Rule 1 - Bug] with_user_defined_backup validation too strict for undefined tools**
- **Found during:** Task 2 implementation
- **Issue:** `with_user_defined_backup()` validated that the logical tool is in `self.tools`, but undefined tools are by definition NOT configured — the timeout fallback needs to create mappings for them
- **Fix:** Removed the logical-tool-existence check from `with_user_defined_backup()`; only the backup target validation remains
- **Files modified:** klippy/extras/tool_fallback_state.py
- **Commit:** fc11145

**3. [Rule 1 - Bug] TIMEOUT not in REASON_CODES**
- **Found during:** Plan 11-02 test development
- **Issue:** `_handle_undefined_tool_timeout` used reason_code "TIMEOUT" but it wasn't in the `REASON_CODES` frozenset, causing notifications to be suppressed
- **Fix:** Added "TIMEOUT" to `REASON_CODES`
- **Files modified:** klippy/extras/tool_fallback.py
- **Commit:** 087b8fe

**4. [Rule 2 - Missing Critical Functionality] Allow undefined LOGICAL in DEFINE_TOOL_BACKUP during prompt**
- **Found during:** Plan 11-02 test development
- **Issue:** `cmd_DEFINE_TOOL_BACKUP` used `_require_configured_tool()` for the LOGICAL parameter, rejecting undefined tools that the prompt flow needs to accept
- **Fix:** Added special case in `cmd_DEFINE_TOOL_BACKUP` to accept any LOGICAL value when an active undefined-tool prompt is pending
- **Files modified:** klippy/extras/tool_fallback.py
- **Commit:** fc11145

**5. [Rule 1 - Bug] Existing tests updated for new prompt flow behavior**
- **Found during:** Task 2 implementation
- **Issue:** Pre-existing tests `test_tool_fallback_tn_unconfigured_triggers_undefined_flow` and `test_tool_fallback_tn_unconfigured_does_not_pause` expected old behavior (no prompt flow)
- **Fix:** Updated tests to reflect new synchronous prompt flow behavior (pause → timeout → resume)
- **Files modified:** tests/test_tool_fallback_extension.py
- **Commit:** fc11145

### No Architectural Changes Required
All changes fit within the existing ToolFallback architecture. No new files, no new classes, no schema changes.

## Auth Gates
None.

## Self-Check: PASSED
