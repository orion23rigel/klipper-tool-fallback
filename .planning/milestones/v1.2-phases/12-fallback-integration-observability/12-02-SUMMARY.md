---
phase: 12-fallback-integration-observability
plan: 02
subsystem: tool-fallback
tags: [observability, status, user-defined-backup]
dependency-graph:
  depends-on: [phase-10-undefined-tool-detection]
  provides: [SHOW_TOOL_FALLBACK_STATE-user-defined-visibility]
  affects: [klippy/extras/tool_fallback.py, tests/test_tool_fallback_extension.py]
tech-stack:
  added: []
  patterns: [to_dict-serialization, respond_info-logging]
key-files:
  created: []
  modified:
    - tests/test_tool_fallback_extension.py
decisions:
  - D-08: get_status() already includes user_defined_backups via state.to_dict() — no code change needed
  - D-09: Output format matches state file: {logical_tool: backup_tool_or_null}
metrics:
  duration_minutes: 10
  completed_date: "2026-06-29"
status: complete
---

# Phase 12 Plan 02: SHOW_TOOL_FALLBACK_STATE Observability Summary

**get_status() already exposes user_defined_backups via to_dict(); 5 new tests verify visibility, empty state, undefinition, JSON serialization, and Phase 10 logging.**

## Objective

Expose user-defined backup mappings in the SHOW_TOOL_FALLBACK_STATE output and verify that undefined tool detection events are already logged to Klipper's log system.

## Implementation

### Code Changes

**No code changes required.** `get_status()` calls `self.state.to_dict()` which already includes `user_defined_backups` at the top level (from `tool_fallback_state.py` line 162). The output format matches the state file: `{logical_tool: backup_tool_or_null}`.

### Tests Added to `tests/test_tool_fallback_extension.py`

1. **`test_show_fallback_state_includes_user_defined_backups`** — VERIFY: SHOW_TOOL_FALLBACK_STATE output contains `user_defined_backups` key with correct mappings
2. **`test_show_fallback_state_user_defined_backups_empty_when_none`** — VERIFY: Empty dict when no user-defined backups exist
3. **`test_show_fallback_state_user_defined_backups_reflects_undefinition`** — VERIFY: Mapping removed after UNDEFINE_TOOL_BACKUP
4. **`test_show_fallback_state_json_serializable`** — VERIFY: Output is valid JSON
5. **`test_undefined_tool_detection_logs_via_respond_info`** — VERIFY: Phase 10's _TOOL_FALLBACK_TN logs via `self.gcode.respond_info()` when tool is not configured

## Deviations from Plan

None — plan executed exactly as written. The code verification step confirmed that `to_dict()` already includes `user_defined_backups`, so no code change was needed.

## Tests

| Test | Status |
|------|--------|
| `test_show_fallback_state_includes_user_defined_backups` | ✅ |
| `test_show_fallback_state_user_defined_backups_empty_when_none` | ✅ |
| `test_show_fallback_state_user_defined_backups_reflects_undefinition` | ✅ |
| `test_show_fallback_state_json_serializable` | ✅ |
| `test_undefined_tool_detection_logs_via_respond_info` | ✅ |
| All 406 existing tests | ✅ (zero regression) |

## Commits

- `4ac78b6`: test(12-fallback-integration-observability): add tests for SHOW_TOOL_FALLBACK_STATE user_defined_backups visibility

## Self-Check: PASSED

- SHOW_TOOL_FALLBACK_STATE includes `user_defined_backups` key at top level
- Output format matches state file: `{logical_tool: backup_tool_or_null}`
- user_defined_backups clearly distinguished from configured backups
- 5 new tests covering visibility, empty state, undefinition, JSON, and logging
- All 406 existing tests pass (zero regression)
