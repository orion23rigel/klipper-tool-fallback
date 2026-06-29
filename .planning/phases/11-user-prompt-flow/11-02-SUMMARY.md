---
phase: 11-user-prompt-flow
plan: 02
subsystem: tool-fallback
tags: [tests, prompt-flow, undefined-tool, timeout, tdd]
dependency_graph:
  requires: [plan-11-01]
  affects: []
tech_stack:
  added: []
  patterns: [pytest, fake-printer, reactor-advance]
key_files:
  created: []
  modified:
    - tests/test_tool_fallback_extension.py
decisions:
  - T-01: Tests use synchronous invoke() — prompt flow runs to completion within the call
  - T-02: User-response tests manually set up checkpoint/sentinel state since synchronous flow can't be interrupted
  - T-03: Timeout tests use short timeout (0.05s) so flow completes within synchronous call
  - T-04: Config validation tests call parse_global_config() explicitly to trigger validation
metrics:
  duration: ~20m
  completed: 2026-06-29
status: complete

# One-liner: 9 comprehensive tests covering pause trigger, prompt message, sentinel flag, user response, timeout fallback, timeout notification, edge cases, resume failure, and config validation

## Objective

Add comprehensive test coverage for the user prompt flow: undefined tool detection triggering pause/prompt/wait/resume, user-defined backup response, and timeout fallback.

## Test Coverage

| Test | Requirement | What it verifies |
|------|------------|-----------------|
| `test_undefined_tool_prompt_triggers_pause` | PROMPT-01 | Print pauses when undefined tool detected |
| `test_undefined_tool_prompt_displays_message` | PROMPT-02 | Console shows prompt with tool name and DEFINE_TOOL_BACKUP instruction |
| `test_undefined_tool_prompt_sets_sentinel` | PROMPT-03 | Sentinel flag is set and cleared after timeout |
| `test_undefined_tool_user_response_resumes` | PROMPT-03, PROMPT-04 | User DEFINE_TOOL_BACKUP clears sentinel and updates state |
| `test_undefined_tool_timeout_falls_back_to_default` | PROMPT-05 | Timeout maps undefined tool to first configured tool |
| `test_undefined_tool_timeout_sends_notification` | PROMPT-06 | UNDEFINED_TOOL_TIMEOUT notification script runs |
| `test_undefined_tool_prompt_no_print_stats_no_pause` | Edge case | No print_stats means no pause, prompt still displayed |
| `test_undefined_tool_prompt_resume_failure_blocks` | Error path | Resume failure leaves checkpoint in blocked state |
| `test_undefined_tool_config_validation` | D-02 | Zero, negative, and infinity values rejected |

## Deviations from Plan

### Test Adaptations

**1. [Rule 3 - Blocking Issue] Synchronous flow changes test structure**
- **Found during:** Test development
- **Issue:** The prompt flow runs synchronously, so user-response tests can't interleave user input during the wait loop
- **Fix:** User-response tests manually set up checkpoint/sentinel state and verify DEFINE_TOOL_BACKUP behavior
- **Files modified:** tests/test_tool_fallback_extension.py

**2. [Rule 3 - Blocking Issue] import missing**
- **Found during:** Test development
- **Issue:** Tests used `replace()` from dataclasses and `tool_fallback_config` without importing them
- **Fix:** Added `from dataclasses import replace` and `from klippy.extras import tool_fallback_config`
- **Files modified:** tests/test_tool_fallback_extension.py

### No Architectural Changes Required

## Auth Gates
None.

## Self-Check: PASSED
