---
phase: 09-user-commands
subsystem: tool-fallback
tags: [gcode-commands, user-defined-backup, state-mutation, phase-complete]
dependency_graph:
  requires: ["08-state-schema-extension"]
  provides: "DEFINE_TOOL_BACKUP, UNDEFINE_TOOL_BACKUP, SHOW_TOOL_BACKUPS G-code commands"
  affects: [tool_fallback.py, tool_fallback_state.py]
tech_stack:
  added: []
  patterns: ["frozen dataclass mutation", "gcode command handler", "workflow guard", "notification guard", "MappingProxyType"]
key_files:
  created:
    - .planning/phases/09-user-commands/09-01-PLAN.md
    - .planning/phases/09-user-commands/09-01-SUMMARY.md
    - .planning/phases/09-user-commands/09-02-PLAN.md
    - .planning/phases/09-user-commands/09-02-SUMMARY.md
    - .planning/phases/09-user-commands/09-03-PLAN.md
    - .planning/phases/09-user-commands/09-03-SUMMARY.md
  modified:
    - klippy/extras/tool_fallback_state.py
    - klippy/extras/tool_fallback.py
    - tests/test_tool_fallback_state.py
    - tests/test_tool_fallback_extension.py
decisions:
  - "with_user_defined_backup follows with_mapping pattern: validates endpoints, no-op check, new instance via _canonical"
  - "None backup value removes the entry from the dict (not sets to None)"
  - "DEFINE_TOOL_BACKUP takes LOGICAL and BACKUP parameters, validates both as configured tools"
  - "UNDEFINE_TOOL_BACKUP takes TOOL parameter, validates mapping exists before removal"
  - "Both mutation commands use _guard_workflow_operation and _guard_notification_operation"
  - "DEFINE no-op reports 'unchanged: no write' and skips persistence"
  - "SHOW_TOOL_BACKUPS is read-only: no workflow or notification guards needed"
  - "Output is human-readable multi-line format, sorted by tool name"
metrics:
  duration_minutes: 7
  completed: "2026-06-29"
  plans_executed: 3
  tasks_completed: 7
  tests_added: 23
  total_tests: 390
status: complete
---

# Phase 09: User Commands Summary

Implement DEFINE_TOOL_BACKUP, UNDEFINE_TOOL_BACKUP, and SHOW_TOOL_BACKUPS G-code commands for runtime management of user-defined backup tool mappings.

## One-Liner

G-code commands for defining, removing, and listing user-defined backup mappings with full validation, workflow guards, and immediate state persistence.

## Plans Executed

### Plan 09-01: `with_user_defined_backup()` State Mutation Method
- Added `with_user_defined_backup(logical, backup)` method to `FallbackState`
- Follows frozen dataclass mutation pattern (returns new instance, never mutates in place)
- Validates configured tools, rejects self-references, detects no-ops
- 8 test cases covering define, undefine, no-op, self-reference, unknown tool, preservation, and immutability
- Commit: `9ca34c6` (RED), `e6bd942` (GREEN)

### Plan 09-02: DEFINE_TOOL_BACKUP + UNDEFINE_TOOL_BACKUP Commands
- `DEFINE_TOOL_BACKUP LOGICAL=T0 BACKUP=T1` — defines a backup mapping
- `UNDEFINE_TOOL_BACKUP TOOL=T0` — removes a user-defined backup mapping
- Both commands: notification guard → workflow guard → parameter validation → state mutation → persistence → response
- 10 test cases covering happy paths, error paths, no-ops, and workflow guards
- Commit: `40002b5` (RED), `67942c3` (GREEN)

### Plan 09-03: SHOW_TOOL_BACKUPS Command
- `SHOW_TOOL_BACKUPS` — lists all user-defined backup mappings in human-readable format
- Read-only: no workflow or notification guards needed
- Shows "(empty)" when no mappings, "(none)" for None backup values, sorted by tool name
- 5 test cases covering registration, empty state, single mapping, multiple sorted mappings, and None display
- Commit: `67d118b` (RED), `db05f25` (GREEN)

## Deviations from Plan

None — all three plans executed exactly as written.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new-endpoint | klippy/extras/tool_fallback.py | Three new G-code command handlers (DEFINE_TOOL_BACKUP, UNDEFINE_TOOL_BACKUP, SHOW_TOOL_BACKUPS) |

All threat mitigations from plan threat models are implemented:
- T-09-01: `_require_configured_tool` validates both parameters; self-reference check; workflow guard; notification guard
- T-09-02: `_require_configured_tool` validates parameter; existence check before removal; same guards as DEFINE
- T-09-03: Information disclosure accepted — only user-defined mappings displayed, no secrets exposed

## Self-Check: PASSED

All 390 tests pass (375 original + 23 new). Full test suite clean.
