---
phase: 09-user-commands
plan: 02
subsystem: tool-fallback-extension
tags: [gcode-commands, user-defined-backup, mutation-commands]
dependency_graph:
  requires: ["09-01"]
  provides: "DEFINE_TOOL_BACKUP and UNDEFINE_TOOL_BACKUP G-code commands"
  affects: [tool_fallback_state.py, test_tool_fallback_extension.py]
tech_stack:
  added: []
  patterns: ["gcode command handler", "workflow guard", "notification guard", "_persist_state"]
key_files:
  created: []
  modified:
    - klippy/extras/tool_fallback.py
    - tests/test_tool_fallback_extension.py
decisions:
  - "DEFINE_TOOL_BACKUP takes LOGICAL and BACKUP parameters, validates both as configured tools"
  - "UNDEFINE_TOOL_BACKUP takes TOOL parameter, validates mapping exists before removal"
  - "Both commands use _guard_workflow_operation and _guard_notification_operation"
  - "DEFINE no-op reports 'unchanged: no write' and skips persistence"
metrics:
  duration_minutes: 3
  completed: "2026-06-29"
status: complete
---

# Phase 09 Plan 02: DEFINE_TOOL_BACKUP + UNDEFINE_TOOL_BACKUP Commands

Implement `DEFINE_TOOL_BACKUP` and `UNDEFINE_TOOL_BACKUP` G-code commands in `tool_fallback.py` with full test coverage.

## Summary

Implemented two G-code commands for managing user-defined backup mappings at runtime:
- `DEFINE_TOOL_BACKUP LOGICAL=T0 BACKUP=T1` — defines a backup mapping, validates inputs, guards against workflow transitions, and persists via `_persist_state`
- `UNDEFINE_TOOL_BACKUP TOOL=T0` — removes a user-defined backup mapping, validates existence, and persists

Both commands follow the established pattern: notification guard → workflow guard → parameter validation → state mutation → persistence → response. 10 test cases added covering happy paths, error paths, no-ops, and workflow guards.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All 385 tests pass (375 original + 10 new). Full test suite clean.
