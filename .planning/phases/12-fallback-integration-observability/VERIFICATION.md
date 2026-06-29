---
phase: 12-fallback-integration-observability
phase_num: 12
started: 2026-06-29T00:00:00Z
completed: 2026-06-29T00:00:00Z
---

# Phase 12 Verification: Fallback Integration & Observability

## Test Results

| Metric | Value |
|--------|-------|
| Total tests | 417 |
| Passed | 417 |
| Failed | 0 |
| Skipped | 0 |

All 417 tests pass with zero regressions (406 existing + 11 new from phase 12).

## Success Criteria Verification

### FALLBACK-01: `resolve_backup_graph()` considers user-defined backups

**Status: PASSED**

User-defined backups are injected at the caller side in `_resolve_backup_with_rescan()` (`tool_fallback.py:1520-1565`). When a `logical_tool` parameter is provided and a user-defined backup exists, an effective backup list is built with the UDD prepended as the first candidate. A temporary `FallbackState` with the modified backup chain is passed to `resolve_backup_graph()`, making the UDD the first candidate in backup resolution.

Key implementation:
- `_resolve_backup_with_rescan()` accepts `logical_tool` parameter (line 1520)
- Backward compatibility: callable detection preserves legacy test behavior (line 1524-1526)
- Effective state creation with UDD prepended to configured chain (lines 1534-1557)
- `resolve_backup_graph()` remains a pure function — no modifications

### FALLBACK-02: User-defined backups flow through `_select_and_conditionally_purge()`

**Status: PASSED**

User-defined backups are applied through the existing `_on_confirmed_runout()` path, which calls `_resolve_backup_with_rescan()` with `logical_tool` (line 1235-1236). The selected backup then flows through the standard preheat, physical selection, heating wait, purge, and persist steps — no separate fast path.

Key implementation:
- `_on_confirmed_runout()` passes `logical_tool` to `_resolve_backup_with_rescan()` (line 1235-1236)
- Selected backup flows through steps 4-9 of `_on_confirmed_runout()`: preheat, select, heat, purge, persist, resume

### FALLBACK-03: Fail-closed safety checkpoints respected

**Status: PASSED**

The effective state created for UDD resolution uses the same `ToolState` fields (loaded, purged, failed) and passes through `resolve_backup_graph()` which enforces all fail-closed safety checks: unloaded tools are skipped, failed tools are skipped, and loop detection prevents cycles. If the UDD tool is unloaded or fails, the configured backup chain is used as fallback.

Safety verification:
- Unloaded UDD tool: falls through to configured backups (verified by `test_user_defined_backup_unloaded_then_configured_used`)
- Failed UDD tool: falls through to configured backups (verified by `test_user_defined_backup_fails_then_configured_used`)
- Unknown authority: UDD is eligible (same as configured, verified by `test_user_defined_backup_respects_fail_closed_unknown_authority`)

### FALLBACK-04: `SHOW_TOOL_FALLBACK_STATE` includes user-defined backup mappings

**Status: PASSED**

`get_status()` calls `self.state.to_dict()` which includes `user_defined_backups` at the top level (`tool_fallback_state.py:162`). The output format matches the state file: `{logical_tool: backup_tool_or_null}`. No code changes were required — the existing `to_dict()` serialization already includes the field.

Verification tests:
- `test_show_fallback_state_includes_user_defined_backups` — confirms key presence and correct mappings
- `test_show_fallback_state_user_defined_backups_empty_when_none` — confirms empty dict when no UDD
- `test_show_fallback_state_user_defined_backups_reflects_undefinition` — confirms removal after UNDEFINE
- `test_show_fallback_state_json_serializable` — confirms valid JSON output

### OBSERVE-01: Undefined tool detection events visible in Klipper's log system

**Status: PASSED**

`cmd_TOOL_FALLBACK_TN` uses `self.gcode.respond_info()` to log when a tool is not configured (`tool_fallback.py:573-574`). The `_handle_undefined_tool_prompt()` method also uses `respond_info()` for the user prompt message. The `test_undefined_tool_detection_logs_via_respond_info` test confirms logging behavior.

### OBSERVE-02: (Implicit — covered by OBSERVE-01 and SHOW_TOOL_FALLBACK_STATE)

**Status: PASSED**

Undefined tool detection is logged via `respond_info()` and user-defined backup state is visible via `SHOW_TOOL_FALLBACK_STATE`. Both observability requirements are satisfied.

## Tests Added

### Plan 01 (6 tests in `tests/test_tool_fallback_fallback.py`):
| Test | Purpose |
|------|---------|
| `test_user_defined_backup_tried_before_configured` | UDD T2 selected over configured T1 |
| `test_user_defined_backup_fails_then_configured_used` | Failed UDD falls through to configured |
| `test_user_defined_backup_unloaded_then_configured_used` | Unloaded UDD falls through to configured |
| `test_user_defined_backup_complete_fallback_workflow` | End-to-end with UDD selected |
| `test_user_defined_backup_respects_fail_closed_unknown_authority` | UDD flows through same safety path |
| `test_no_user_defined_backup_unchanged_behavior` | Regression: no UDD = original behavior |

### Plan 02 (5 tests in `tests/test_tool_fallback_extension.py`):
| Test | Purpose |
|------|---------|
| `test_show_fallback_state_includes_user_defined_backups` | SHOW_TOOL_FALLBACK_STATE contains UDD mappings |
| `test_show_fallback_state_user_defined_backups_empty_when_none` | Empty dict when no UDD |
| `test_show_fallback_state_user_defined_backups_reflects_undefinition` | Mapping removed after UNDEFINE |
| `test_show_fallback_state_json_serializable` | Output is valid JSON |
| `test_undefined_tool_detection_logs_via_respond_info` | Phase 10 logging verified |

## Decisions

| Decision | Description |
|----------|-------------|
| D-01 | User-defined backups injected at caller side (`_resolve_backup_with_rescan`), not in `resolve_backup_graph()` |
| D-02 | User-defined backup prepended to configured backup chain as first candidate |
| D-03 | `resolve_backup_graph()` remains a pure function — no modifications |
| D-05 | User-defined backups flow through `_select_and_conditionally_purge()` — no separate fast path |
| D-06 | Fail-closed safety preserved: unloaded/failed UDD tools skipped, configured chain used |
| D-08 | `get_status()` already includes `user_defined_backups` via `state.to_dict()` — no code change needed |
| D-09 | Output format matches state file: `{logical_tool: backup_tool_or_null}` |

## Commits

| Commit | Message |
|--------|---------|
| `ac71c81` | test(12): add failing tests for user-defined backup priority (RED phase) |
| `895add4` | feat(12): inject user-defined backup into `_resolve_backup_with_rescan()` |
| `4ac78b6` | test(12): add tests for SHOW_TOOL_FALLBACK_STATE user_defined_backups visibility |

## Modified Files

| File | Changes |
|------|---------|
| `klippy/extras/tool_fallback.py` | `_resolve_backup_with_rescan()` signature + UDD injection logic; `_on_confirmed_runout()` passes `logical_tool` |
| `tests/test_tool_fallback_fallback.py` | 6 new tests + `_load_fallback_config_with_udd()` helper + backward compat fix |
| `tests/test_tool_fallback_extension.py` | 5 new tests for SHOW_TOOL_FALLBACK_STATE observability |

## Conclusion

All 6 success criteria (FALLBACK-01 through FALLBACK-04, OBSERVE-01 through OBSERVE-02) are verified as passing. All 417 tests pass with zero regressions. Phase 12 is verified complete.
