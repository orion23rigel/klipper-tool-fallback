# Phase 11: User Prompt Flow — Verification

**Phase**: 11-user-prompt-flow
**Date**: 2026-06-29
**Status**: verified

## Summary

Phase 11 implements the pause/prompt/wait/resume flow for undefined tool detection. When a tool is referenced that has no configuration, the system pauses the print, displays a prompt instructing the user to run `DEFINE_TOOL_BACKUP Tn Tm`, waits for user input or a configurable timeout (default 300s), then resumes — either after the user defines a backup tool or by automatically falling back to the first configured tool.

**Tests: 45/45 passed** (including 9 new prompt-flow tests)

## Requirements Verification

### PROMPT-01: Pause on undefined tool detection

**Expected**: When an undefined tool is detected during print, the print pauses via `pause_gcode`.

**Verified**: `_handle_undefined_tool_prompt` (tool_fallback.py:1082-1091) calls `self._print_is_active()` and if true, runs `pause_gcode` via `self.gcode.run_script_from_command()`. Test `test_undefined_tool_prompt_triggers_pause` confirms `print_stats.state == "paused"` and `"PAUSE"` in script events.

**Result**: PASS

### PROMPT-02: Console displays prompt message

**Expected**: Klipper console shows "Tool Tn not defined. Define a backup tool: `DEFINE_TOOL_BACKUP Tn Tm`".

**Verified**: `_handle_undefined_tool_prompt` (tool_fallback.py:1094-1096) calls `self.gcode.respond_info()` with the formatted prompt. Test `test_undefined_tool_prompt_displays_message` confirms both "Tn not defined" and "DEFINE_TOOL_BACKUP Tn" appear in responses.

**Result**: PASS

### PROMPT-03: System waits for user input or timeout

**Expected**: The system polls via a reactor loop, waiting for the user to submit `DEFINE_TOOL_BACKUP` (clearing `_undefined_tool_pending` sentinel) or for the timeout to expire.

**Verified**: `_handle_undefined_tool_prompt` (tool_fallback.py:1111-1124) implements a `while True` loop that checks `self._undefined_tool_pending is None` (cleared by `cmd_DEFINE_TOOL_BACKUP` at line 387) and `now >= timeout_deadline`. Uses `reactor.advance(0.1)` consistent with existing polling patterns. Sentinel flag is set at line 1100.

Tests:
- `test_undefined_tool_prompt_sets_sentinel` — confirms sentinel is set and checkpoint stage is "waiting_for_user"
- `test_undefined_tool_prompt_no_print_stats_no_pause` — edge case: no print_stats, prompt still displayed, sentinel still set

**Result**: PASS

### PROMPT-04: Resume after user defines backup

**Expected**: After the user defines a backup tool via `DEFINE_TOOL_BACKUP`, the print resumes via `resume_gcode`.

**Verified**: When `_undefined_tool_pending` is cleared by `cmd_DEFINE_TOOL_BACKUP`, the wait loop breaks (tool_fallback.py:1115-1116) and execution proceeds to the resume block (tool_fallback.py:1126-1141), which calls `resume_gcode` then `_finalize_undefined_tool_success()`. Test `test_undefined_tool_user_response_resumes` confirms sentinel cleared, state updated, `print_stats.state == "printing"`, and `"RESUME"` in script events.

Guard: `_guard_workflow_operation` (tool_fallback.py:1602) allows "tool backup definition" during `waiting_for_user` stage — all other operations blocked.

**Result**: PASS

### PROMPT-05: Timeout falls back to first configured tool

**Expected**: After `undefined_tool_timeout` seconds (default 300.0s), the system falls back to the first configured tool and resumes.

**Verified**: Timeout path (tool_fallback.py:1119-1121) calls `_handle_undefined_tool_timeout()`, which selects `next(iter(self.config.tools))` as the default tool (first configured, lowest number per D-17), calls `self.state.with_user_defined_backup(undefined_tool, default_tool)` to auto-define the mapping, persists state, displays timeout message, clears sentinel, runs `resume_gcode`, and finalizes with `_finalize_undefined_tool_success()`.

State validation: `with_user_defined_backup` (tool_fallback_state.py:313-332) only validates the backup target exists — not the logical tool — so undefined tools can be mapped during timeout.

Test `test_undefined_tool_timeout_falls_back_to_default` uses 0.05s timeout, advances reactor 1.0s, confirms sentinel cleared, mapping set to "T0", print resumed, and timeout message displayed.

Config validation: Test `test_undefined_tool_config_validation` confirms zero, negative, and infinity values are rejected by `_positive_finite_float()`.

**Result**: PASS

### PROMPT-06: Timeout events logged via notification system

**Expected**: Timeout events are logged via the existing notification system.

**Verified**: `_handle_undefined_tool_timeout` (tool_fallback.py:1174-1177) calls `self._attempt_notification(self._terminal_event(completed, "UNDEFINED_TOOL_TIMEOUT", "TIMEOUT", reason_detail=undefined_tool))`. Both "UNDEFINED_TOOL_TIMEOUT" and "UNDEFINED_TOOL_SUCCESS" are in `NOTIFICATION_EVENTS` (tool_fallback.py:16-18). "TIMEOUT" is in `REASON_CODES` (tool_fallback.py:22).

Test `test_undefined_tool_timeout_sends_notification` confirms `"UNDEFINED_TOOL_TIMEOUT"` appears in script events.

**Result**: PASS

## Additional Verification

### Sentinel flag coordination

- `_undefined_tool_pending` initialized to `None` in `__init__` (tool_fallback.py:191)
- Set to undefined tool name when prompt active (tool_fallback.py:1100)
- Cleared by `cmd_DEFINE_TOOL_BACKUP` when user defines backup (tool_fallback.py:386-387)
- Cleared on timeout (tool_fallback.py:1170)
- Cleared on successful resume (tool_fallback.py:1127)

### Config field

- `undefined_tool_timeout: float` added to `GlobalConfig` dataclass (tool_fallback_config.py:22)
- Parsed with `_positive_finite_float(config, "undefined_tool_timeout", 300.0)` (tool_fallback_config.py:106-107)
- Default: 300.0 seconds (5 minutes)

### Edge cases handled

1. **No print_stats**: Prompt still displayed, sentinel set, no pause attempted (test: `test_undefined_tool_prompt_no_print_stats_no_pause`)
2. **Resume failure after user response**: Workflow blocked with "RESUME_FAILED" stage (test: `test_undefined_tool_prompt_resume_failure_blocks`)
3. **Resume failure after timeout**: Workflow blocked with "RESUME_FAILED" stage (tool_fallback.py:1183-1187)
4. **Persist failure during timeout**: Workflow blocked (tool_fallback.py:1158-1161)
5. **Pause failure**: Workflow blocked (tool_fallback.py:1087-1091)
6. **Self-backup rejection**: `logical_tool == backup_tool` rejected (tool_fallback.py:364-366)
7. **Undefined LOGICAL in DEFINE_TOOL_BACKUP**: Accepted during `waiting_for_user` stage (tool_fallback.py:355-360)

## Test Results

```
45 passed, 1594 warnings in 0.25s
```

All 45 tests pass, including:
- 9 new prompt-flow tests (PROMPT-01 through PROMPT-06, edge cases, error paths, config validation)
- 36 existing tests (no regression)

## Conclusion

Phase 11 is **verified**. All 6 PROMPT requirements are implemented and tested. The pause/prompt/wait/resume flow works correctly for both user-response and timeout paths. Edge cases (no print_stats, resume failure, persist failure) are handled. Config validation rejects invalid timeout values. No regressions in existing tests.
