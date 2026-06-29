---
phase: 09-user-commands
plan: 03
subsystem: tool-fallback-extension
tags: [gcode-commands, user-defined-backup, read-only-command]
dependency_graph:
  requires: ["09-01"]
  provides: "SHOW_TOOL_BACKUPS G-code command"
  affects: [tool_fallback_state.py, test_tool_fallback_extension.py]
tech_stack:
  added: []
  patterns: ["read-only gcode command", "MappingProxyType read", "sorted output"]
key_files:
  created: []
  modified:
    - klippy/extras/tool_fallback.py
    - tests/test_tool_fallback_extension.py
decisions:
  - "SHOW_TOOL_BACKUPS is read-only: no workflow or notification guards needed"
  - "Output is human-readable multi-line format, sorted by tool name"
  - "Shows '(none)' for entries with None backup value"
metrics:
  duration_minutes: 2
  completed: "2026-06-29"
status: complete
---

# Phase 09 Plan 03: SHOW_TOOL_BACKUPS Command

Implement `SHOW_TOOL_BACKUPS` G-code command for listing user-defined backup mappings.

## Summary

Implemented `SHOW_TOOL_BACKUPS` as a read-only command that displays all user-defined backup mappings in human-readable multi-line format. No workflow or notification guards needed. Shows "(empty)" when no mappings exist, "(none)" for entries with None backup values, and sorted output by tool name. 5 test cases added covering registration, empty state, single mapping, multiple sorted mappings, and None backup display.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All 390 tests pass (385 previous + 5 new). Full test suite clean.
